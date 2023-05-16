
from datetime import datetime, timedelta


def beidoutow2utc(tow: int) -> datetime.time:
    """
    Convert GPS Time Of Week to UTC time
    (UTC = GPS - 18 seconds; correct as from 1/1/2017).

    :param int tow: GPS Time Of Week
    :return: UTC time hh.mm.ss
    :rtype: datetime.time

    """

    utc = datetime(1980, 1, 6) + timedelta(seconds=(tow / 1000) - 18) + timedelta(seconds=14)
    return utc.time()



def glonass2tow (GlonassGNSSEpoch: int) -> int:

    """
    The MSM Glonass messages GNSSepoch is not a time of week
    """

    dow=GlonassGNSSEpoch>>27 # dow is high 3 bits of a 30 bit value DF416
    sod_mask=(2 ** 27)-1 # seconds of day is the lower 27
    sod=GlonassGNSSEpoch & sod_mask # Get the lower 27 bits. DF034
    if dow != 7:
        tow=dow*86400000 + sod
    else:
        tow=sod

    # tow in ms

    return(tow)



def glonass2dowsod (GlonassGNSSEpoch: int) -> tuple:

    """
    The MSM Glonass messages GNSSepoch is not a time of week
    """

    dow=GlonassGNSSEpoch>>27 # dow is high 3 bits of a 30 bit value DF416
    sod_mask=(2 ** 27)-1 # seconds of day is the lower 27
    sod=GlonassGNSSEpoch & sod_mask # Get the lower 27 bits. DF034

    return((dow,sod))




def glonasstow2utc(tow: int) -> datetime.time:
    """
    Convert GPS Time Of Week to UTC time
    (UTC = GPS - 18 seconds; correct as from 1/1/2017).

    :param int tow: GPS Time Of Week
    :return: UTC time hh.mm.ss
    :rtype: datetime.time

    """

    utc = datetime(1980, 1, 6) + timedelta(seconds=(tow / 1000) - 18) + timedelta(hours=-3) + timedelta(seconds=18)
    return utc.time()


