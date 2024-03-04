# encoding: utf-8
import calendar, re
from functools import reduce

NONE = ('none', 'null')
MONTH_NAMES = [m.lower() for m in list(calendar.month_name)[1:]]
MONTH_NAMES += [m.lower() for m in list(calendar.month_abbr)[1:]]
MONTH_NAMES += ['sept']
WEEKDAY_NAMES = [d.lower() for d in list(calendar.day_name)]
WEEKDAY_NAMES += [d.lower() for d in list(calendar.day_abbr)]
YEAR, MONTH, WEEK, DAY = 'year', 'month', 'week', 'day'


def is_none(valuestr):
    """ Returns true if the value is a None string. """
    if valuestr.lower() in NONE:
        return True
    return False


def is_int(valuestr):
    """ Returns true if the valuestr can be converted to an int. """
    try:
        int(valuestr)
        return True
    except ValueError:
        return False


def is_number(valuestr):
    """ Returns true if the valuestr can be converted to a float. """
    try:
        float(valuestr)
        return True
    except ValueError:
        return False


def datestr_rdelta(valuestr):
    """ Given a datestr, try our best to determine the a new relativedelta object
        contianing the duration of time it is referring to. There are obviously
        dragons here, but I can't think of a better way.
    """
    # Determine the delimiter
    delim = None
    delim = '.' if '.' in valuestr else delim
    delim = '/' if '/' in valuestr else delim
    delim = '-' if '-' in valuestr else delim
    # Cleanup the datestr
    datestr = valuestr.strip().lower()
    datestr = re.sub(r'[\/\.\-]', ' ', datestr)
    # Check we can quickly match the datestr
    quickmatch = {
        'last year': YEAR, 'this year': YEAR, 'next year': YEAR,
        'last month': MONTH, 'this month': MONTH, 'next month': MONTH,
        'last week': WEEK, 'this week': WEEK, 'next week': WEEK,
        'yesterday': DAY, 'today': DAY, 'tomorrow': DAY,
    }
    if datestr in quickmatch:
        return quickmatch[datestr]
    # More complicated checks
    strs = datestr.split()
    if is_year(valuestr): return YEAR  # 2024
    if is_month(valuestr): return MONTH  # Jan
    if len(strs) == 2:
        s1, s2 = strs
        if is_month(s1) and is_year(s2): return MONTH  # Jan 2024
        if is_year(s1) and is_month(s2): return MONTH  # 2024 Jan
        if is_month(s1) and is_day_num(s2): return DAY  # Jan 21
        if is_day_num(s1) and is_month(s2): return DAY  # 21 Jan
        if s1 == 'last' and is_weekday(s2): return DAY  # last wed
        if s1 == 'this' and is_weekday(s2): return DAY  # this wed
        if s1 == 'next' and is_weekday(s2): return DAY  # next wed
    if len(strs) == 3:
        s1, s2, s3 = strs
        if is_year(s1) and is_month(s2) and is_day_num(s3): return DAY  # 2024 Jan 21
        if is_month(s1) and is_day_num(s2) and is_year(s3): return DAY  # Jan 21 2024
        if is_day_num(s1) and is_month(s2) and is_year(s3): return DAY  # 21 Jan 2024
        if is_year(s1) and is_month_num(s2) and is_day_num(s3): return DAY  # 2024 01 01
        if is_month_num(s1) and is_day_num(s2) and is_year(s3) and delim in '/-': return DAY  # 01/01/2024
        if is_day_num(s1) and is_month_num(s2) and is_year(s3) and delim == '.': return DAY  # 01.01.2024
    return None


def is_weekday(valuestr):
    """ Returns true if the valuestr is a weekday name. """
    return valuestr.lower() in WEEKDAY_NAMES


def is_day_num(valuestr):
    """ Returns true if the valuestr is a number between 1-31. """
    return is_int(valuestr) and 0 < int(valuestr) <= 31


def is_month(valuestr):
    """ Returns true if the valuestr is a month name. """
    return valuestr.lower().strip() in MONTH_NAMES


def is_month_num(valuestr):
    return is_int(valuestr) and 0 < int(valuestr) <= 12


def is_year(valuestr):
    """ Returns true if the valuestr is a 4 digit year. """
    return is_int(valuestr) and 1900 <= int(valuestr) <= 2100


def clear_dt(dt, clearto='day'):
    """ Return the dt from the beginning of the month. """
    attrs = ['year','month','day','hour','minute','second','microsecond']
    kwargs = {}
    for attr in attrs[attrs.index(clearto)+1:]:
        newvalue = 1 if attr in ('month', 'day') else 0
        kwargs[attr] = newvalue
    return dt.replace(**kwargs)


def merge_queries(queries, andjoin=True):
    """ Merge all subqueries into a single query. """
    # The logic here can be a bit tangled up as the method to join queries
    # with pretty tightly coupled with exlude. In short, if we are excluding,
    # we generally want to join with AND (unless were doing a bitwise AND,
    # then its backwards).
    if andjoin:
        return reduce(lambda x,y: x & y, queries)
    return reduce(lambda x,y: x | y, queries)
