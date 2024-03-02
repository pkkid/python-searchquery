# encoding: utf-8
import calendar, datetime, logging, re, shlex, timelib
from dateutil.relativedelta import relativedelta
from django.db.models import Q
from functools import reduce
from types import SimpleNamespace
log = logging.getLogger(__name__)

NONE = ('none', 'null')
OPERATIONS = {'=':'__iexact', '>':'__gt', '>=':'__gte', '<=':'__lte', '<':'__lt', ':': '__icontains'}
REVERSEOP = {'__gt':'__lte', '__gte':'__lt', '__lte':'__gt', '__lt':'__gte'}
STOPWORDS = ('and', '&&', '&', 'or', '||', '|')
MONTHNAMES = [m.lower() for m in list(calendar.month_name)[1:] + list(calendar.month_abbr)[1:] + ['sept']]
DEFAULT_MODIFIER = lambda value: value

FIELDTYPES = SimpleNamespace()
FIELDTYPES.BOOL = 'bool'
FIELDTYPES.DATE = 'date'
FIELDTYPES.NUM = 'numeric'
FIELDTYPES.STR = 'string'


class SearchError(Exception):
    pass


class SearchField:

    def __init__(self, fieldstr, fieldtype, field, modifier=None, desc=None):
        self.fieldstr = fieldstr        # field string user should input
        self.fieldtype = fieldtype      # field type (NUM, STR, ...)
        self.field = field              # model field lookup (ex: account__first_name)
        self.modifier = modifier        # callback to modify search_value comparing
        self.desc = desc                # Human readable description
        
    def __str__(self):
        return '<%s:%s:%s>' % (self.__class__.__name__, self.fieldtype, self.field)
        
        
class Search:
    
    def __init__(self, basequeryset, fields, searchstr, tzinfo=None):
        self.errors = []                                # list of errors to display
        self.basequeryset = basequeryset                # base queryset to filter in Search
        self.fields = {f.fieldstr:f for f in fields}    # field objects to filter on
        self.searchstr = searchstr                      # orignal search string
        self.tzinfo = tzinfo                            # tzinfo for datetime fields
        self._queryset = None                           # final queryset
    
    @property
    def meta(self):
        """ Returns metadata about this Search object. """
        result = {}
        result['fields'] = {k:f.desc for k,f in self.fields.items()}
        if self.searchstr:
            result['query'] = self.searchstr or ''
            result['filters'] = self.filterstrs
            if self.errors:
                result['errors'] = ', '.join(self.errors)
        return result
    
    @property
    def filterstrs(self):
        """ Returns a list of processed filters used in the search. """
        return {c.filterstr:c.searchtype for c in self.chunks}

    def _build_chunks(self):
        try:
            chunkstrs = shlex.split(self.searchstr)
            for chunk in [c for c in chunkstrs if c in STOPWORDS]:
                self.errors.append('Part of the search is being ignored: %s' % chunk)
            return [SearchChunk(self, c) for c in chunkstrs if c not in STOPWORDS]
        except Exception as err:
            self.errors.append('Invalid query: %s' % err)
            log.exception(err)
            
    def queryset(self):
        if self._queryset is None:
            self.chunks = self._build_chunks()
            if self.errors:
                print('%s errors found in search!' % len(self.errors))
                self._queryset = self.basequeryset.filter(pk=-1)
            else:
                queryset = self.basequeryset
                for chunk in self.chunks:
                    queryset = queryset & chunk.queryset()
                self.errors = [c.error for c in self.chunks if c.error]
                # self.datefilters = self._list_datefilters()
                self._queryset = queryset
        log.debug(self._queryset.query)
        return self._queryset
        
    
class SearchChunk:
    
    def __init__(self, search, chunkstr):
        self.search = search            # reference to parent search object
        self.chunkstr = chunkstr        # single part of search.searchstr
        self.exclude = False            # set True if this is an exclude
        self.field = None               # search field from chunkstr
        self.operation = None           # search operation from chunkstr
        self.value = None               # search value from chunkstr
        self.qfield = None              # django query field
        self.qoperation = None          # django query operation
        self.qvalue = None              # django query value
        self.error = None               # error message (if applicable)
        self.filterstr = ''             # Human readable filter string
        self._parse_chunkstr()
        
    def __str__(self):
        rtnstr = '\n--- %s ---\n' % self.__class__.__name__
        for attr in ('chunkstr','exclude','field','value','qfield','qoperation','qvalue','error'):
            value = getattr(self, attr)
            if value is not None:
                rtnstr += '%-12s %s\n' % (attr + ':', value)
        return rtnstr

    @property
    def searchtype(self):
        if self.operation == ':':
            return FIELDTYPES.STR
        return self.search.fields.get(self.field).fieldtype
        
    @property
    def is_value_list(self):
        if len(self.value) == 0:
            return False
        return self.value[0] == '[' and self.value[-1] == ']'
    
    def _update_filterstr(self, join='', **kwargs):
        # Parse the kwargs
        exclude = kwargs.get('exclude', self.exclude)
        field = kwargs.get('field', self.qfield)
        qoperation = kwargs.get('qoperation', self.qoperation)
        qvalue = kwargs.get('qvalue', self.qvalue)
        # Generic search
        excludestr = '-' if exclude else ''
        valuestr = qvalue if ' ' not in str(qvalue) else f"'{qvalue}'"
        valuestr = str(valuestr).replace(' 00:00:00', '')
        joinstr = join if not join else f' {join} '
        if not field:
            self.filterstr += f'{joinstr}{excludestr}{valuestr}'
            return self.filterstr
        # Advanced or Date search
        fieldstr = field.fieldstr
        opstr = dict((v,k) for k,v in OPERATIONS.items()).get(qoperation)
        # opstr = opstr if opstr == ':' else f' {opstr} '
        self.filterstr += f'{joinstr}{excludestr}{fieldstr}{opstr}{valuestr}'
        return self.filterstr

    def _parse_chunkstr(self):
        try:
            chunkstr = self.chunkstr
            # check exclude pattern
            if '-' == chunkstr[0]:
                self.exclude = True
                chunkstr = chunkstr[1:]
            # save default value and operation
            self.value = chunkstr
            self.qvalue = chunkstr
            self.operation = ':'
            # check advanced search operations
            for operation in sorted(OPERATIONS.keys(), key=len, reverse=True):
                parts = chunkstr.split(operation, 1)
                if len(parts) == 2:
                    # extract field, operation, and value
                    self.field = parts[0]
                    self.operation = operation
                    self.value = parts[1]
                    # fetch the qfield, qoperation, and qvalue
                    self.qfield = self._get_qfield()
                    self.qvalue = self._get_qvalue()
                    self.qoperation = self._get_qoperation()
                    break  # only use one operation
        except SearchError as err:
            log.error(err)
            self.error = str(err)
            
    def _get_qfield(self):
        field = self.search.fields.get(self.field)
        if not field:
            raise SearchError('Unknown field: %s' % self.field)
        elif self.searchtype != field.fieldtype:
            raise SearchError('Unknown %s field: %s' % (self.searchtype, self.field))
        return field
    
    def _get_qoperation(self):
        # check were searching none
        if self.value.lower() in NONE:
            return '__isnull'
        # regex will catch invalid operations, no need to check
        operation = OPERATIONS[self.operation]
        if self.is_value_list and self.operation == '=':
            operation = '__in'
        elif isinstance(self.qvalue, bool):
            operation = ''
        return operation
        
    def _get_qvalue(self):
        # check were searching none
        if self.value.lower() in NONE:
            return True
        # get correct modifier
        modifier = DEFAULT_MODIFIER
        modifier_args = {}
        if self.qfield.modifier:
            modifier = self.qfield.modifier
        elif self.searchtype == FIELDTYPES.BOOL:
            modifier = modifier_bool
        elif self.searchtype == FIELDTYPES.NUM:
            modifier = modifier_numeric
        elif self.searchtype == FIELDTYPES.DATE:
            modifier = modifier_date
            modifier_args = {'tzinfo': self.search.tzinfo}
        # process the modifier
        if self.is_value_list:
            return self._parse_value_list(modifier)
        return modifier(self.value, **modifier_args)
        
    def _parse_value_list(self, modifier):
        if self.operation != '=':
            raise SearchError('Invalid operation is using list search: %s' % self.operation)
        qvalues = set()
        values = self.value.lstrip('[').rstrip(']')
        for value in values.split(','):
            qvalues.add(modifier(value))
        return qvalues
        
    def queryset(self):
        try:
            queryset = self.search.basequeryset.all()
            if self.error:
                return queryset
            elif not self.field:
                return queryset & self._queryset_generic()
            elif isinstance(self.qvalue, datetime.datetime):
                return queryset & self._queryset_datetime()
            return queryset & self._queryset_advanced()
        except Exception as err:
            log.exception(err)
        
    def _queryset_generic(self):
        self._update_filterstr()
        subqueries = self._queryset_generic_string()
        subqueries += self._queryset_generic_num()
        if self.exclude:
            return reduce(lambda x,y: x & y, subqueries)
        return reduce(lambda x,y: x | y, subqueries)

    def _queryset_generic_string(self):
        # check all string fields for self.qvalue
        subqueries = []
        stringfields = (f for f in self.search.fields.values() if f.fieldtype == FIELDTYPES.STR)
        for field in stringfields:
            kwarg = '%s%s' % (field.field, OPERATIONS[':'])
            if self.exclude:
                subquery = self.search.basequeryset.exclude(**{kwarg: self.qvalue})
                subqueries.append(subquery)
                continue
            subquery = self.search.basequeryset.filter(**{kwarg: self.qvalue})
            subqueries.append(subquery)
        return subqueries

    def _queryset_generic_num(self):
        # check all int and float fields for self.qvalue
        subqueries = []
        if is_float(self.qvalue):
            numfields = (f for f in self.search.fields.values() if f.fieldtype == FIELDTYPES.NUM)
            for field in numfields:
                qvalue = abs(float(self.qvalue))
                sigdigs = len(self.qvalue.split('.')[1]) if '.' in self.qvalue else 0
                variance = round(.1 ** sigdigs, sigdigs)
                posfilter = {'%s__gte' % field.field: qvalue, '%s__lt' % field.field: qvalue + variance}
                negfilter = {'%s__lte' % field.field: -qvalue, '%s__gt' % field.field: -qvalue - variance}
                subquery = self.search.basequeryset.filter(**posfilter)
                subquery |= self.search.basequeryset.filter(**negfilter)
                subqueries.append(subquery)
        return subqueries
        
    def _queryset_advanced(self):
        self._update_filterstr()
        kwarg = '%s%s' % (self.qfield.field, self.qoperation)
        if self.exclude:
            return self.search.basequeryset.exclude(**{kwarg: self.qvalue})
        return self.search.basequeryset.filter(**{kwarg: self.qvalue})

    def _queryset_datetime(self):
        # return the queryset for a date operation on a specific column.
        clauses = []
        mindate, maxdate = self._min_max_dates()
        if self.operation == '>=': clauses.append([OPERATIONS['>='], mindate])
        if self.operation == '>': clauses.append([OPERATIONS['>='], mindate])
        if self.operation == '<=': clauses.append([OPERATIONS['<='], mindate])
        if self.operation == '<': clauses.append([OPERATIONS['<='], mindate])
        if self.operation == '=':
            clauses.append([OPERATIONS['>='], mindate])
            clauses.append([OPERATIONS['<'], maxdate])
        # build and return the queryset
        qobject = None
        for qoperation, qvalue in clauses:
            if self.exclude:
                qoperation = REVERSEOP[qoperation]
            kwarg = '%s%s' % (self.qfield.field, qoperation)
            if not qobject:
                qobject = Q(**{kwarg: qvalue})
                self._update_filterstr(qoperation=qoperation, qvalue=qvalue)
            elif self.exclude:
                qobject |= Q(**{kwarg: qvalue})
                self._update_filterstr(join='OR', qoperation=qoperation, qvalue=qvalue)
            else:
                qobject &= Q(**{kwarg: qvalue})
                self._update_filterstr(join='AND', qoperation=qoperation, qvalue=qvalue)
        return self.search.basequeryset.filter(qobject)

    def _min_max_dates(self):
        """ Figure out the daterange min and max dates for this date chunk. """
        value = self.value.lower()
        if is_year(value):
            minyear = int(self.qvalue.strftime('%Y'))
            mindate = datetime.datetime(minyear, 1, 1, tzinfo=self.search.tzinfo)
            maxdate = mindate + relativedelta(years=1)
        elif is_month(value):
            minyear = int(self.qvalue.strftime('%Y'))
            minmonth = int(self.qvalue.strftime('%m'))
            mindate = datetime.datetime(minyear, minmonth, 1, tzinfo=self.search.tzinfo)
            today = datetime.datetime.today(tzinfo=self.search.tzinfo)
            if mindate > today and str(minyear) not in self.value:
                mindate -= relativedelta(years=1)
            maxdate = mindate + relativedelta(months=1)
        else:
            mindate = self.qvalue
            maxdate = mindate + datetime.timedelta(days=1)
        return mindate, maxdate


def is_float(value):
    try:
        float(value)
        return True
    except ValueError:
        return False


def is_int(value):
    try:
        int(value)
        return True
    except ValueError:
        return False


def is_month(value):
    parts = value.lower().split()
    if len(parts) == 1 and parts[0] in MONTHNAMES:
        return True
    elif len(parts) == 2 and is_year(parts[0]) and is_month(parts[1]):
        return True
    elif len(parts) == 2 and is_month(parts[0]) and is_year(parts[1]):
        return True
    return False


def is_year(value):
    return re.match(r'^20\d\d$', value.lower())


def modifier_bool(value):
    if value.lower() in ('t', 'true', '1', 'y', 'yes'):
        return True
    elif value.lower() in ('f', 'false', '0', 'n', 'no'):
        return False
    raise SearchError('Invalid bool value: %s' % value)


def modifier_numeric(value):
    if re.match(r'^\-*\d+$', value):
        return int(value)
    elif re.match(r'^\-*\d+.\d+$', value):
        return float(value)
    raise SearchError('Invalid int value: %s' % value)


def modifier_date(value, tzinfo=None):
    try:
        value = value.replace('_', ' ')
        if is_year(value):
            return datetime.datetime(int(value), 1, 1, tzinfo=tzinfo)
        dt = timelib.strtodatetime(value.encode('utf8'))
        return datetime.datetime(dt.year, dt.month, dt.day, tzinfo=tzinfo)
    except Exception:
        raise SearchError("Invalid date format: '%s'" % value)
