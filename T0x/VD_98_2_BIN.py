#! /usr/bin/env python3

import csv
import argparse


def get_args():
    """
    Creates the command line arguments, parses and returns values
        :param int quitonerror: (kwarg) 0 = ignore,  1 = log and continue, 2 = (re)raise (1)
        :param int validate: (kwarg) 0 = ignore invalid checksum, 1 = validate checksum (1)
        :param bool scaling: (kwarg) apply attribute scaling True/False (True)
        :param bool labelmsm: (kwarg) whether to label MSM NSAT and NCELL attributes (True)
    """



    parser = argparse.ArgumentParser(fromfile_prefix_chars="@",\
        description='ViewData Type 98 -x Records to Binary.', \
        formatter_class=argparse.ArgumentDefaultsHelpFormatter\
        )

    parser.add_argument("ViewDataFile", type=argparse.FileType('r'), \
        help="ViewDat File to display info on",)

    parser.add_argument("RTCMFile", type=argparse.FileType('wb'), \
        help="Binary File with RTCM Data",)

    parser = parser.parse_args()
    return vars(parser)





def main():

    """
    Convert ViewData Type 98 -x Records to Binary
    """

    args=get_args()
#    pprint(args)

    csv_reader = csv.reader(args["ViewDataFile"])

    # Loop through each row in the CSV file
    for row in csv_reader:
        if len(row) == 0:
            continue
        if row[0] != '130':
            continue
        binary_data = [int(number) for number in row[4:]]
        args["RTCMFile"].write(bytes(binary_data))





if __name__ == '__main__':
    main()
