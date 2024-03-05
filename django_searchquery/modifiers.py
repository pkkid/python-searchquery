# encoding: utf-8
import timelib
from .exceptions import SearchError
from . import utils


def boolean(valuestr):
    if valuestr.lower() in ('true', 't', 'yes', 'y', '1'):
        return True
    elif valuestr.lower() in ('false', 'f', 'no', 'n', '0'):
        return False
    raise SearchError(f"Invalid boolean value '{valuestr}'")


def date(valuestr, tzinfo=None):
    try:
        valuestr = valuestr.replace('_', ' ')
        dt = timelib.strtodatetime(valuestr.encode('utf8'))
        return dt.astimezone(tzinfo)
    except Exception:
        raise SearchError(f"Invalid date format '{valuestr}'.")


def duration(valuestr):
    """ Convert valuestr such as 1d, 1h, 1m, 1s to an integer. """
    try:
        return utils.convert_units(valuestr, utils.UNITS_SECONDS)
    except Exception as err:
        raise SearchError(f"Unknown duration format '{valuestr}'")


def num(valuestr):
    """ Convert valuestr such as 1k, 1M, 1G to an integer. """
    try:
        return utils.convert_units(valuestr, utils.UNITS_NUM)
    except Exception as err:
        raise SearchError(f"Unknown number format '{valuestr}'")


def percent(valuestr):
    """ Convert valuestr such as 99% to 0.99. """
    try:
        percentValue = valuestr
        if percentValue[-1] == '%':
            percentValue = percentValue[:-1]
        return float(percentValue) / 100
    except Exception:
        raise SearchError(f"Invalid percent format '{valuestr}'")
