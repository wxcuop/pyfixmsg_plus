"""Small utility-type functions"""

import datetime
import time

DATEFORMAT = '%Y%m%d-%H:%M:%S.%f'


def int_or_str(val, decode_as=None):
    """ simple format to int or string if not possible """
    try:
        return int(val)
    except ValueError:
        if decode_as is None:
            if isinstance(val, (bytes, str)):
                return val.strip()
            else:
                return str(val)
        elif isinstance(val, bytes):
            return val.decode(decode_as).strip()
        else:
            raise ValueError('Cannot decode type {}'.format(type(val)))


def native_str(val, encoding='UTF-8'):
    """ format to native string (support int type) """
    if val is None:
        return val
    if isinstance(val, int):
        return str(val)
    if isinstance(val, bytes):
        return val.decode(encoding)
    return str(val)


def utc_timestamp():
    """
    @return: a UTCTimestamp (see FIX spec)
    @rtype: str
    """
    return datetime.datetime.utcnow().strftime(DATEFORMAT)


def generate_clordid(prefix="ORD"):
    """
    Generates a unique Client Order ID (ClOrdID).
    :param prefix: A prefix for the ClOrdID (default is "ORD").
    :return: A unique ClOrdID string.
    """
    timestamp = int(time.time() * 1000)  # Current time in milliseconds
    return f"{prefix}{timestamp}"
