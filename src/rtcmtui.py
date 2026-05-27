#! /usr/bin/env python3
"""
Textual dashboard for RTCM stream inspection.
"""

from collections import defaultdict
from io import StringIO

from pyrtcm import RTCMReader
from pyrtcm.rtcmhelpers import tow2utc
from pyrtcm.rtcmtypes_core import GNSSMAP, RTCM_MSGIDS
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, RichLog, Static

from rtcmextrahelpers import beidoutow2utc, glonasstow2utc
from rtcmprint import OUTPUT_FUNCTIONS, print_record


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
        height: 2fr;
        border: round $accent;
    }

    #events {
        height: 1fr;
        border: round $secondary;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
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
        self.details = {}
        self.latest_status = "Ready"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Ready", id="status")
        with Horizontal(id="body"):
            with Vertical(id="left"):
                yield DataTable(id="messages")
                yield DataTable(id="counts")
            with Vertical(id="right"):
                yield RichLog(id="detail", wrap=True, highlight=False)
                yield RichLog(id="events", wrap=True, highlight=False)
        yield Footer()

    def on_mount(self):
        messages = self.query_one("#messages", DataTable)
        messages.add_columns("#", "ID", "Description", "Epoch")
        messages.cursor_type = "row"

        counts = self.query_one("#counts", DataTable)
        counts.add_columns("ID", "Count", "Description")

        self.query_one("#events", RichLog).write("Starting RTCM stream reader")
        self.run_worker(self.read_stream, thread=True)

    def read_stream(self):
        reader = RTCMReader(
            self.stream,
            errorhandler=self.reader_error,
            quitonerror=self.quitonerror,
            validate=self.validate,
        )

        for raw_data, parsed_data in reader:
            self.msg_count += 1
            if raw_data is None or parsed_data is None:
                continue

            msg_id = int(parsed_data.identity)
            self.message_counts[msg_id] += 1

            if self.single_record and self.message_counts[msg_id] > 1:
                self.call_from_thread(self.refresh_counts)
                continue

            if not self.should_display(msg_id):
                self.call_from_thread(self.refresh_counts)
                continue

            description = RTCM_MSGIDS.get(parsed_data.identity, "Unknown")
            epoch = format_epoch(parsed_data, msg_id)
            detail = "" if self.summary_only else render_record(parsed_data, self.obs_summary)
            self.print_count += 0 if self.summary_only else 1
            self.call_from_thread(self.add_message, msg_id, description, epoch, detail)

            if self.debug_output:
                self.call_from_thread(self.log_event, str(parsed_data))

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

    def add_message(self, msg_id, description, epoch, detail):
        row_key = str(self.msg_count)
        table = self.query_one("#messages", DataTable)
        table.add_row(str(self.msg_count), str(msg_id), description, epoch, key=row_key)
        self.details[row_key] = detail
        if detail:
            detail_log = self.query_one("#detail", RichLog)
            detail_log.clear()
            detail_log.write(detail)
        self.refresh_counts()
        self.update_status("Reading")

    def refresh_counts(self):
        counts = self.query_one("#counts", DataTable)
        counts.clear()
        for msg_id in sorted(self.message_counts):
            counts.add_row(
                str(msg_id),
                str(self.message_counts[msg_id]),
                RTCM_MSGIDS.get(str(msg_id), "Unknown"),
            )
        self.update_status(self.latest_status)

    def update_status(self, state):
        self.latest_status = state
        self.query_one("#status", Static).update(
            f"{state} | messages read: {self.msg_count} | displayed: {self.print_count}"
        )

    def reader_error(self, err):
        self.call_from_thread(self.log_event, f"ERROR: {err}")

    def log_event(self, message):
        self.query_one("#events", RichLog).write(message)

    def finish_stream(self):
        self.refresh_counts()
        self.update_status("Complete")
        self.log_event(f"{self.msg_count} messages read. {self.print_count} displayed.")

    def on_data_table_row_highlighted(self, event):
        if event.data_table.id != "messages":
            return

        detail = self.details.get(str(event.row_key.value), "")
        detail_log = self.query_one("#detail", RichLog)
        detail_log.clear()
        if detail:
            detail_log.write(detail)


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
