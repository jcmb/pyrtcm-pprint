#!/usr/bin/env python3
"""
Apache CGI front end for rtcm-pprint.

Requires Python 3.10+ (Trimble server: Python 3.12).

CGI mode expects an HTML form POST with multipart/form-data and a required
file field:

    <input type="file" name="file" />

Optional form fields (checkboxes, any truthy value enables the flag):

    metadataOnly, obsSummary, summaryOnly, singleRecord, debug

Full decode output (none of metadataOnly, summaryOnly, or singleRecord) is
returned as a ZIP download automatically. Compact modes return plain text.

Local testing (no Apache required):

    python3 rtcm-pprint.cgi --file samples/R750_626_MSM7.bin
    python3 rtcm-pprint.cgi --file samples/R750_626_MSM7.bin --singleRecord
    python3 rtcm-pprint.cgi --file samples/R750_626_MSM7.bin --output decode.zip

Environment variables (optional):

    RTCM_PPRINT   Path to the compiled rtcm-pprint executable
                  (default: rtcm-pprint in the same directory as this script)
    RTCM_CGI_LOG    Log file path; setting this enables file logging
    RTCM_CGI_DEBUG  Set to 1 to enable file logging and stderr debug output
    MAX_UPLOAD_BYTES  Maximum uploaded file size (default: 52428800 = 50 MiB)

Optional CGI form field:

    cgiDebug      Enable file logging, stderr debug, and debug output in error responses

File logging is disabled by default. Enable with RTCM_CGI_DEBUG=1, RTCM_CGI_LOG,
or the cgiDebug form field.

Example Apache configuration:

    ScriptAlias /cgi-bin/rtcm-pprint /path/to/pyrtcm-pprint/rtcm-pprint.cgi
    <Directory /path/to/pyrtcm-pprint>
        Options +ExecCGI
        AddHandler cgi-script .cgi
        Require all granted
    </Directory>

Standard Linux layout:

    /usr/lib/cgi-bin/rtcm-pprint.cgi
    /usr/lib/cgi-bin/rtcm-pprint

The script finds the decoder using Apache SCRIPT_FILENAME, then
/usr/lib/cgi-bin/rtcm-pprint. Override with RTCM_PPRINT if needed.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile
from pathlib import Path

DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_LOG_RESPONSE_BODY = 16384
TRUTHY = {"1", "on", "yes", "true"}
FormData = dict[str, str | tuple[bytes, str]]
LOG_FILE_USED: Path | None = None
CGI_FILE_LOGGING = False
CGI_ENV_KEYS = (
    "GATEWAY_INTERFACE",
    "REQUEST_METHOD",
    "CONTENT_TYPE",
    "CONTENT_LENGTH",
    "QUERY_STRING",
    "SCRIPT_FILENAME",
    "SCRIPT_NAME",
    "SERVER_SOFTWARE",
    "SERVER_NAME",
    "REMOTE_ADDR",
    "RTCM_PPRINT",
    "RTCM_CGI_LOG",
    "RTCM_CGI_DEBUG",
    "MAX_UPLOAD_BYTES",
)


class DebugLog:
    """
    Collect debug lines for CGI error responses, stderr, and a log file.
    """

    def __init__(self, enabled: bool, *, cgi_mode: bool = False):
        self.enabled = enabled
        self.cgi_mode = cgi_mode
        self.lines: list[str] = []

    def log(self, message: str) -> None:
        line = f"rtcm-pprint.cgi: {message}"
        self.lines.append(line)
        if self.cgi_mode and CGI_FILE_LOGGING:
            write_log_file(line)
        if self.enabled:
            print(line, file=sys.stderr, flush=True)

    def section(self, title: str) -> None:
        self.log(f"--- {title} ---")

    def dump(self) -> str:
        return "\n".join(self.lines)


DEBUG = DebugLog(False)


DEFAULT_CGI_BIN = Path("/usr/lib/cgi-bin")


def script_root() -> Path:
    return Path(__file__).resolve().parent


def cgi_bin_dir() -> Path:
    """
    Directory containing this CGI script, preferring Apache SCRIPT_FILENAME.
    """

    script_filename = os.environ.get("SCRIPT_FILENAME", "").strip()
    if script_filename:
        return Path(script_filename).resolve().parent
    return script_root()


def unique_paths(paths: list[Path]) -> list[Path]:
    seen = set()
    unique = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def log_file_candidates() -> list[Path]:
    configured = os.environ.get("RTCM_CGI_LOG")
    if configured:
        return [Path(configured).expanduser()]

    candidates = [
        cgi_bin_dir() / "rtcm-pprint-cgi.log",
        DEFAULT_CGI_BIN / "rtcm-pprint-cgi.log",
    ]
    tmpdir = os.environ.get("TMPDIR", "").strip()
    if tmpdir:
        candidates.append(Path(tmpdir) / "rtcm-pprint-cgi.log")
    candidates.extend(
        [
            Path("/tmp/rtcm-pprint-cgi.log"),
            Path("/var/tmp/rtcm-pprint-cgi.log"),
        ]
    )
    return unique_paths(candidates)


def write_log_file(message: str) -> None:
    if not CGI_FILE_LOGGING:
        return

    global LOG_FILE_USED

    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    line = f"{timestamp} {message}"

    paths = [LOG_FILE_USED] if LOG_FILE_USED is not None else []
    for path in log_file_candidates():
        if path not in paths:
            paths.append(path)

    for path in paths:
        if path is None:
            continue
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
            LOG_FILE_USED = path
            return
        except OSError:
            continue


def cgi_file_logging_enabled(form: FormData | None = None) -> bool:
    if os.environ.get("RTCM_CGI_LOG", "").strip():
        return True
    if os.environ.get("RTCM_CGI_DEBUG", "").strip().lower() in TRUTHY:
        return True
    if form is not None and form_flag(form, "cgiDebug"):
        return True
    return False


def set_cgi_file_logging(form: FormData | None = None) -> bool:
    global CGI_FILE_LOGGING

    CGI_FILE_LOGGING = cgi_file_logging_enabled(form)
    return CGI_FILE_LOGGING


def bootstrap_cgi_log(note: str) -> None:
    """
    Earliest possible log line when running under Apache CGI.
    """

    if not is_cgi() or not CGI_FILE_LOGGING:
        return
    write_log_file(f"rtcm-pprint.cgi: {note}")


def max_upload_bytes() -> int:
    raw = os.environ.get("MAX_UPLOAD_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES))
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_MAX_UPLOAD_BYTES


def is_cgi() -> bool:
    return os.environ.get("GATEWAY_INTERFACE", "").startswith("CGI/")


def debug_enabled(form: FormData | None = None) -> bool:
    if os.environ.get("RTCM_CGI_DEBUG", "").strip().lower() in TRUTHY:
        return True
    if form is not None and form_flag(form, "cgiDebug"):
        return True
    return False


def init_debug(
    form: FormData | None = None,
    *,
    force: bool = False,
    cgi_mode: bool = False,
) -> DebugLog:
    global DEBUG
    DEBUG = DebugLog(force or debug_enabled(form), cgi_mode=cgi_mode)
    DEBUG.section("startup")
    DEBUG.log(f"python={sys.version.split()[0]} executable={sys.executable}")
    DEBUG.log(f"script={Path(__file__).resolve()}")
    DEBUG.log(f"cgi_bin_dir={cgi_bin_dir()}")
    DEBUG.log(f"cwd={Path.cwd()}")
    try:
        DEBUG.log(f"uid={os.getuid()} gid={os.getgid()}")
    except AttributeError:
        DEBUG.log("uid/gid unavailable on this platform")
    DEBUG.log(f"is_cgi={is_cgi()}")
    if is_cgi():
        DEBUG.section("cgi environment")
        for key in CGI_ENV_KEYS:
            DEBUG.log(f"{key}={os.environ.get(key, '')!r}")
    return DEBUG


def summarize_form(form: FormData) -> None:
    DEBUG.section("parsed form")
    for name, value in sorted(form.items()):
        if isinstance(value, tuple):
            data, filename = value
            DEBUG.log(f"{name}=<file {filename!r}, {len(data)} bytes>")
        else:
            DEBUG.log(f"{name}={value!r}")


def format_error_message(message: str, *, include_traceback: bool = False) -> str:
    parts = [message.rstrip()]
    if DEBUG.lines:
        parts.extend(["", "--- CGI debug ---", DEBUG.dump()])
    if LOG_FILE_USED is not None:
        parts.extend(["", f"Log file: {LOG_FILE_USED}"])
    elif DEBUG.cgi_mode and CGI_FILE_LOGGING:
        parts.extend(
            [
                "",
                "Log file: not writable; tried:",
                *[f"  {path}" for path in log_file_candidates()],
            ]
        )
    if include_traceback:
        parts.extend(["", "--- traceback ---", traceback.format_exc()])
    return "\n".join(parts) + "\n"


def decoder_candidates() -> list[Path]:
    names = ("rtcm-pprint", "rtcm-pprint.exe")
    search_roots = unique_paths(
        [
            cgi_bin_dir(),
            script_root(),
            DEFAULT_CGI_BIN,
        ]
    )
    candidates = []
    # Onefile build: /usr/lib/cgi-bin/rtcm-pprint beside rtcm-pprint.cgi
    for root in search_roots:
        for name in names:
            candidates.append(root / name)
    # Onedir build: /usr/lib/cgi-bin/rtcm-pprint/rtcm-pprint
    for root in search_roots:
        for name in names:
            candidates.append(root / "rtcm-pprint" / name)
    return unique_paths(candidates)


def decoder_layout(decoder: Path) -> str:
    if decoder_workdir(decoder) is not None:
        return "onedir"
    if decoder.name.startswith("rtcm-pprint"):
        return "onefile"
    return "custom"


def decoder_workdir(decoder: Path) -> Path | None:
    bundle_dir = decoder.parent
    if (bundle_dir / "_internal").is_dir():
        return bundle_dir
    return None


def resolve_decoder(explicit: Path | None = None, *, allow_python_fallback: bool = False) -> Path:
    DEBUG.section("resolve decoder")
    if explicit is not None:
        decoder = explicit.resolve()
        DEBUG.log(f"explicit decoder={decoder}")
        if not decoder.is_file():
            raise FileNotFoundError(f"Decoder not found: {decoder}")
        if decoder.suffix != ".py" and not os.access(decoder, os.X_OK):
            raise FileNotFoundError(f"Decoder is not executable: {decoder}")
        DEBUG.log(f"using decoder={decoder} layout={decoder_layout(decoder)}")
        return decoder

    configured = os.environ.get("RTCM_PPRINT")
    if configured:
        decoder = Path(configured).resolve()
        DEBUG.log(f"RTCM_PPRINT={decoder}")
        if not decoder.is_file():
            raise FileNotFoundError(f"RTCM_PPRINT not found: {decoder}")
        if decoder.suffix != ".py" and not os.access(decoder, os.X_OK):
            raise FileNotFoundError(f"RTCM_PPRINT is not executable: {decoder}")
        DEBUG.log(f"using decoder={decoder} layout={decoder_layout(decoder)}")
        return decoder

    compiled = script_root() / "rtcm-pprint"
    for candidate in decoder_candidates():
        DEBUG.log(
            f"checking decoder={candidate} "
            f"exists={candidate.is_file()} executable={os.access(candidate, os.X_OK)}"
        )
        if candidate.is_file() and os.access(candidate, os.X_OK):
            DEBUG.log(f"using decoder={candidate} layout={decoder_layout(candidate)}")
            return candidate

    DEBUG.log(f"no compiled decoder found under {compiled.parent}")

    if allow_python_fallback:
        script = script_root() / "src" / "rtcm-pprint.py"
        DEBUG.log(f"python fallback={script} exists={script.is_file()}")
        if script.is_file():
            DEBUG.log(f"using decoder={script}")
            return script

    raise FileNotFoundError(
        "Compiled rtcm-pprint executable not found. "
        f"Expected one of {[str(path) for path in decoder_candidates()]}, "
        "or set RTCM_PPRINT, or use --decoder."
    )


def form_flag(form: FormData, name: str) -> bool:
    if name not in form:
        return False
    value = form[name]
    if isinstance(value, tuple):
        return False
    return str(value).strip().lower() in TRUTHY


def should_auto_zip(form: FormData) -> bool:
    """
    Full decode output is zipped; compact modes return plain text.
    """

    return not any(
        form_flag(form, name)
        for name in ("metadataOnly", "summaryOnly", "singleRecord")
    )


def form_from_local_args(args: argparse.Namespace) -> FormData:
    form: FormData = {}
    for name in (
        "metadataOnly",
        "obsSummary",
        "summaryOnly",
        "singleRecord",
        "debug",
    ):
        if getattr(args, name):
            form[name] = "on"
    return form


def parse_boundary(content_type: str) -> bytes:
    for part in content_type.split(";"):
        part = part.strip()
        if not part.lower().startswith("boundary="):
            continue
        boundary = part[9:].strip()
        if boundary.startswith('"') and boundary.endswith('"'):
            boundary = boundary[1:-1]
        if not boundary:
            break
        return boundary.encode("latin-1")
    raise ValueError("Missing multipart boundary")


def parse_disposition(header_line: str) -> tuple[str | None, str | None]:
    name = None
    filename = None
    for token in header_line.split(";"):
        token = token.strip()
        if token.lower().startswith("name="):
            name = token[5:].strip().strip('"')
        elif token.lower().startswith("filename="):
            filename = token[9:].strip().strip('"')
    return name, filename


def parse_multipart_form(body: bytes, content_type: str) -> FormData:
    """
    Parse multipart/form-data without the deprecated cgi module.
    """

    boundary = parse_boundary(content_type)
    DEBUG.log(f"multipart boundary={boundary!r}")
    delimiter = b"--" + boundary
    form: FormData = {}

    for part in body.split(delimiter):
        if not part or part in (b"--", b"--\r\n", b"\r\n", b"\n"):
            continue
        if part.startswith(b"\r\n"):
            part = part[2:]
        elif part.startswith(b"\n"):
            part = part[1:]
        if not part.strip():
            continue

        header_bytes, _, payload = part.partition(b"\r\n\r\n")
        if not header_bytes:
            continue
        if payload.endswith(b"\r\n"):
            payload = payload[:-2]
        elif payload.endswith(b"\n"):
            payload = payload[:-1]

        field_name = None
        filename = None
        for line in header_bytes.decode("latin-1", errors="replace").split("\r\n"):
            if line.lower().startswith("content-disposition:"):
                field_name, filename = parse_disposition(line.split(":", 1)[1].strip())

        if not field_name:
            continue

        if filename is not None:
            form[field_name] = (payload, filename)
        else:
            form[field_name] = payload.decode("utf-8", errors="replace")

    DEBUG.log(f"parsed {len(form)} form field(s)")
    return form


def read_request_body() -> bytes:
    try:
        content_length = int(os.environ.get("CONTENT_LENGTH", "0"))
    except ValueError as err:
        raise ValueError("Invalid CONTENT_LENGTH") from err

    DEBUG.log(f"reading request body, CONTENT_LENGTH={content_length}")

    if content_length <= 0:
        raise ValueError("Missing request body")

    body = sys.stdin.buffer.read(content_length)
    DEBUG.log(f"read {len(body)} bytes from stdin")
    if len(body) != content_length:
        raise ValueError(
            f"Incomplete request body: expected {content_length}, got {len(body)}"
        )
    return body


def safe_filename(name: str) -> str:
    cleaned = os.path.basename(name or "upload.bin")
    cleaned = re.sub(r"[^\w.\-]", "_", cleaned)
    return cleaned or "upload.bin"


def build_cgi_headers(
    body: bytes,
    *,
    content_type: str,
    status: int = 200,
    disposition: str | None = None,
) -> str:
    header_lines: list[str] = []
    if status != 200:
        header_lines.append(f"Status: {status}")
    header_lines.append(f"Content-Type: {content_type}")
    if disposition:
        header_lines.append(f"Content-Disposition: {disposition}")
    header_lines.append(f"Content-Length: {len(body)}")
    return "\r\n".join(header_lines) + "\r\n\r\n"


def log_cgi_response(headers: str, body: bytes) -> None:
    """
    Record the exact CGI response sent to Apache (headers + body).
    """

    if not CGI_FILE_LOGGING:
        return

    def record(message: str) -> None:
        write_log_file(f"rtcm-pprint.cgi: {message}")
        if DEBUG.enabled:
            print(f"rtcm-pprint.cgi: {message}", file=sys.stderr, flush=True)

    record("--- cgi response ---")
    record(f"headers raw={headers!r}")
    record(f"header bytes={len(headers.encode('ascii'))}")
    record(f"body bytes={len(body)}")
    record(f"total bytes={len(headers.encode('ascii')) + len(body)}")
    for line in headers.split("\r\n"):
        if line:
            record(f"header: {line}")

    if not body:
        record("body: (empty)")
        return

    if len(body) <= MAX_LOG_RESPONSE_BODY:
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            record(f"body raw={body!r}")
            return
        record("body text:")
        if "\n" in text:
            for line in text.splitlines():
                record(f"  | {line}")
        else:
            record(f"  | {text}")
        return

    preview = body[:512]
    try:
        record(f"body preview: {preview.decode('utf-8', errors='replace')!r}")
    except Exception:
        record(f"body preview raw={preview!r}")
    record(f"body truncated in log ({len(body)} bytes total)")


def emit_cgi_response(headers: str, body: bytes) -> None:
    """
    Write a CGI response using stdout.buffer only.

    Mixing sys.stdout.write() with sys.stdout.buffer.write() can corrupt
    the response and cause Apache to return 500.
    """

    log_cgi_response(headers, body)
    sys.stdout.buffer.write(headers.encode("ascii"))
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()


def send_fatal_cgi(message: str) -> None:
    """
    Last-resort CGI output when normal handlers fail.
    """

    try:
        body = message.encode("utf-8")
        headers = build_cgi_headers(
            body,
            content_type="text/plain; charset=utf-8",
        )
        emit_cgi_response(headers, body)
    except Exception:
        pass


def send_response(
    body: bytes,
    *,
    content_type: str,
    status: int = 200,
    disposition: str | None = None,
) -> None:
    headers = build_cgi_headers(
        body,
        content_type=content_type,
        status=status,
        disposition=disposition,
    )
    emit_cgi_response(headers, body)


def send_text(message: str, *, status: int = 200) -> None:
    send_response(message.encode("utf-8"), content_type="text/plain; charset=utf-8", status=status)


def parse_upload(form: FormData) -> tuple[bytes, str]:
    if "file" not in form:
        raise ValueError("Missing required form field: file")

    upload = form["file"]
    if not isinstance(upload, tuple):
        raise ValueError("No RTCM file was uploaded")

    data, filename = upload
    if not filename:
        raise ValueError("No RTCM file was uploaded")

    if len(data) > max_upload_bytes():
        limit = max_upload_bytes()
        raise ValueError(f"Uploaded file exceeds MAX_UPLOAD_BYTES ({limit} bytes)")

    if not data:
        raise ValueError("Uploaded file is empty")

    return data, safe_filename(filename)


def build_command(
    decoder: Path,
    rtcm_file: Path,
    form: FormData,
) -> list[str]:
    if decoder.suffix == ".py":
        command = [sys.executable, str(decoder)]
    else:
        command = [str(decoder)]

    command.extend(
        [
            "--RTCMFile",
            str(rtcm_file),
            "--quitonerror",
            "0",
        ]
    )

    if form_flag(form, "metadataOnly"):
        command.append("--metadataOnly")
    if form_flag(form, "obsSummary"):
        command.append("--obsSummary")
    if form_flag(form, "summaryOnly"):
        command.append("--summaryOnly")
    if form_flag(form, "singleRecord"):
        command.append("--singleRecord")
    if form_flag(form, "debug"):
        command.append("--debug")

    return command


def run_decoder(command: list[str], decoder: Path) -> tuple[int, bytes, bytes]:
    DEBUG.section("run decoder")
    DEBUG.log(f"command={' '.join(command)!r}")
    workdir = decoder_workdir(decoder)
    DEBUG.log(f"subprocess cwd={workdir!r}")
    completed = subprocess.run(
        command,
        capture_output=True,
        check=False,
        cwd=workdir,
    )
    DEBUG.log(f"returncode={completed.returncode}")
    DEBUG.log(f"stdout bytes={len(completed.stdout)} stderr bytes={len(completed.stderr)}")
    if completed.stderr:
        preview = completed.stderr.decode("utf-8", errors="replace").strip()
        if len(preview) > 500:
            preview = preview[:500] + "..."
        DEBUG.log(f"stderr preview={preview!r}")
    if completed.returncode != 0 and completed.stdout:
        preview = completed.stdout.decode("utf-8", errors="replace").strip()
        if len(preview) > 500:
            preview = preview[:500] + "..."
        DEBUG.log(f"stdout preview={preview!r}")
    return completed.returncode, completed.stdout, completed.stderr


def make_zip_output(upload_name: str, decode_text: bytes) -> tuple[bytes, str]:
    stem = Path(upload_name).stem or "rtcm"
    text_name = f"{stem}-decode.txt"
    archive_name = f"{stem}-decode.zip"

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(text_name, decode_text)

    return buffer.getvalue(), archive_name


def decode_upload(
    upload_data: bytes,
    upload_name: str,
    form: FormData,
    *,
    decoder: Path | None = None,
    allow_python_fallback: bool = False,
) -> tuple[bytes, bytes | None, str | None]:
    if len(upload_data) > max_upload_bytes():
        limit = max_upload_bytes()
        raise ValueError(f"Uploaded file exceeds MAX_UPLOAD_BYTES ({limit} bytes)")

    if not upload_data:
        raise ValueError("Uploaded file is empty")

    pprint_executable = resolve_decoder(decoder, allow_python_fallback=allow_python_fallback)

    with tempfile.NamedTemporaryFile(suffix=".bin", delete=True) as handle:
        handle.write(upload_data)
        handle.flush()
        DEBUG.log(f"temp input file={handle.name} size={len(upload_data)}")

        command = build_command(pprint_executable, Path(handle.name), form)
        returncode, stdout, stderr = run_decoder(command, pprint_executable)

    if returncode != 0 and not stdout.strip():
        detail = stderr.decode("utf-8", errors="replace").strip()
        if not detail:
            detail = stdout.decode("utf-8", errors="replace").strip()
        if not detail:
            detail = f"rtcm-pprint exited with status {returncode}"
        raise RuntimeError(detail)

    if should_auto_zip(form):
        DEBUG.log("auto zip (full decode output)")
        body, archive_name = make_zip_output(upload_name, stdout)
        return stdout, body, archive_name

    DEBUG.log("plain text (compact decode options)")
    return stdout, None, None


def local_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local test mode for rtcm-pprint.cgi (no Apache required).",
    )
    parser.add_argument(
        "--file",
        required=True,
        type=Path,
        help="RTCM file to decode",
    )
    parser.add_argument(
        "--decoder",
        type=Path,
        help="Path to rtcm-pprint executable or rtcm-pprint.py",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write auto-zipped full decode output to this file",
    )
    parser.add_argument("--metadataOnly", action="store_true")
    parser.add_argument("--obsSummary", action="store_true")
    parser.add_argument("--summaryOnly", action="store_true")
    parser.add_argument("--singleRecord", action="store_true")
    parser.add_argument("--debug", action="store_true", help="Pass --debug to rtcm-pprint")
    parser.add_argument(
        "--cgi-debug",
        action="store_true",
        help="Enable CGI wrapper debug logging",
    )
    return parser


def run_local() -> int:
    parser = local_arg_parser()
    args = parser.parse_args()

    init_debug(force=args.cgi_debug)

    rtcm_file = args.file.resolve()
    if not rtcm_file.is_file():
        print(format_error_message(f"ERROR: file not found: {rtcm_file}"), file=sys.stderr)
        return 1

    upload_data = rtcm_file.read_bytes()
    form = form_from_local_args(args)
    DEBUG.log(f"local file={rtcm_file} size={len(upload_data)}")
    summarize_form(form)

    try:
        decoder = resolve_decoder(args.decoder, allow_python_fallback=True)

        decode_text, zip_body, archive_name = decode_upload(
            upload_data,
            safe_filename(rtcm_file.name),
            form,
            decoder=decoder,
            allow_python_fallback=True,
        )

        if zip_body is not None:
            output_path = args.output
            if output_path is None:
                output_path = Path(f"{rtcm_file.stem}-decode.zip")
            output_path.write_bytes(zip_body)
            DEBUG.log(f"wrote zip={output_path}")
            return 0

        sys.stdout.buffer.write(decode_text)
        sys.stdout.buffer.flush()
        DEBUG.log("decode complete")
        return 0

    except (ValueError, FileNotFoundError, RuntimeError) as err:
        print(format_error_message(f"ERROR: {err}"), file=sys.stderr)
        return 1
    except Exception as err:  # pylint: disable=broad-exception-caught
        print(format_error_message(f"Unexpected error: {err}", include_traceback=True), file=sys.stderr)
        return 1


def send_cgi_status() -> None:
    try:
        lines = [
            "rtcm-pprint.cgi is installed and reachable.",
            "",
            f"Script: {Path(__file__).resolve()}",
            f"CGI bin dir: {cgi_bin_dir()}",
            f"Working directory: {Path.cwd()}",
            f"Python: {sys.version.split()[0]}",
            "",
            "Decoder search order (onefile first, then onedir):",
        ]
        selected = None
        for candidate in decoder_candidates():
            if (
                selected is None
                and candidate.is_file()
                and os.access(candidate, os.X_OK)
            ):
                selected = candidate
            lines.append(
                f"  {candidate} layout={decoder_layout(candidate)} "
                f"exists={candidate.is_file()} executable={os.access(candidate, os.X_OK)}"
            )
        configured = os.environ.get("RTCM_PPRINT")
        if configured:
            lines.append(f"RTCM_PPRINT={configured}")
        if selected is not None:
            lines.extend(
                [
                    "",
                    f"Selected decoder: {selected}",
                    f"Selected layout: {decoder_layout(selected)}",
                ]
            )
        else:
            lines.extend(
                [
                    "",
                    "Selected decoder: NONE",
                    "Place onefile binary rtcm-pprint beside this script, or set RTCM_PPRINT.",
                ]
            )
        if LOG_FILE_USED is not None:
            lines.append(f"Log file: {LOG_FILE_USED}")
        elif CGI_FILE_LOGGING:
            lines.append("Log file: not writable; tried:")
            for path in log_file_candidates():
                lines.append(f"  {path}")
        else:
            lines.append(
                "File logging: disabled "
                "(set RTCM_CGI_DEBUG=1 or RTCM_CGI_LOG to enable)"
            )
        lines.extend(
            [
                "",
                "Submit a POST with multipart/form-data and field name 'file'.",
            ]
        )
        send_text("\n".join(lines) + "\n")
    except Exception as err:  # pylint: disable=broad-exception-caught
        DEBUG.log(f"status page error={err}")
        send_fatal_cgi(
            format_error_message(
                f"Status page failed: {err}\n",
                include_traceback=True,
            )
        )


def run_cgi() -> None:
    set_cgi_file_logging()
    init_debug(cgi_mode=True)

    method = os.environ.get("REQUEST_METHOD", "GET").upper()
    DEBUG.log(f"request method={method}")
    if method == "GET":
        send_cgi_status()
        DEBUG.log("status page sent")
        return

    if method != "POST":
        send_text(
            format_error_message(
                "Use GET for a status page or POST an RTCM file using "
                "multipart/form-data with field name 'file'.\n"
            ),
            status=405,
        )
        return

    content_type = os.environ.get("CONTENT_TYPE", "")
    DEBUG.log(f"content type={content_type!r}")
    if "multipart/form-data" not in content_type.lower():
        send_text(
            format_error_message(
                "Expected Content-Type: multipart/form-data with an uploaded file field named 'file'.\n"
            ),
            status=400,
        )
        return

    try:
        body = read_request_body()
        form = parse_multipart_form(body, content_type)
        set_cgi_file_logging(form)
        if debug_enabled(form):
            DEBUG.enabled = True
        summarize_form(form)

        upload_data, upload_name = parse_upload(form)
        DEBUG.log(f"upload name={upload_name!r} size={len(upload_data)}")

        decode_text, zip_body, archive_name = decode_upload(
            upload_data,
            upload_name,
            form,
            allow_python_fallback=False,
        )

        DEBUG.log("decode complete")
        if zip_body is not None and archive_name is not None:
            DEBUG.log(f"returning zip={archive_name!r} size={len(zip_body)}")
            send_response(
                zip_body,
                content_type="application/zip",
                disposition=f'attachment; filename="{archive_name}"',
            )
            return

        DEBUG.log(f"returning plain text size={len(decode_text)}")
        if not decode_text and not form_flag(form, "summaryOnly"):
            send_text(
                format_error_message(
                    "Decode completed but produced no output.\n"
                ),
                status=500,
            )
            return
        send_response(decode_text, content_type="text/plain; charset=utf-8")

    except ValueError as err:
        DEBUG.log(f"value error={err}")
        send_text(format_error_message(f"{err}\n"), status=400)
    except FileNotFoundError as err:
        DEBUG.log(f"file not found={err}")
        send_text(format_error_message(f"{err}\n"), status=500)
    except RuntimeError as err:
        DEBUG.log(f"runtime error={err}")
        send_text(format_error_message(f"Decode failed:\n\n{err}\n"), status=500)
    except Exception as err:  # pylint: disable=broad-exception-caught
        DEBUG.log(f"unexpected error={err}")
        send_text(
            format_error_message(f"Unexpected error: {err}\n", include_traceback=True),
            status=500,
        )


def main() -> None:
    set_cgi_file_logging()
    bootstrap_cgi_log(
        f"cgi entry python={sys.version.split()[0]} executable={sys.executable}"
    )

    if sys.version_info < (3, 10):
        message = (
            f"Python 3.10+ required; this interpreter is {sys.version.split()[0]}.\n"
        )
        if is_cgi():
            send_fatal_cgi(message)
        else:
            print(f"ERROR: {message}", file=sys.stderr)
        raise SystemExit(1)

    if "--file" in sys.argv:
        raise SystemExit(run_local())

    if not is_cgi():
        local_arg_parser().print_help()
        print(
            "\nLocal test example:\n"
            "  python3 rtcm-pprint.cgi --file samples/R750_626_MSM7.bin\n"
            "  python3 rtcm-pprint.cgi --file samples/R750_626_MSM7.bin --cgi-debug\n",
            file=sys.stderr,
        )
        raise SystemExit(2)

    try:
        run_cgi()
    except Exception as err:  # pylint: disable=broad-exception-caught
        try:
            if not DEBUG.lines:
                init_debug(cgi_mode=True)
            DEBUG.log(f"fatal error={err}")
            send_text(
                format_error_message(f"Fatal CGI error: {err}\n", include_traceback=True),
                status=500,
            )
        except Exception as fatal:  # pylint: disable=broad-exception-caught
            send_fatal_cgi(f"Fatal CGI error: {err}\n\nSecondary failure: {fatal}\n")


if __name__ == "__main__":
    try:
        main()
    except BaseException as err:  # pylint: disable=broad-exception-caught
        set_cgi_file_logging()
        bootstrap_cgi_log(f"uncaught {type(err).__name__}: {err}")
        if is_cgi():
            try:
                send_fatal_cgi(
                    f"Fatal CGI error: {err}\n\n{traceback.format_exc()}\n"
                )
            except Exception:
                pass
        raise
