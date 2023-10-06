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



#from pprint import pprint
#import os
import sys
import argparse
from collections import defaultdict

from pyrtcm import RTCMReader, __version__ as pyrtcmVersion

from pyrtcm.rtcmtypes_core import RTCM_MSGIDS

from pyrtcm.rtcmhelpers import tow2utc

from rtcmextrahelpers import glonass2tow, glonasstow2utc, beidoutow2utc





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

    print(f"\nERROR: {err}\n")


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
        stream, errorhandler=errorhandler, quitonerror=quitonerror, validate=validate, scaling=True
    )
    for (_, parsed_data) in ubr.iterate(
        errorhandler=errorhandler, quitonerror=quitonerror
    ):
        msg_count += 1

        if debug:
#            pprint (parsed_data)
            print (parsed_data)
#            pprint (parsed_data._get_dict())


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
            print ("ID: {} (Unknown)" , msg_id)


#        print (parsed_data)

        try:
            if 1081 <=  msg_id <= 1087 :
                print ("   Epoch Time: {:0.3f}".format(\
                    glonass2tow(parsed_data.GNSSEpoch)/1000))
                print ("   UTC   Time: {}".format(\
                    glonasstow2utc(glonass2tow(parsed_data.GNSSEpoch)).strftime("%H:%M:%S")))
            elif 1121 <=  msg_id <= 1127 :
                print ("   Epoch Time: {:0.3f}".format(\
                    parsed_data.GNSSEpoch/1000))
                print ("   UTC   Time: {}".format(\
                    beidoutow2utc(parsed_data.GNSSEpoch).strftime("%H:%M:%S")))
            else:
                print ("   Epoch Time: {:0.3f}".format(\
                    parsed_data.GNSSEpoch/1000))
                print ("   UTC   Time: {}".format(\
                    tow2utc(parsed_data.GNSSEpoch).strftime("%H:%M:%S")))
        except:
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
                    msg_id,message_counts[id], RTCM_MSGIDS[str(msg_id)]))
            else:
                print ("{:<4} : {:>6} : **Undecoded** Unknown" .format(\
                    msg_id, message_counts[msg_id]))
    print(f"\n{msg_count} messages read. {print_msg_count} printed\n")

VERSION=0.1


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
    parser = parser.parse_args()
    return vars(parser)


def main():

    """
    rtcmdump pretty print a RTCM V3 stream
    """

    args=get_args()
#    pprint(args)

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
