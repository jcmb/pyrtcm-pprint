#! /usr/bin/env python3

import sys

from pprint import pprint

from pyrtcm import RTCM_DATA_FIELDS, RTCM_MSGIDS , GPS_SIG_MAP , GLONASS_SIG_MAP, QZSS_SIG_MAP, GALILEO_SIG_MAP, BEIDOU_SIG_MAP, datasiz, datascale, datadesc,sat2prn, cell2prn, id2prnsigmap
from pyrtcm.rtcmreader import RTCMReader


GPS_SIG_NAME = {
    1: "Reserved",
    2: "L1 C/A",
    3: "L1 P",
    4: "L1 E",
    5: "Reserved",
    6: "Reserved",
    7: "Reserved",
    8: "L2 C/A",
    9: "L2 P",
    10: "L2 E",
    11: "Reserved",
    12: "Reserved",
    13: "Reserved",
    14: "Reserved",
    15: "L2 C(M)",
    16: "L2 C(L)",
    17: "L2 C(M+L)",
    18: "Reserved",
    19: "Reserved",
    20: "Reserved",
    21: "Reserved",
    22: "L5 I",
    23: "L5 Q",
    24: "L5 I+Q",
    25: "Reserved",
    26: "Reserved",
    27: "Reserved",
    28: "Reserved",
    29: "Reserved",
    30: "L1C-D",
    31: "L1C-P",
    32: "L1C-(D+P)",
}

QZSS_SIG_NAME = {
    1: "Reserved",
    2: "L1 C/A",
    3: "Reserved",
    4: "Reserved",
    5: "Reserved",
    6: "Reserved",
    7: "Reserved",
    8: "Reserved",
    9: "LEX S",
    10: "LEX L",
    11: "LEX S+L",
    12: "Reserved",
    13: "Reserved",
    14: "Reserved",
    15: "L2 C(M)",
    16: "L2 C(L)",
    17: "L2 C(M+L)",
    18: "Reserved",
    19: "Reserved",
    20: "Reserved",
    21: "Reserved",
    22: "L5 I",
    23: "L5 Q",
    24: "L5 I+Q",
    25: "Reserved",
    26: "Reserved",
    27: "Reserved",
    28: "Reserved",
    29: "Reserved",
    30: "L1C-D",
    31: "L1C-P",
    32: "L1C-(D+P)",
}


GLONASS_SIG_NAME = {
    1: "Reserved",
    2: "G1 C/A",
    3: "G1 P",
    4: "Reserved",
    5: "Reserved",
    6: "Reserved",
    7: "Reserved",
    8: "G2 C/A",
    9: "G2 P",
    10: "Reserved",
    11: "Reserved",
    12: "Reserved",
    13: "Reserved",
    14: "Reserved",
    15: "Reserved",
    16: "Reserved",
    17: "Reserved",
    18: "Reserved",
    19: "Reserved",
    20: "Reserved",
    21: "Reserved",
    22: "Reserved",
    23: "Reserved",
    24: "Reserved",
    25: "Reserved",
    26: "Reserved",
    27: "Reserved",
    28: "Reserved",
    29: "Reserved",
    30: "Reserved",
    31: "Reserved",
    32: "Reserved",
}


GALILEO_SIG_NAME = {
    1: "Reserved",
    2: "E1 C",
    3: "E1 A",
    4: "E1 B",
    5: "E1 B+C",
    6: "E1 A+B+C",
    7: "Reserved",
    8: "E6 C",
    9: "E6 A",
    10: "E6 B",
    11: "E6 A+B",
    12: "E6 A+B+C",
    13: "Reserved",
    14: "E5B I",
    15: "E5B Q",
    16: "E5B I+Q",
    17: "Reserved",
    18: "E5(A+B) I",
    19: "E5(A+B) Q",
    20: "E5(A+B) I+Q",
    21: "Reserved",
    22: "E5A I",
    23: "E5A Q",
    24: "E5A I+Q",
    25: "Reserved",
    26: "Reserved",
    27: "Reserved",
    28: "Reserved",
    29: "Reserved",
    30: "L1C-D",
    31: "L1C-P",
    32: "L1C-(D+P)",
}

BEIDOU_SIG_NAME = {
    1: "Reserved",
    2: "B1 I",
    3: "B1 Q",
    4: "B1 I+Q",
    5: "Reserved",
    6: "Reserved",
    7: "Reserved",
    8: "B3 I",
    9: "B3 Q",
    10: "B3 I+Q",
    11: "Reserved",
    12: "Reserved",
    13: "Reserved",
    14: "B2 I",
    15: "B2 I",
    16: "B2 I+Q",
    17: "Reserved",
    18: "Reserved",
    19: "Reserved",
    20: "Reserved",
    21: "Reserved",
    22: "B2a D",
    23: "B2a P",
    24: "B2a D+P",
    25: "B2b I",
    26: "Reserved",
    27: "Reserved",
    28: "Reserved",
    29: "Reserved",
    30: "B1C-D",
    31: "B1C-P",
    32: "B1C-(D+P)",
}

MSM_SIGNAL_NAMES={
    1071:GPS_SIG_NAME,
    1072:GPS_SIG_NAME,
    1073:GPS_SIG_NAME,
    1074:GPS_SIG_NAME,
    1075:GPS_SIG_NAME,
    1076:GPS_SIG_NAME,
    1077:GPS_SIG_NAME,

    1081:GLONASS_SIG_NAME,
    1082:GLONASS_SIG_NAME,
    1083:GLONASS_SIG_NAME,
    1084:GLONASS_SIG_NAME,
    1085:GLONASS_SIG_NAME,
    1086:GLONASS_SIG_NAME,
    1087:GLONASS_SIG_NAME,


    1091:GALILEO_SIG_NAME,
    1092:GALILEO_SIG_NAME,
    1093:GALILEO_SIG_NAME,
    1094:GALILEO_SIG_NAME,
    1095:GALILEO_SIG_NAME,
    1096:GALILEO_SIG_NAME,
    1097:GALILEO_SIG_NAME,

    1111:BEIDOU_SIG_NAME,
    1112:BEIDOU_SIG_NAME,
    1113:BEIDOU_SIG_NAME,
    1114:BEIDOU_SIG_NAME,
    1115:BEIDOU_SIG_NAME,
    1116:BEIDOU_SIG_NAME,
    1117:BEIDOU_SIG_NAME,

    1121:BEIDOU_SIG_NAME,
    1122:BEIDOU_SIG_NAME,
    1123:BEIDOU_SIG_NAME,
    1124:BEIDOU_SIG_NAME,
    1125:BEIDOU_SIG_NAME,
    1126:BEIDOU_SIG_NAME,
    1127:BEIDOU_SIG_NAME

    }


MSM_SIGNAL_MAPS={
    1071:GPS_SIG_MAP,
    1072:GPS_SIG_MAP,
    1073:GPS_SIG_MAP,
    1074:GPS_SIG_MAP,
    1075:GPS_SIG_MAP,
    1076:GPS_SIG_MAP,
    1077:GPS_SIG_MAP,

    1081:GLONASS_SIG_MAP,
    1082:GLONASS_SIG_MAP,
    1083:GLONASS_SIG_MAP,
    1084:GLONASS_SIG_MAP,
    1085:GLONASS_SIG_MAP,
    1086:GLONASS_SIG_MAP,
    1087:GLONASS_SIG_MAP,

    1091:GALILEO_SIG_MAP,
    1092:GALILEO_SIG_MAP,
    1093:GALILEO_SIG_MAP,
    1094:GALILEO_SIG_MAP,
    1095:GALILEO_SIG_MAP,
    1096:GALILEO_SIG_MAP,
    1097:GALILEO_SIG_MAP,

    1111:QZSS_SIG_MAP,
    1112:QZSS_SIG_MAP,
    1113:QZSS_SIG_MAP,
    1114:QZSS_SIG_MAP,
    1115:QZSS_SIG_MAP,
    1116:QZSS_SIG_MAP,
    1117:QZSS_SIG_MAP,

    1121:BEIDOU_SIG_MAP,
    1122:BEIDOU_SIG_MAP,
    1123:BEIDOU_SIG_MAP,
    1124:BEIDOU_SIG_MAP,
    1125:BEIDOU_SIG_MAP,
    1126:BEIDOU_SIG_MAP,
    1127:BEIDOU_SIG_MAP
}


def multiStr(message,id):
    result=""
    base_id=f"DF{id:03}"
    secondary_id=f"DF{id+1:03}"

    try:
        length=int(getattr(message, base_id))
    except:
        length=0

    secondary_id=f"DF{id+1:03}"
    for i in range(length):
#                    print(i)

        result += getattr(message, f"{secondary_id}_{i+1:02}")

#    print(datadesc(base_id))
    return("   " + base_id + ": " + datadesc(base_id) + ": " + str(length) + "\n"  + \
           "   "  + secondary_id + ": " + datadesc(secondary_id) + ": " + result)

def standardStr(message,id):
    base_id=f"DF{id:03}"
    try:
        value=getattr(message, base_id)
    except:
        value=""
#    print(datadesc(base_id))
    return("   " + str(base_id) + ": " + datadesc(base_id) + ": " + str(value))

def standardNumber(message,id):
    base_id=f"DF{id:03}"
    try:
        value=format("{: }".format(getattr(message, base_id)))
    except:
        value=""
#    print(datadesc(base_id))
    return("   " + str(base_id) + ": " + datadesc(base_id) + ": " + value)

def standardBoolean(message,id):
    base_id=f"DF{id:03}"
    try:
        if getattr(message, base_id) == 0 :
            value="False"
        elif getattr(message, base_id) == 1 :
            value="False"
        else:
            value="Unknown"

    except:
        value="N/A"

#    print(datadesc(base_id))
    return("   " + str(base_id) + ": " + datadesc(base_id) + ": " + str(value))


def output_1006(message,outfile,obsSummary=None):

    def standard141(message,id=141):
        base_id=f"DF{id:03}"
        try:
            if getattr(message, base_id) == 0 :
                value="Physical Base"
            elif getattr(message, base_id) == 1 :
                value="Non Physical Base"
            else:
                value="Unknown"
        except:
            value="N/A"
        return("   " + str(base_id) + ": " + datadesc(base_id) + ": " + str(value))

    def standard142(message,id=142):
        base_id=f"DF{id:03}"
        try:
            if getattr(message, base_id) == 0 :
                value="Measurements At different intervals"
            elif getattr(message, base_id) == 1 :
                value="Measurements at same interval"
            else:
                value="Unknown"
        except:
            value="N/A"
        return("   " + str(base_id) + ": " + datadesc(base_id) + ": " + str(value))



    if message.identity != "1006":
        return(False)


#    print(message.identity  + ": " + RTCM_MSGIDS[message.identity],file=outfile)
    print(standardNumber(message,3),file=outfile)

    print(standardNumber(message,21),file=outfile)
    print(standardBoolean(message,22),file=outfile)
    print(standardBoolean(message,23),file=outfile)
    print(standardBoolean(message,24),file=outfile)
    print(standardNumber(message,25),file=outfile)
    print(standardNumber(message,26),file=outfile)
    print(standardNumber(message,27),file=outfile)
    print(standardNumber(message,28),file=outfile)
    print(standard141(message),file=outfile)
    print(standard142(message),file=outfile)
    print(standardNumber(message,364),file=outfile)
    return(True)

def output_1008(message,outfile,obsSummary=None):
    if message.identity != "1008":
        return(False)


#    print(message.identity  + ": " + RTCM_MSGIDS[message.identity],file=outfile)
    print(standardNumber(message,3),file=outfile)

    print(multiStr(message,29),file=outfile)
    print(standardNumber(message,31),file=outfile)
    print(multiStr(message,32),file=outfile)

    return(True)


def output_1013(message,outfile,obsSummary=None):

    def messageIDs(message,id=53):
        result=standardNumber(message,53)

        result+= "\n      Message: {:4}: {:4}: {:4}".format("ID","Sync","Rate")

        base_id=f"DF{id:03}"

        try:
            number=int(getattr(message, base_id))
        except:
            number=0

        DF_message_id="DF055"
        DF_message_sync="DF056"
        DF_message_interval="DF057"
        for i in range(number):
            message_id=getattr(message, f"{DF_message_id}_{i+1:02}")
            message_sync=getattr(message, f"{DF_message_sync}_{i+1:02}")
            if message_sync == 1:
                message_sync_text="Sync"
            else:
                message_sync_text="Async"

            message_interval=getattr(message, f"{DF_message_interval}_{i+1:02}")
            result += "\n      Message: {:4}: {:5}: {:4}".format(message_id,message_sync_text,message_interval)


    #    print(datadesc(base_id))
        return(result)


    if message.identity != "1013":
        return(False)

#    print(message.identity  + ": " + RTCM_MSGIDS[message.identity],file=outfile)
    print(standardNumber(message,3),file=outfile)

    print(standardNumber(message,51),file=outfile)
    print(standardNumber(message,52),file=outfile)
    print(standardNumber(message,54),file=outfile)
    print(messageIDs(message))

    return(True)



def output_1033(message,outfile,obsSummary=None):
    if message.identity != "1033":
        return(False)

#    print(message.identity  + ": " + RTCM_MSGIDS[message.identity],file=outfile)
    print(standardNumber(message,3),file=outfile)

    print(standardNumber(message,31),file=outfile)
    print(multiStr(message,29),file=outfile)
    print(multiStr(message,32),file=outfile)
    print(multiStr(message,227),file=outfile)
    print(multiStr(message,229),file=outfile)
    print(multiStr(message,231),file=outfile)
    return(True)

def output_MSM(message,outfile,obsSummary=False):

    def MSMRough(nSat, message,outfile,id=398):
        base_id=f"DF{id:03}"
#        pprint(message.DF398_05)
        SV_Map=sat2prn(message)
        Signal_Map=cell2prn(message)

#        pprint(Signal_Map)
        result=str(base_id) + ": " + datadesc(base_id)

        result+="\n   {:3} {}\n".format("SV","Range")


        for SV in range(nSat):
            Range=getattr(message, f"{base_id}_{SV+1:02}")
            result+="   {:3} {}\n".format(SV_Map[SV+1], Range)

        print(result,file=outfile)
        return(None)

    def MSMSvLock(nSat,nSignals, message, messageId,subtypeId,outfile):

        SubDF=f"DF{subtypeId}"
        print("{} {}".format(SubDF,datadesc(SubDF)),file=outfile)

        SV_Map=sat2prn(message)

        Band_Index=0
        Header="   {:>3} ".format("SV")

        Signals=message.DF395
#       SV=1

        for Signal in range(1,33):
            Signal_Bit=1 << (32-Signal)
            if (Signals & Signal_Bit) != 0:
                SigName="{:}-({:})".format(MSM_SIGNAL_NAMES[messageId][Signal],MSM_SIGNAL_MAPS[messageId][Signal])
                Header+="{:<16} ".format(SigName)
        print(Header,file=outfile)


        SVMap=sat2prn(message)
        signalMap=cell2prn(message)
#        pprint(signalMap)
        signals=int(getattr(message, "DF396"))
        signal_bit=1 << ((nSat*nSignals)-1)
        attributeIndex=1
        for SV in range(1,nSat+1):
            line="   {:3} ".format(SVMap[SV])
            for signal in range(1,nSignals+1):
                if signal_bit & signals:
                    indicator=int(getattr(message, f"{SubDF}_{attributeIndex:02}"))
#                    print ("indicator", indicator)
                    if indicator == 0:
                        Locktime="{:<16}" .format("Slip")
                    elif indicator == 15:
                        Locktime="{:<16} ".format("Max")
                    else:
                        min_ms=2 ** (indicator+4)
                        Locktime="{:< 16.3f} ".format(min_ms/1000)
                    line+=Locktime
                    attributeIndex+=1
                else:
                    line+="{:<16} ".format("")
                signal_bit=signal_bit>>1



            print(line,file=outfile)
        print("",file=outfile)

    #    print(datadesc(base_id))
        return(None)


    def MSM7SvLock(nSat,nSignals, message, messageId,subtypeId,outfile):

        SubDF=f"DF{subtypeId}"
        print("{} {}".format(SubDF,datadesc(SubDF)),file=outfile)

        SV_Map=sat2prn(message)

        Band_Index=0
        Header="   {:>3} ".format("SV")

        Signals=message.DF395

        for Signal in range(1,33):
            Signal_Bit=1 << (32-Signal)
            if (Signals & Signal_Bit) != 0:
                SigName="{:}-({:})".format(MSM_SIGNAL_NAMES[messageId][Signal],MSM_SIGNAL_MAPS[messageId][Signal])
                Header+="{:<16} ".format(SigName)
        print(Header,file=outfile)


        SVMap=sat2prn(message)
        signalMap=cell2prn(message)
        signals=int(getattr(message, "DF396"))
        signal_bit=1 << ((nSat*nSignals)-1)

        attributeIndex=1
        for SV in range(1,nSat+1):
            line="   {:3} ".format(SVMap[SV])
            for signal in range(1,nSignals+1):
                if signal_bit & signals:
                    indicator=int(getattr(message, f"{SubDF}_{attributeIndex:02}"))
                    if indicator == 0:
                        Locktime="{:<16}" .format("Slip")
                    elif indicator > 0 and indicator < 704:
                        Locktime="{:<16.0f} ".format(indicator)
                    elif indicator == 704:
                        Locktime="{:<16} ".format("Max")
                    else:
                        Locktime="{:<16} ".format("Reserved")
                    line+=Locktime
                    attributeIndex+=1
                else:
                    line+="{:<16} ".format("")
                signal_bit=signal_bit>>1



            print(line,file=outfile)
        print("",file=outfile)

    #    print(datadesc(base_id))
        return(None)


    def MSMSvHalfCycle (nSat,nSignals, message, messageId,subtypeId,outfile):

        SubDF=f"DF{subtypeId}"
        print("{} {}".format(SubDF,datadesc(SubDF)),file=outfile)

        SV_Map=sat2prn(message)

        Band_Index=0
        Header="   {:>3} ".format("SV")

        Signals=message.DF395
#       SV=1

        for Signal in range(1,33):
            Signal_Bit=1 << (32-Signal)
            if (Signals & Signal_Bit) != 0:
                SigName="{:}-({:})".format(MSM_SIGNAL_NAMES[messageId][Signal],MSM_SIGNAL_MAPS[messageId][Signal])
                Header+="{:<16} ".format(SigName)
        print(Header,file=outfile)



        for SV in range(1,nSat+1):
            line="   {:3} ".format(SV_Map[SV])
            for Signal in range(1,nSignals+1):
                Band_Index+=1


        SVMap=sat2prn(message)
        signalMap=cell2prn(message)
        signals=int(getattr(message, "DF396"))
        signal_bit=1 << ((nSat*nSignals)-1)

        attributeIndex=1
        for SV in range(1,nSat+1):
            line="   {:3} ".format(SVMap[SV])
            for signal in range(1,nSignals+1):
                if signal_bit & signals:
                    indicator=int(getattr(message, f"{SubDF}_{attributeIndex:02}"))
                    if indicator == 0:
                        Cycle="{:<16} " .format("None")
                    else:
                        Cycle="{:<16} " .format("Half")

                    line+=Cycle
                    attributeIndex+=1
                else:
                    line+="{:<16} ".format("")

                signal_bit=signal_bit>>1


            print(line,file=outfile)

    #    print(datadesc(base_id))
        print("",file=outfile)
        return(None)


    def MSMCNRs(nSat,nSignals, message, messageId,subtypeId,outfile):

        SubDF=f"DF{subtypeId}"
        print("{} {}".format(SubDF,datadesc(SubDF)),file=outfile)
        Header="   {:>3} ".format("SV")
        Signals=message.DF395



        for Signal in range(1,33):
            Signal_Bit=1 << (32-Signal)
            if Signal_Bit & Signal:
                SigName="{:}-({:})".format(MSM_SIGNAL_NAMES[messageId][Signal],MSM_SIGNAL_MAPS[messageId][Signal])
                Header+="{:<16} ".format(SigName)
        print(Header,file=outfile)


        SVMap=sat2prn(message)
        signalMap=cell2prn(message)

        signals=int(getattr(message, "DF396"))
        signal_bit=1 << ((nSat*nSignals)-1)
        attributeIndex=1
        for SV in range(1,nSat+1):
            line="   {:3} ".format(SVMap[SV])
            for signal in range(1,nSignals+1):
                if signal_bit & signals:
                    line+="{:< 16.4f} ".format(getattr(message, f"{SubDF}_{attributeIndex:02}"))
                    attributeIndex+=1
                else:
                    line+="{:<16} ".format("")
                signal_bit=signal_bit>>1


            print(line,file=outfile)
        print("",file=outfile)
        return(None)




    def MSMSv(nSat,nSignals, message, messageId,subtypeId,outfile,invalid):

        SubDF=f"DF{subtypeId}"
        print("{} {}".format(SubDF,datadesc(SubDF)),file=outfile)

        Header="   {:>3} ".format("SV")

        Signals=message.DF395
#       SV=1

        for Signal in range(1,33):
            Signal_Bit=1 << (32-Signal)
            if (Signals & Signal_Bit) != 0:
                SigName="{:}-({:})".format(MSM_SIGNAL_NAMES[messageId][Signal],MSM_SIGNAL_MAPS[messageId][Signal])
                Header+="{:<16} ".format(SigName)
        print(Header,file=outfile)


        SVMap=sat2prn(message)
        signalMap=cell2prn(message)

        signals=int(getattr(message, "DF396"))
        signal_bit=1 << ((nSat*nSignals)-1)
        attributeIndex=1

        for SV in range(1,nSat+1):
            line="   {:3} ".format(SVMap[SV])
            for signal in range(1,nSignals+1):
                if signal_bit & signals:
                    value=getattr(message, f"{SubDF}_{attributeIndex:02}")
                    if value == invalid:
                        line+="{:<16} ".format("Invalid")
                    else:
                        line+="{:< 16.8f} ".format(getattr(message, f"{SubDF}_{attributeIndex:02}"))
                    attributeIndex+=1
                else:
                    line+="{:<16} ".format("")

                signal_bit=signal_bit>>1

            print(line,file=outfile)

    #    print(datadesc(base_id))
        print("",file=outfile)

        return(None)

    def standard411(message,id=411):
        base_id=f"DF{id:03}"
        try:
            value = getattr(message, base_id)
            if  value== 0 :
                value="No Clock Steering"
            elif value == 1 :
                value="Clock Steering"
            elif value == 2 :
                value="Unknown Clock Steering"
            elif value == 3 :
                value="Reserved"
            else:
                value="Error"
        except:
            value="N/A"
        return("   " + str(base_id) + ": " + datadesc(base_id) + ": " + str(value))

    def standard412(message,id=412):
        base_id=f"DF{id:03}"
        try:
            value = getattr(message, base_id)
            if  value== 0 :
                value="Internal Clock"
            elif value == 1 :
                value="External Clock, Locked"
            elif value == 2 :
                value="External Clock, Not Locked"
            elif value == 3 :
                value="Unknown"
            else:
                value="Error"
        except:
            value="N/A"
        return("   " + str(base_id) + ": " + datadesc(base_id) + ": " + str(value))


    def standard417(message,id=417):
        base_id=f"DF{id:03}"
        try:
            value = getattr(message, base_id)
            if  value== 0 :
                value="Divergence Free Smoothing"
            elif value == 1 :
                value="Unknown Smoothing"
            else:
                value="Error"
        except:
            value="N/A"
        return("   " + str(base_id) + ": " + datadesc(base_id) + ": " + str(value))


#    print(message)
#    pprint(message._get_dict())
#    pprint(id2prnsigmap(message.identity))


    print(standardNumber(message,3),file=outfile)
    print(standardNumber(message,393),file=outfile)
    print(standardNumber(message,409),file=outfile)
    print(standard411(message,411),file=outfile)
    print(standard412(message,412),file=outfile)
    print(standard417(message,417),file=outfile)
    print(standardNumber(message,418),file=outfile)


    SVs=message.DF394




    if obsSummary:
    #    print("{:016x}".format(SVs))
    #    print("{:064b}".format(SVs))

        Signals=message.DF395
        print("   Observations:",file=outfile)
        Header="   {:>3} ".format("SV")
        for Signal in range(1,33):
            Signal_Bit=1 << (32-Signal)
            if (Signals & Signal_Bit) != 0:
                SigName="{:}-({:})".format(MSM_SIGNAL_NAMES[int(message.identity)][Signal],MSM_SIGNAL_MAPS[int(message.identity)][Signal])
                Header+="{:<16} ".format(SigName)
        print(Header,file=outfile)


#        SV=1
#        for SV in range(1,65):
#            SV_Bit=1 << (64-SV)
#            if (SVs & SV_Bit) != 0:
#                print ("SV: {}".format(SV))

#        print("Signals {:08x}".format(Signals))
#        print("Signals {:032b}".format(Signals))
#        SV=1
#        for Signal in range(1,33):
#            Signal_Bit=1 << (32-Signal)
#            if (Signals & Signal_Bit) != 0:
#                print ("Signal: {:2} : {:2}: {:2}".format(Signal, MSM_SIGNAL_MAPS[int(message.identity)][Signal], MSM_SIGNAL_NAMES[int(message.identity)][Signal]))

        SVMap=sat2prn(message)
        signalMap=cell2prn(message)
        attributeIndex=1
        signals=int(getattr(message, "DF396"))
        signal_bit=1 << ((message.NSat * message.NSig)-1)

        for SV in range(1,message.NSat+1):
            line="   {:3} ".format(SVMap[SV])
            for signal in range(1,message.NSig+1):
                if signal_bit & signals:
                    line+="{:<16} ".format("Present")
                    attributeIndex+=1
                else:
                    line+="{:<16} ".format("")

                signal_bit=signal_bit>>1


            print(line,file=outfile)

    else:
        MSMRough(message.NSat,message,outfile)

        if "groupsig1" in message._get_dict() :

            if 'DF400' in message._get_dict()["groupsig1"][1] :
                MSMSv(message.NSat,message.NSig, message,int(message.identity),400,outfile,-2**10)
            if 'DF405' in message._get_dict()["groupsig1"][1] :
                MSMSv(message.NSat,message.NSig, message,int(message.identity),405,outfile,-2**10)

        if "groupsig2" in message._get_dict() :
            if 'DF401' in message._get_dict()["groupsig2"][1] :
                MSMSv(message.NSat,message.NSig, message,int(message.identity),401,outfile,0.0)
            if 'DF406' in message._get_dict()["groupsig2"][1] :
                MSMSv(message.NSat,message.NSig, message,int(message.identity),406,outfile,0.0)

        if "groupsig3" in message._get_dict() :
            if 'DF402' in message._get_dict()["groupsig3"][1] :
                MSMSvLock(message.NSat,message.NSig,message,int(message.identity),402,outfile)
            if 'DF407' in message._get_dict()["groupsig3"][1] :
                MSM7SvLock(message.NSat,message.NSig,message,int(message.identity),407,outfile)

        if "groupsig4" in message._get_dict() :
            if 'DF420' in message._get_dict()["groupsig4"][1] :
                MSMSvHalfCycle(message.NSat,message.NSig,message,int(message.identity),420,outfile)

        if "groupsig5" in message._get_dict() :
            if 'DF403' in message._get_dict()["groupsig5"][1] :
                MSMCNRs(message.NSat,message.NSig,message,int(message.identity),403,outfile)
            if 'DF408' in message._get_dict()["groupsig5"][1] :
                MSMCNRs(message.NSat,message.NSig,message,int(message.identity),408,outfile)

        if "groupsig6" in message._get_dict() :
            MSMSv(message.NSat,message.NSig,message,int(message.identity),404,outfile,-1.6384)


def output_1230(message,outfile,obsSummary=None):


    def standard421(message,id=421):
        base_id=f"DF{id:03}"
        try:
            if getattr(message, base_id) == 0 :
                value="Phase and Range at different intervals"
            elif getattr(message, base_id) == 1 :
                value="Phase and Range at same interval"
            else:
                value="Unknown"
        except:
            value="N/A"
        return("   " + str(base_id) + ": " + datadesc(base_id) + ": " + str(value))

    def standard422andSubs(message,outfile,id=422):

        base_id=f"DF{id:03}"
        mask=getattr(message, base_id)

        try:
            value="{:0X} ({:b})".format(mask, mask)
        except:
            value="N/A"

        print("   " + str(base_id) + ": " + datadesc(base_id) + ": " + str(value),file=outfile)

        if mask and 1<<3 :
            print(standardNumber(message,423),file=outfile)

        if mask and 1<<2 :
            print(standardNumber(message,424),file=outfile)

        if mask and 1<<1 :
            print(standardNumber(message,425),file=outfile)

        if mask and 1  :
            print(standardNumber(message,426),file=outfile)


    if message.identity != "1230":
        return(False)

#    print(message)
#    pprint(message._get_dict())


#    print(message.identity  + ": " + RTCM_MSGIDS[message.identity],file=outfile)
    print(standardNumber(message,3),file=outfile)
    print(standard421(message),file=outfile)
    standard422andSubs(message,outfile)

#    print(standardNumber(message,422))

    return(True)


OUTPUT_FUNCTIONS={
    1006: output_1006,
    1008: output_1008,
    1013: output_1013,
    1033: output_1033,

    1071: output_MSM,
    1072: output_MSM,
    1073: output_MSM,
    1074: output_MSM,
    1075: output_MSM,
    1076: output_MSM,
    1077: output_MSM,

    1081: output_MSM,
    1082: output_MSM,
    1083: output_MSM,
    1084: output_MSM,
    1085: output_MSM,
    1086: output_MSM,
    1087: output_MSM,

    1091: output_MSM,
    1092: output_MSM,
    1093: output_MSM,
    1094: output_MSM,
    1095: output_MSM,
    1096: output_MSM,
    1097: output_MSM,

    1111: output_MSM,
    1112: output_MSM,
    1113: output_MSM,
    1114: output_MSM,
    1115: output_MSM,
    1116: output_MSM,
    1117: output_MSM,

    1121: output_MSM,
    1122: output_MSM,
    1123: output_MSM,
    1124: output_MSM,
    1125: output_MSM,
    1126: output_MSM,
    1127: output_MSM,

    1230: output_1230,
    }

def print_record(parsed_data,outfile,obsSummary):



    if int(parsed_data.identity) in OUTPUT_FUNCTIONS:
        OUTPUT_FUNCTIONS[int(parsed_data.identity)](parsed_data,outfile,obsSummary=obsSummary)
    else:
        print("   Undecoded\n",file=outfile)
        pass
    print("\n",file=outfile)


#    sys.exit(22)

    #            pprint(parsed_data._get_dict())
    """
    if output_1006(parsed_data,outfile):
        pass
    elif output_1008(parsed_data,outfile):
        pass
    elif output_1013(parsed_data,outfile):
        pass
    elif output_1033(parsed_data,outfile):
        pass
    elif output_MSM(parsed_data,outfile):
        pass
    elif output_1230(parsed_data,outfile):
        pass
    else:
        try:
            print(parsed_data.GNSSEpoch)
        except:
            print("No GNSSEpoch")
        pass
    #                print(parsed_data)


    #            dfname = "DF003"
    #            pprint(RTCM_DATA_FIELDS[dfname])
    #            print(datasiz(dfname)) # size in bits
    #            print(datascale(dfname)) # scaling factor
    #            print(datadesc(dfname)) # description
    #            print(parsed_data)
"""
