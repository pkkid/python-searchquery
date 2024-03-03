# encoding: utf-8
import calendar, re

NONE = ('none', 'null')
MONTHNAMES = [m.lower() for m in list(calendar.month_name)[1:]]
MONTHNAMES += [m.lower() for m in list(calendar.month_abbr)[1:]]
MONTHNAMES += ['sept']


def is_int(value):
    """ Returns true if the value can be converted to an int. """
    try:
        int(value)
        return True
    except ValueError:
        return False


def is_month(value):
    """ Returns true if the value is a month name. """
    parts = value.lower().split()
    if len(parts) == 1 and parts[0] in MONTHNAMES:
        return True
    elif len(parts) == 2 and is_year(parts[0]) and is_month(parts[1]):
        return True
    elif len(parts) == 2 and is_month(parts[0]) and is_year(parts[1]):
        return True
    return False


def is_none(valuestr):
    """ Returns true if the value is a None string. """
    if valuestr.lower() in NONE:
        return True
    return False


def is_number(value):
    """ Returns true if the value can be converted to a float. """
    try:
        float(value)
        return True
    except ValueError:
        return False


def is_year(value):
    """ Returns true if the value is a 4 digit year. """
    return re.match(r'^20\d\d$', value.lower())
