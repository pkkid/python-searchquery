# encoding: utf-8
import datetime, re, timelib
from . import utils
from .exceptions import SearchError


def boolean(valuestr):
    if valuestr.lower() in ('true', 't', 'yes', 'y', '1'):
        return True
    elif valuestr.lower() in ('false', 'f', 'no', 'n', '0'):
        return False
    raise SearchError(f"Invalid bool value '{valuestr}'")


def num(valuestr):
    if re.match(r'^\-*\d+$', valuestr):
        return int(valuestr)
    elif re.match(r'^\-*\d+.\d+$', valuestr):
        return float(valuestr)
    raise SearchError(f"Invalid num value '{valuestr}'")


def date(valuestr, tzinfo=None):
    try:
        valuestr = valuestr.replace('_', ' ')
        if utils.is_year(valuestr):
            return datetime.datetime(int(valuestr), 1, 1, tzinfo=tzinfo)
        dt = timelib.strtodatetime(valuestr.encode('utf8'))
        return datetime.datetime(dt.year, dt.month, dt.day, tzinfo=tzinfo)
    except Exception:
        raise SearchError(f"Invalid date format '{valuestr}'")
