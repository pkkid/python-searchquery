# encoding: utf-8
import pytz
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db.models import Q
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
        if self.mod is None: return valuestr
        return self.mod(valuestr, *self.modargs)

    def get_subquery(self, valuestr, operator=':', exclude=False):
        """ Returns list of subqueries for the given valuestr and operator. """
        if utils.is_none(valuestr):
            return self.get_subquery_none(valuestr, operator, exclude)
        kwarg = f'{self.model_field}{OPERATORS[operator]}'
        qvalue = self.get_qvalue(valuestr)
        qobject = Q(**{kwarg: qvalue})
        return ~qobject if exclude else qobject
    
    def get_subquery_none(self, valuestr, operator=':', exclude=False):
        """ Returns the subquery for None value. """
        if operator not in ('=', ':'):
            raise SearchError(f"Invalid operator '{operator}' for None value")
        kwarg = f'{self.model_field}__isnull'
        qobject = Q(**{kwarg: True})
        return ~qobject if exclude else qobject


class BoolField(SearchField):
    VALID_OPERATORS = (':','=')

    def __init__(self, search_key, model_field=None, desc=None, mod=None, modargs=None):
        mod = mod or modifiers.boolean
        super().__init__(search_key, model_field, desc, mod, modargs)
    
    def get_subquery(self, valuestr, operator=':', exclude=False):
        """ Returns list of subqueries for the given valuestr and operator. """
        qvalue = self.get_qvalue(valuestr)
        if utils.is_none(valuestr):
            return self.get_subquery_none(valuestr, operator, exclude)
        qvalue = self.get_qvalue(valuestr)
        qobject = Q(**{self.model_field: qvalue})
        return ~qobject if exclude else qobject


class DateField(SearchField):
    VALID_OPERATORS = ('=', '>', '>=', '<=', '<')

    def __init__(self, search_key, model_field=None, desc=None, mod=None, modargs=None):
        mod = mod or modifiers.date
        modargs = modargs or self._default_modargs()
        super().__init__(search_key, model_field, desc, mod, modargs)

    def _default_modargs(self):
        return [pytz.timezone(settings.TIME_ZONE)] if settings.TIME_ZONE else []
    
    def get_subquery(self, valuestr, operator=':', exclude=False):
        # Build kwargs from the min and max dates. It looks like we're changing
        # the > to >= here, becasue we are. Dates are funny and people of think
        # of them inclusively.
        if utils.is_none(valuestr):
            return self.get_subquery_none(valuestr, operator, exclude)
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
        qobjects = []
        for kwarg, qvalue in kwargs.items():
            qobject = Q(**{kwarg: qvalue})
            qobject = ~qobject if exclude else qobject
            qobjects.append(qobject)
        return utils.merge_qobjects(qobjects, exclude)

    def _get_min_max_dates(self, valuestr):
        qvalue = self.get_qvalue(valuestr)
        rdelta = utils.datestr_rdelta(valuestr)
        now = datetime.now(self.modargs[0])  # modargs[0]=tz
        if rdelta == utils.YEAR:
            mindate = utils.clear_dt(qvalue, 'year')
            maxdate = mindate + relativedelta(years=1)
            return mindate, maxdate
        if rdelta == utils.MONTH:
            mindate = utils.clear_dt(qvalue, 'month')
            if mindate > now:
                mindate -= relativedelta(years=1)
            maxdate = mindate + relativedelta(months=1)
            return mindate, maxdate
        if rdelta == utils.WEEK:
            mindate = qvalue - timedelta(days=(qvalue.weekday() + 1) % 7)
            mindate = utils.clear_dt(mindate, 'day')
            maxdate = mindate + relativedelta(days=7)
            return mindate, maxdate
        if rdelta == utils.DAY:
            mindate = utils.clear_dt(qvalue, 'day')
            maxdate = mindate + timedelta(days=1)
            return mindate, maxdate
        return qvalue, None


class NumField(SearchField):
    VALID_OPERATORS = ('=', '>', '>=', '<=', '<', ':')
    
    def __init__(self, search_key, model_field=None, desc=None, mod=None, modargs=None):
        mod = mod or modifiers.num
        super().__init__(search_key, model_field, desc, mod, modargs)

    def get_subquery(self, valuestr, operator=':', exclude=False):
        """ Returns list of subqueries for the given valuestr and operator. """
        if utils.is_none(valuestr):
            return self.get_subquery_none(valuestr, operator, exclude)
        if operator == ':':
            return self._get_contains_subquery(valuestr)
        return super().get_subquery(valuestr, operator, exclude)
    
    def _get_contains_subquery(self, valuestr):
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
        qobject = Q(**negfilter)
        if ispositive:
            posfilter = {f'{self.model_field}__gte': qvalue, f'{self.model_field}__lt': qvalue + variance}
            qobject |= Q(**posfilter)
        return qobject


class StrField(SearchField):
    VALID_OPERATORS = ('=', ':')

    def __init__(self, search_key, model_field=None, desc=None, mod=None, modargs=None):
        default_modifier = lambda valuestr: valuestr
        mod = mod or default_modifier
        super().__init__(search_key, model_field, desc, mod, modargs)
        
    def get_subquery(self, valuestr, operator=':', exclude=False):
        """ Returns list of subqueries for the given valuestr and operator. """
        if utils.is_none(valuestr):
            return self.get_subquery_none(valuestr, operator, exclude)
        if operator not in self.VALID_OPERATORS:
            raise SearchError(f"Invalid operator '{operator}' for string field")
        return super().get_subquery(valuestr, operator, exclude)
