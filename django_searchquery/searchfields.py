# encoding: utf-8
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from . import modifiers, utils
from .exceptions import SearchError

OPERATORS = {'=':'__iexact', '>':'__gt', '>=':'__gte', '<=':'__lte', '<':'__lt', ':': '__icontains'}
REVERSEOP = {'__gt':'__lte', '__gte':'__lt', '__lte':'__gt', '__lt':'__gte'}


class SearchField:
    """ Abstract SearchField class. Don't use this directly. """
    VALID_OPERATORS = ()
    
    def __init__(self, search_key, model_field=None, desc=None, mod=None, modargs=None):
        default_modifier = lambda valuestr: valuestr
        self.search_key = search_key                    # Field string user should input
        self.model_field = model_field or search_key    # Model field lookup (ex: account__first_name)
        self.desc = desc                                # Human readable description
        self.mod = mod or default_modifier              # Callback to modify search_value comparing
        self.modargs = modargs or []                    # Additional args to pass to the modifier
        
    def __str__(self):
        return f'<{self.__class__.__name__}:{self.model_field}>'

    def get_qvalue(self, valuestr):
        """ Returns value to be used in the query. """
        if utils.is_none(valuestr): return None
        if self.mod is None: return valuestr
        return self.mod(valuestr, *self.modargs)

    def get_subquery(self, basequery, valuestr, operator=':', exclude=False):
        """ Returns list of subqueries for the given valuestr and operator. """
        kwarg = f'{self.model_field}{OPERATORS[operator]}'
        qvalue = self.get_qvalue(valuestr)
        queryfunc = basequery.exclude if exclude else basequery.filter
        return queryfunc(**{kwarg: qvalue})


class BoolField(SearchField):
    VALID_OPERATORS = ('=',)

    def __init__(self, search_key, model_field=None, desc=None, mod=None, modargs=None):
        super().__init__(search_key, model_field, desc, mod, modargs)
        self.mod = self.mod or modifiers.boolean


class DateField(SearchField):
    VALID_OPERATORS = ('=', '>', '>=', '<=', '<')

    def __init__(self, search_key, model_field=None, desc=None, mod=None, modargs=None):
        super().__init__(search_key, model_field, desc, mod, modargs)
        self.mod = self.mod or modifiers.date

    def get_qvalue(self, valuestr):
        if utils.is_none(valuestr): return None
        return modifiers.date(valuestr, *self.modargs)
    
    def get_subquery(self, basequery, valuestr, operator=':', exclude=False):
        # Build kwargs from the min and max dates. It looks like we're changing
        # the > to >= here, becasue we are. Dates are funny and people of think
        # of them inclusively.
        kwargs = {}
        mindate, maxdate = self._get_min_max_dates(valuestr)
        if operator in ('>=', '>'):
            kwargs[f'{self.model_field}{OPERATORS[">="]}'] = mindate
        elif operator in ('<=', '<'):
            kwargs[f'{self.model_field}{OPERATORS["<="]}'] = mindate
        elif operator == '=':
            kwargs[f'{self.model_field}{OPERATORS[">="]}'] = mindate
            kwargs[f'{self.model_field}{OPERATORS["<"]}'] = maxdate
        # Build and return the queryset
        subqueries = []
        for kwarg, qvalue in kwargs.items():
            queryfunc = basequery.exclude if exclude else basequery.filter
            subqueries.append(queryfunc(**{kwarg: qvalue}))
        return utils.merge_queries(subqueries, exclude)

    def _get_min_max_dates(self, valuestr):
        qvalue = self.get_qvalue(valuestr)
        valuestr = valuestr.lower()
        if utils.is_year(valuestr):
            minyear = int(qvalue.strftime('%Y'))
            mindate = datetime(minyear, 1, 1)
            maxdate = mindate + relativedelta(years=1)
            return mindate, maxdate
        elif utils.is_month(valuestr):
            minyear = int(qvalue.strftime('%Y'))
            minmonth = int(qvalue.strftime('%m'))
            mindate = datetime(minyear, minmonth, 1)
            if mindate > datetime.today() and str(minyear) not in valuestr:
                mindate -= relativedelta(years=1)
            maxdate = mindate + relativedelta(months=1)
            return mindate, maxdate
        mindate = qvalue
        maxdate = mindate + timedelta(days=1)
        return mindate, maxdate


class NumField(SearchField):
    VALID_OPERATORS = ('=', '>', '>=', '<=', '<', ':')

    def __init__(self, search_key, model_field=None, desc=None, mod=None, modargs=None):
        super().__init__(search_key, model_field, desc, mod, modargs)
        self.mod = self.mod or modifiers.num

    def get_subquery(self, basequery, valuestr, operator=':', exclude=False):
        """ Returns list of subqueries for the given valuestr and operator. """
        if operator == ':':
            return self._get_contains_subquery(basequery, valuestr)
        return super().get_subquery(basequery, valuestr, operator, exclude)
    
    def _get_contains_subquery(self, basequery, valuestr):
        """ Returns list of subqueries for a generic 'contains' search. """
        # There are two things that make generically searching a number not as
        # straight forward as one might think:
        #   1. Signifigant digits are relevant. For example: The user could be
        #      searching for 123, but they would want to include 123.45.
        #   2. Remember its a generic search, so 123 should also match -123.
        #      However, -123 should not match 123 as the - was explicit.
        ispositive = not valuestr.startswith('-')
        qvalue = abs(float(self.get_qvalue(valuestr)))
        sigdigs = len(valuestr.split('.')[1]) if '.' in valuestr else 0
        variance = round(.1 ** sigdigs, sigdigs)
        negfilter = {f'{self.model_field}__lte': -qvalue, f'{self.model_field}__gt': -qvalue - variance}
        subquery = basequery.filter(**negfilter)
        if ispositive:
            posfilter = {f'{self.model_field}__gte': qvalue, f'{self.model_field}__lt': qvalue + variance}
            subquery |= basequery.filter(**posfilter)
        return subquery


class StrField(SearchField):
    VALID_OPERATORS = ('=', ':')

    def __init__(self, search_key, model_field=None, desc=None, mod=None, modargs=None):
        super().__init__(search_key, model_field, desc, mod, modargs)
        default_modifier = lambda valuestr, _: valuestr
        self.mod = self.mod or default_modifier
    
    def get_subquery(self, basequery, valuestr, operator=':', exclude=False):
        """ Returns list of subqueries for the given valuestr and operator. """
        if operator not in self.VALID_OPERATORS:
            raise SearchError(f"Invalid operator '{operator}' for string field")
        return super().get_subquery(basequery, valuestr, operator, exclude)
