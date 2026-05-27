#! /usr/bin/env python3
"""
Textual dashboard for RTCM stream inspection.
"""

from collections import defaultdict
from datetime import datetime
from io import StringIO
from os import _exit
from threading import Event
from time import monotonic, sleep

from pyrtcm import RTCMReader
from pyrtcm.rtcmhelpers import tow2utc
from pyrtcm.rtcmtypes_core import GNSSMAP, RTCM_MSGIDS
try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.events import Key
    from textual.widgets import DataTable, Footer, Header, RichLog, Static
except ModuleNotFoundError as err:
    if err.name != "textual":
        raise
    raise SystemExit(
        "Missing optional dependency: textual\n\n"
        "Textual is required only for --tui mode. Install it into the same Python "
        "environment you use to run rtcm-pprint:\n"
        "  python -m pip install textual\n\n"
        "Or install both runtime dependencies at once:\n"
        "  python -m pip install pyrtcm==1.1.12 textual\n"
    ) from None

from rtcmextrahelpers import beidoutow2utc, glonasstow2utc
from rtcmprint import print_record

MESSAGE_RETENTION_SECONDS = 5 * 60


class SelectableDataTable(DataTable):
    """
    DataTable that tells the app when the user starts interacting with it.
    """

    def on_focus(self, _event):
        self.app.activate_table(self.id)

    def on_mouse_down(self, _event):
        self.app.activate_table(self.id)

    def on_key(self, event: Key):
        if event.key in {
            "up",
            "down",
            "home",
            "end",
            "pageup",
            "pagedown",
            "enter",
            "space",
        }:
            self.app.activate_table(self.id)


def msm_epoch_tow(parsed_data):
    """
    Return the MSM epoch time as time-of-week milliseconds.
    """

    msg_prefix = parsed_data.identity[0:3]
    if msg_prefix == "108":  # GLONASS stores day-of-week and time-of-day separately.
        dow = getattr(parsed_data, "DF416")
        sod = getattr(parsed_data, "DF034")
        return sod if dow == 7 else dow * 86400000 + sod

    _, epoch_attr = GNSSMAP[msg_prefix]
    return getattr(parsed_data, epoch_attr)


def format_epoch(parsed_data, msg_id):
    """
    Return an epoch summary for display.
    """

    try:
        epoch_tow = msm_epoch_tow(parsed_data)
        if 1081 <= msg_id <= 1087:
            utc_time = glonasstow2utc(epoch_tow)
        elif 1121 <= msg_id <= 1127:
            utc_time = beidoutow2utc(epoch_tow)
        else:
            utc_time = tow2utc(epoch_tow)
        return f"{epoch_tow / 1000:0.3f}s / {utc_time.strftime('%H:%M:%S')} UTC"
    except (AttributeError, KeyError):
        return ""


def render_record(parsed_data, obs_summary):
    """
    Render the existing pretty-printer output into a string.
    """

    output = StringIO()
    msg_id = int(parsed_data.identity)
    description = RTCM_MSGIDS.get(parsed_data.identity, "Unknown")
    print(f"ID: {msg_id} ({description})", file=output)
    epoch = format_epoch(parsed_data, msg_id)
    if epoch:
        print(f"   Epoch Time: {epoch}", file=output)
    print_record(parsed_data, output, obs_summary)
    return output.getvalue().strip()


def format_received_time(received_at):
    """
    Return a local timestamp with millisecond precision for the detail pane.
    """

    local_time = received_at.astimezone()
    return (
        local_time.strftime("%Y-%m-%d %H:%M:%S")
        + f".{local_time.microsecond // 1000:03d} {local_time.tzname()}"
    )


def add_received_time(detail, received_at):
    """
    Prefix rendered message detail with the local receive time.
    """

    received_line = f"Received Local Time: {format_received_time(received_at)}"
    return f"{received_line}\n{detail}" if detail else received_line


class RTCMTuiApp(App):
    """
    Interactive Textual app for browsing an RTCM stream.
    """

    CSS = """
    Screen {
        layout: vertical;
    }

    #status {
        height: 3;
        padding: 0 1;
    }

    #body {
        height: 1fr;
    }

    #left {
        width: 45%;
    }

    #messages {
        height: 2fr;
    }

    #counts {
        height: 1fr;
    }

    #right {
        width: 55%;
    }

    #detail {
        height: 1fr;
        border: round $accent;
    }
    """

    BINDINGS = [
        Binding("q", "quit_app", "Quit", priority=True),
        Binding("ctrl+c", "quit_app", "Quit", priority=True, show=False),
        Binding("p", "toggle_pause", "Pause", priority=True),
        Binding("escape", "clear_selection", "Clear selection", priority=True),
    ]

    def __init__(
        self,
        stream,
        *,
        quitonerror,
        validate,
        metadata_only,
        obs_summary,
        summary_only,
        single_record,
        debug,
    ):
        super().__init__()
        self.stream = stream
        self.quitonerror = quitonerror
        self.validate = validate
        self.metadata_only = metadata_only
        self.obs_summary = obs_summary
        self.summary_only = summary_only
        self.single_record = single_record
        self.debug_output = debug
        self.msg_count = 0
        self.print_count = 0
        self.message_counts = defaultdict(int)
        self.messages = []
        self.details_by_row = {}
        self.latest_detail_by_type = {}
        self.count_rows = set()
        self.active_detail_source = ("latest", None)
        self.latest_status = "Ready"
        self.shutting_down = False
        self.stop_requested = Event()
        self.pause_requested = Event()
        self.reader_worker = None
        self.programmatic_cursor_move = False
        self.ignored_highlights = set()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Ready", id="status")
        with Horizontal(id="body"):
            with Vertical(id="left"):
                yield SelectableDataTable(id="messages")
                yield SelectableDataTable(id="counts")
            with Vertical(id="right"):
                yield RichLog(id="detail", wrap=True, highlight=False)
        yield Footer()

    def on_mount(self):
        messages = self.query_one("#messages", DataTable)
        messages.add_columns(("#", "seq"), ("ID", "id"), ("Description", "description"), ("Epoch", "epoch"))
        messages.cursor_type = "row"
        messages.show_cursor = False

        counts = self.query_one("#counts", DataTable)
        counts.add_columns(("ID", "id"), ("Count", "count"), ("Description", "description"))
        counts.cursor_type = "row"
        counts.show_cursor = False

        self.show_detail("Starting RTCM stream reader")
        self.reader_worker = self.run_worker(self.read_stream, thread=True)

    def read_stream(self):
        try:
            reader = RTCMReader(
                self.stream,
                errorhandler=self.reader_error,
                quitonerror=self.quitonerror,
                validate=self.validate,
            )

            for raw_data, parsed_data in reader:
                if self.stop_requested.is_set():
                    break
                while self.pause_requested.is_set() and not self.stop_requested.is_set():
                    sleep(0.1)

                self.msg_count += 1
                if raw_data is None or parsed_data is None:
                    continue

                msg_id = int(parsed_data.identity)
                self.message_counts[msg_id] += 1

                description = RTCM_MSGIDS.get(parsed_data.identity, "Unknown")
                received_at = datetime.now().astimezone()
                detail = add_received_time(
                    render_record(parsed_data, self.obs_summary),
                    received_at,
                )
                self.latest_detail_by_type[str(msg_id)] = detail
                self.call_from_thread(self.update_active_type_detail, str(msg_id), detail)

                if self.single_record and self.message_counts[msg_id] > 1:
                    self.call_from_thread(self.refresh_counts)
                    continue

                if not self.should_display(msg_id):
                    self.call_from_thread(self.refresh_counts)
                    continue

                epoch = format_epoch(parsed_data, msg_id)
                self.print_count += 0 if self.summary_only else 1
                self.call_from_thread(
                    self.add_message,
                    monotonic(),
                    self.msg_count,
                    msg_id,
                    description,
                    epoch,
                    "" if self.summary_only else detail,
                )

                if self.debug_output:
                    self.call_from_thread(self.show_detail, str(parsed_data))
        except Exception as err:  # pylint: disable=broad-exception-caught
            if not self.stop_requested.is_set():
                self.call_from_thread(self.show_detail, f"ERROR: {err}")
        finally:
            if not self.stop_requested.is_set():
                self.call_from_thread(self.finish_stream)

    def should_display(self, msg_id):
        if self.summary_only:
            return False
        if not self.metadata_only:
            return True
        if 1070 <= msg_id <= 1229:  # MSM
            return False
        if 1001 <= msg_id <= 1004:  # GPS
            return False
        if 1009 <= msg_id <= 1012:  # GLONASS
            return False
        return True

    def add_message(self, received_at, sequence, msg_id, description, epoch, detail):
        row_key = str(sequence)
        self.messages.append((received_at, row_key, str(sequence), str(msg_id), description, epoch))
        self.details_by_row[row_key] = detail
        self.add_message_row(row_key, str(sequence), str(msg_id), description, epoch)
        self.prune_old_messages()
        if detail and self.active_detail_source[0] == "latest":
            self.ensure_auto_follow()
            self.show_detail(detail)
        self.refresh_counts()
        self.update_status("Reading")

    def add_message_row(self, row_key, sequence, msg_id, description, epoch):
        table = self.query_one("#messages", DataTable)
        selected_key = self.selected_row_key(table)
        table.add_row(sequence, msg_id, description, epoch, key=row_key)
        table.sort("seq", key=int, reverse=True)
        if selected_key is not None:
            self.move_cursor_to_key(table, selected_key)
        else:
            self.move_cursor_to_row(table, 0)

    def prune_old_messages(self):
        cutoff = monotonic() - MESSAGE_RETENTION_SECONDS
        table = self.query_one("#messages", DataTable)

        expired = [message for message in self.messages if message[0] < cutoff]
        if not expired:
            return

        expired_keys = {message[1] for message in expired}
        self.messages = [
            message for message in self.messages if message[1] not in expired_keys
        ]

        for _, row_key, *_ in expired:
            self.details_by_row.pop(row_key, None)
            try:
                table.remove_row(row_key)
            except KeyError:
                pass
            if self.active_detail_source == ("row", row_key):
                self.active_detail_source = ("latest", None)
                self.show_detail("Selected message aged out of the five-minute window.")

    def refresh_counts(self):
        counts = self.query_one("#counts", DataTable)
        selected_key = self.selected_row_key(counts)
        for msg_id in sorted(self.message_counts):
            row_key = f"type-{msg_id}"
            count = str(self.message_counts[msg_id])
            description = RTCM_MSGIDS.get(str(msg_id), "Unknown")
            if row_key in self.count_rows:
                counts.update_cell(row_key, "count", count)
                counts.update_cell(row_key, "description", description)
            else:
                counts.add_row(str(msg_id), count, description, key=row_key)
                self.count_rows.add(row_key)
        if selected_key is not None:
            self.move_cursor_to_key(counts, selected_key)
        self.update_status(self.latest_status)

    def selected_row_key(self, table):
        if not table.show_cursor:
            return None
        if table.row_count == 0 or not table.is_valid_row_index(table.cursor_row):
            return None
        return str(table.ordered_rows[table.cursor_row].key.value)

    def move_cursor_to_key(self, table, row_key):
        try:
            self.move_cursor_to_row(table, table.get_row_index(row_key))
        except KeyError:
            pass

    def move_cursor_to_row(self, table, row):
        if table.row_count and table.is_valid_row_index(row):
            self.ignored_highlights.add(
                (table.id, str(table.ordered_rows[row].key.value))
            )
        self.programmatic_cursor_move = True
        try:
            table.move_cursor(row=row, animate=False, scroll=True)
        finally:
            self.programmatic_cursor_move = False

    def ensure_auto_follow(self):
        messages = self.query_one("#messages", DataTable)
        counts = self.query_one("#counts", DataTable)
        messages.show_cursor = False
        counts.show_cursor = False
        if messages.row_count:
            self.move_cursor_to_row(messages, 0)

    def update_status(self, state):
        self.latest_status = state
        pause = " | paused" if self.pause_requested.is_set() else ""
        self.query_one("#status", Static).update(
            f"{state}{pause} | messages read: {self.msg_count} | displayed: {self.print_count}"
        )

    def reader_error(self, err):
        if not self.stop_requested.is_set():
            self.call_from_thread(self.show_detail, f"ERROR: {err}")

    def show_detail(self, message):
        detail_log = self.query_one("#detail", RichLog)
        detail_log.clear()
        detail_log.write(message)

    def update_active_type_detail(self, msg_id, detail):
        if self.active_detail_source == ("type", msg_id):
            self.show_detail(detail)

    def finish_stream(self):
        self.refresh_counts()
        self.update_status("Complete")
        if not self.details_by_row:
            self.show_detail(f"{self.msg_count} messages read. {self.print_count} displayed.")

    def on_data_table_row_highlighted(self, event):
        if self.shutting_down:
            return

        row_key = str(getattr(event.row_key, "value", event.row_key))
        ignored_highlight = (event.data_table.id, row_key)
        if self.programmatic_cursor_move or ignored_highlight in self.ignored_highlights:
            self.ignored_highlights.discard(ignored_highlight)
            return

        if event.data_table.id == "messages":
            self.activate_table("messages")
            self.active_detail_source = ("row", row_key)
            detail = self.details_by_row.get(row_key, "")
        elif event.data_table.id == "counts":
            self.activate_table("counts")
            msg_id = row_key.removeprefix("type-")
            self.active_detail_source = ("type", msg_id)
            detail = self.latest_detail_by_type.get(
                msg_id,
                f"No decoded message detail available yet for message type {msg_id}.",
            )
        else:
            return

        if detail:
            self.show_detail(detail)

    def activate_table(self, table_id):
        messages = self.query_one("#messages", DataTable)
        counts = self.query_one("#counts", DataTable)
        messages.show_cursor = table_id == "messages"
        counts.show_cursor = table_id == "counts"
        table = messages if table_id == "messages" else counts
        self.select_current_table_row(table)

    def select_current_table_row(self, table):
        if table.row_count == 0 or not table.is_valid_row_index(table.cursor_row):
            return

        row_key = str(table.ordered_rows[table.cursor_row].key.value)
        if table.id == "messages":
            self.active_detail_source = ("row", row_key)
            detail = self.details_by_row.get(row_key, "")
        elif table.id == "counts":
            msg_id = row_key.removeprefix("type-")
            self.active_detail_source = ("type", msg_id)
            detail = self.latest_detail_by_type.get(
                msg_id,
                f"No decoded message detail available yet for message type {msg_id}.",
            )
        else:
            return

        if detail:
            self.show_detail(detail)

    def action_toggle_pause(self):
        """
        Pause or resume consuming the RTCM stream.
        """

        if self.pause_requested.is_set():
            self.pause_requested.clear()
            self.update_status("Reading")
        else:
            self.pause_requested.set()
            self.update_status("Paused")

    def action_clear_selection(self):
        """
        Clear table selections and return the message list to auto-follow mode.
        """

        self.ensure_auto_follow()
        self.active_detail_source = ("latest", None)
        self.update_status(self.latest_status)

    def on_key(self, event: Key):
        """
        Ensure q exits even when a table has focus.
        """

        if event.key.lower() == "q":
            event.stop()
            self.action_quit_app()
        elif event.key.lower() == "p":
            event.stop()
            self.action_toggle_pause()
        elif event.key == "escape":
            event.stop()
            self.action_clear_selection()

    def action_quit_app(self):
        """
        Stop the reader thread and exit the TUI.
        """

        self.stop_requested.set()
        self.shutting_down = True
        if self.reader_worker is not None:
            self.reader_worker.cancel()
        try:
            self.stream.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        self.exit()


def run_tui(
    stream,
    *,
    quitonerror,
    validate,
    metadata_only,
    obs_summary,
    summary_only,
    single_record,
    debug,
):
    app = RTCMTuiApp(
        stream,
        quitonerror=quitonerror,
        validate=validate,
        metadata_only=metadata_only,
        obs_summary=obs_summary,
        summary_only=summary_only,
        single_record=single_record,
        debug=debug,
    )
    app.run()
    if app.stop_requested.is_set():
        _exit(0)
