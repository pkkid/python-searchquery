# encoding: utf-8
import calendar, re
from functools import reduce

# Valid month names january-december + jan-dec + sept
MONTH_NAMES = [m.lower() for m in list(calendar.month_name)[1:]]
MONTH_NAMES += [m.lower() for m in list(calendar.month_abbr)[1:]]
MONTH_NAMES += ['sept']  # also very common

# Valid weekday names sunday-saturday + sun-sat
WEEKDAY_NAMES = [d.lower() for d in list(calendar.day_name)]
WEEKDAY_NAMES += [d.lower() for d in list(calendar.day_abbr)]

# Other useful constants
YEAR, MONTH, WEEK, DAY = 'year', 'month', 'week', 'day'
NONE = ('none', 'null')
UNITS_NUM = (
    (1000000000000000.0, ('q','qa','quadrillion')),
    (1000000000000.0, ('t','tn','trillion')),
    (1000000000.0, ('b','bn','billion')),
    (1000000.0, ('m','million')),
    (1000.0, ('k','thousand')),
    (1.0, ()),
)
UNITS_SECONDS = (
    (31536000.0, ('y','yr','yrs','year','years')),  # 365 days
    (2678400.0, ('mo','mos','month','months')),  # 31 days
    (604800.0, ('w','wk','wks','week','weeks')),
    (86400.0, ('d','day','days')),
    (3600.0, ('h','hr','hrs','hour','hours')),
    (60.0, ('m','min','mins','minute','minutes')),
    (1.0, ('s','sec','secs','second','seconds')),
)


def clear_dt(dt, clearto='day'):
    """ Return the dt from the beginning of the month. """
    attrs = ['year','month','day','hour','minute','second','microsecond']
    kwargs = {}
    for attr in attrs[attrs.index(clearto)+1:]:
        newvalue = 1 if attr in ('month', 'day') else 0
        kwargs[attr] = newvalue
    return dt.replace(**kwargs)


def datestr_rdelta(valuestr):
    """ Given a datestr, try our best to determine the duration of time it is
        referring to. This is used when searching a DateField for a specific
        timeframe (like 'yesterday'). These have a start and end; they are
        not specific to a single point in time. After the duration is passed
        back, we can use this along with whatever single date is returned from
        timelib to figure out the start and end times to filter on. There are
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


def is_day_num(valuestr):
    """ Returns true if the valuestr is a number between 1-31. """
    return is_int(valuestr) and 0 < int(valuestr) <= 31


def is_int(valuestr):
    """ Returns true if the valuestr can be converted to an int. """
    try:
        int(valuestr)
        return True
    except ValueError:
        return False


def is_month(valuestr):
    """ Returns true if the valuestr is a month name. """
    return valuestr.lower().strip() in MONTH_NAMES


def is_month_num(valuestr):
    return is_int(valuestr) and 0 < int(valuestr) <= 12


def is_none(valuestr):
    """ Returns true if the value is a None string. """
    if valuestr.lower() in NONE:
        return True
    return False


def is_number(valuestr):
    """ Returns true if the valuestr can be converted to a float. """
    try:
        float(valuestr)
        return True
    except ValueError:
        return False


def is_weekday(valuestr):
    """ Returns true if the valuestr is a weekday name. """
    return valuestr.lower() in WEEKDAY_NAMES


def is_year(valuestr):
    """ Returns true if the valuestr is a 4 digit year. """
    return is_int(valuestr) and 1900 <= int(valuestr) <= 2100


def merge_queries(qobjects, andjoin=True):
    """ Merge all qobjects into a single qobject. """
    # The logic here can be a bit tangled up as the method to join qobjects
    # with pretty tightly coupled with exlude. In short, if we are excluding,
    # we generally want to join with AND (unless were doing a bitwise AND,
    # then its backwards).
    if andjoin:
        return reduce(lambda x,y: x & y, qobjects)
    return reduce(lambda x,y: x | y, qobjects)


def parent_searchfields(searchfields, search_key_prefix='', search_key_suffix='',
                        model_field_prefix='', model_field_suffix=''):
    """ Returns a new list of searchfields with the search_keys or model_fields
        updated with a prefix or suffix. This makes it easy to include parent
        search fields on a child table.
    """
    newsearchfields = []
    for sf in searchfields:
        cls = sf.__class__
        searchkey = f'{search_key_prefix}{sf.search_key}{search_key_suffix}'
        modelfield = f'{model_field_prefix}{sf.model_field}{model_field_suffix}'
        newsearchfield = cls(search_key=searchkey, model_field=modelfield,
            desc=sf.desc, mod=sf.mod, modargs=sf.modargs)
        newsearchfields.append(newsearchfield)
    return newsearchfields


def convert_units(valuestr, units=UNITS_NUM):
    """ Convert the valuestr to a number and multiply by the unit. """
    if not valuestr:
        return 0
    valuestr = valuestr.lower().strip()
    matches = re.findall(r'^(-*[0-9\.]+)\s*([a-z]+)$', valuestr)
    if len(matches) and len(matches[0]) == 2:
        value, unit = matches[0]
        for mult, unitlist in units:
            if unit in unitlist:
                return float(value) * mult
    if is_number(valuestr):
        return float(valuestr)
    raise Exception(f"Unknown number format '{valuestr}'")
