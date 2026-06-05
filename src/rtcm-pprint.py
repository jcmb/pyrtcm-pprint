#! /usr/bin/env python3

"""
rtcm-pprint.py

This application displays the RTCM stream in a human readable form.

RTCMMessage binary logfile reader using the
RTCMReader iterator functions and an external error handler.

Created on 11 Feb 2023

:author: jcmb
:copyright: Geoffrey Kirk
:license: GPL V3
"""



import sys
import argparse
import os
from collections import defaultdict

try:
    from pyrtcm import RTCMReader, __version__ as pyrtcmVersion
    from pyrtcm.rtcmhelpers import tow2utc
    from pyrtcm.rtcmtypes_core import GNSSMAP, RTCM_MSGIDS
except ModuleNotFoundError as err:
    if err.name != "pyrtcm":
        raise
    print(
        "Missing dependency: pyrtcm\n\n"
        "Install it into the same Python environment you use to run rtcm-pprint:\n"
        "  python -m pip install pyrtcm==1.1.12\n\n"
        "If you use a virtual environment, activate it first:\n"
        "  python3 -m venv .venv\n"
        "  source .venv/bin/activate\n"
        "  python -m pip install pyrtcm==1.1.12\n",
        file=sys.stderr,
    )
    sys.exit(1)


from rtcmextrahelpers import glonasstow2utc, beidoutow2utc

from pprint import pprint


from rtcmprint import print_record , OUTPUT_FUNCTIONS



def  count_set_bits(value):
    """
    Function to get no of set bits in binary
    representation of positive integer n
    """

    count = 0
    while value:
        count += value & 1
        value >>= 1
    return count

def errhandler(err):
    """
    Handles errors output by iterator.
    """

    print(f"\nERROR: {err}")


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


def read(stream, errorhandler, quitonerror, validate,
    metadata_only,\
    obs_summary=False,\
    summary_only=False,\
    debug=False,\
    single_record=False):
    """
    Reads and parses RTCM message data from stream.
    """

    msg_count = 0
    print_msg_count = 0
    message_counts=defaultdict(int)

    ubr = RTCMReader(
        stream, errorhandler=errorhandler, quitonerror=quitonerror, validate=validate
    )

    for (raw_data, parsed_data) in ubr:
        msg_count += 1

        if debug:
#            pprint (parsed_data)
            print (parsed_data)
#            pprint (parsed_data._get_dict())

#        pprint(parsed_data)
#        pprint(raw_data)
        if raw_data == None :
#            if quitonerror!=1:
#                print(parsed_data)
            continue

        msg_id = int(parsed_data.identity)

        message_counts[msg_id]+=1

        if single_record:
            if  message_counts[msg_id] > 1:
                continue

        if summary_only:
            continue


        if metadata_only:
            if 1070 <= msg_id <= 1229 : # MSM
                continue
            if 1001 <= msg_id <= 1004 : # GPS
                continue
            if 1009  <= msg_id <= 1012 : # GLONASS
                continue

        if parsed_data.identity in RTCM_MSGIDS:
            print (f"ID: {msg_id} ({RTCM_MSGIDS[parsed_data.identity]})" )
        else:
            print (f"ID: {msg_id} (Unknown)")


#        print (parsed_data)

        try:
            epoch_tow = msm_epoch_tow(parsed_data)
            print ("   Epoch Time: {:0.3f}".format(epoch_tow / 1000))
            if 1081 <= msg_id <= 1087:
                utc_time = glonasstow2utc(epoch_tow)
            elif 1121 <= msg_id <= 1127:
                utc_time = beidoutow2utc(epoch_tow)
            else:
                utc_time = tow2utc(epoch_tow)
            print ("   UTC   Time: {}".format(utc_time.strftime("%H:%M:%S")))
        except (AttributeError, KeyError):
            pass

        print_record(parsed_data,sys.stdout,obs_summary)

        print_msg_count +=1


    print("Message Type Count")
    for msg_id in sorted (message_counts):
        if msg_id in OUTPUT_FUNCTIONS:
            if str(msg_id) in RTCM_MSGIDS:
                print ("{:<4} : {:>6} : {}" .format (\
                    msg_id,message_counts[msg_id], RTCM_MSGIDS[str(msg_id)]))
            else:
                print ("{:<4} : {:>6} : Unknown" .format(\
                    msg_id, message_counts[msg_id]))
        else:
            if str(msg_id) in RTCM_MSGIDS:
                print ("{:<4} : {:>6} : **Undecoded** {}" .format (\
                    msg_id,message_counts[msg_id], RTCM_MSGIDS[str(msg_id)]))
            else:
                print ("{:<4} : {:>6} : **Undecoded** Unknown" .format(\
                    msg_id, message_counts[msg_id]))
    print(f"\n{msg_count} messages read. {print_msg_count} printed\n")

VERSION=1.2.1


def get_args():
    """
    Creates the command line arguments, parses and returns values
        :param int quitonerror: (kwarg) 0 = ignore,  1 = log and continue, 2 = (re)raise (1)
        :param int validate: (kwarg) 0 = ignore invalid checksum, 1 = validate checksum (1)
        :param bool scaling: (kwarg) apply attribute scaling True/False (True)
        :param bool labelmsm: (kwarg) whether to label MSM NSAT and NCELL attributes (True)
    """



    parser = argparse.ArgumentParser(fromfile_prefix_chars="@",\
        description='RTCM V3 Pretty Printer.', \
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
        epilog="Version: {} pyrtcm: {}".format(VERSION,pyrtcmVersion)
        )

    parser.add_argument("--RTCMFile", type=argparse.FileType('rb'),default=sys.stdin.buffer, \
        help="RTCM File to display info on",)


    parser.add_argument("--quitonerror", type=int, choices=[0, 1, 2], default=2, \
        help="0 = ignore,  1 = log and continue, 2 = (re)raise",)
    parser.add_argument("--validate", type=int, choices=[0, 1], default=1, \
        help="0 = ignore invalid checksum, 1 = validate checksum",)
    parser.add_argument("--metadataOnly", action="store_true", \
        help="Display only Meta Data records")
    parser.add_argument("--obsSummary", action="store_true", \
        help="Display only Observation Summary")
    parser.add_argument("--summaryOnly", action="store_true", \
        help="Display only the summary of the records")
    parser.add_argument("--singleRecord", action="store_true", \
        help="Display only first record of each type")
    parser.add_argument("--debug", action="store_true", \
        help="Display low level information.")
    parser.add_argument("--tui", action="store_true", \
        help="Display an interactive terminal dashboard instead of streaming decoded output.")
    parser = parser.parse_args()
    return vars(parser)


def is_stdin_stream(stream):
    """
    Return True when the RTCM input stream is stdin.
    """

    return stream is sys.stdin.buffer or getattr(stream, "name", None) == "<stdin>"


def prepare_tui_terminal_input(rtcm_stream):
    """
    Give Textual a terminal stdin while preserving binary RTCM stdin.
    """

    if not is_stdin_stream(rtcm_stream) or sys.stdin.isatty():
        return None

    terminal_name = "CONIN$" if os.name == "nt" else "/dev/tty"
    try:
        terminal = open(
            terminal_name,
            "r",
            encoding=sys.stdin.encoding or "utf-8",
            errors="replace",
        )
    except OSError as err:
        print(
            "The --tui dashboard can read RTCM data from stdin, but it also needs "
            "a terminal for keyboard input.\n\n"
            f"Could not open {terminal_name}: {err}\n\n"
            "Run --tui from an interactive terminal, or use --RTCMFile with a file. "
            "For plain piped output without a dashboard, run without --tui.",
            file=sys.stderr,
        )
        sys.exit(2)

    original_stdin = sys.stdin
    original_dunder_stdin = sys.__stdin__
    sys.stdin = terminal
    sys.__stdin__ = terminal
    return terminal, original_stdin, original_dunder_stdin


def configure_stdout_buffering() -> None:
    """
    Stream decoded output line-by-line when stdout is a pipe (e.g. CGI).
    """

    if not hasattr(sys.stdout, "reconfigure"):
        return
    try:
        sys.stdout.reconfigure(line_buffering=True, write_through=True)
    except (AttributeError, OSError, ValueError):
        pass


def main():

    """
    rtcmdump pretty print a RTCM V3 stream
    """

    args=get_args()
#    pprint(args)

    if args["tui"]:
        tui_input = prepare_tui_terminal_input(args["RTCMFile"])
        print("\nProcessing file {}...\n".format(args["RTCMFile"].name),file=sys.stderr)
        from rtcmtui import run_tui

        try:
            run_tui(
                args["RTCMFile"],
                quitonerror=args["quitonerror"],
                validate=args["validate"],
                metadata_only=args["metadataOnly"],
                obs_summary=args["obsSummary"],
                summary_only=args["summaryOnly"],
                debug=args["debug"],
                single_record=args["singleRecord"],
            )
        finally:
            if tui_input is not None:
                terminal, original_stdin, original_dunder_stdin = tui_input
                sys.stdin = original_stdin
                sys.__stdin__ = original_dunder_stdin
                terminal.close()
    else:
        configure_stdout_buffering()
        print("\nProcessing file {}...\n".format(args["RTCMFile"].name),file=sys.stderr)
        read(args["RTCMFile"],
            errhandler,\
            args["quitonerror"],\
            args["validate"],\
            args["metadataOnly"],\
            args["obsSummary"],\
            args["summaryOnly"],\
            args["debug"],\
            args["singleRecord"],\

            )





if __name__ == '__main__':
    main()
