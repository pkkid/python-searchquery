# encoding: utf-8
from . import modifiers, utils
from .exceptions import SearchError

OPERATORS = {'=':'__iexact', '>':'__gt', '>=':'__gte', '<=':'__lte', '<':'__lt', ':': '__icontains'}
REVERSEOP = {'__gt':'__lte', '__gte':'__lt', '__lte':'__gt', '__lt':'__gte'}


class SearchField:
    """ Abstract SearchField class. Don't use this directly. """
    VALID_OPERATORS = ('=', '>', '>=', '<=', '<', ':')
    
    def __init__(self, searchkey, modelfield=None, modifier=None, desc=None):
        default_modifier = lambda valuestr, _: valuestr
        self.searchkey = searchkey                      # Field string user should input
        self.modelfield = modelfield or searchkey       # Model field lookup (ex: account__first_name)
        self.modifier = modifier or default_modifier    # Callback to modify search_value comparing
        self.desc = desc                                # Human readable description
        
    def __str__(self):
        return f'<{self.__class__.__name__}:{self.modelfield}>'

    def get_qvalue(self, valuestr, searchobj=None):
        """ Returns value to be used in the query. """
        if utils.is_none(valuestr): return None
        if self.modifier is None: return valuestr
        return self.modifier(valuestr, searchobj)

    def get_subquery(self, basequery, valuestr, operator=':', exclude=False):
        """ Returns list of subqueries for the given valuestr and operator. """
        kwarg = f'{self.modelfield}{OPERATORS[operator]}'
        qvalue = self.get_qvalue(valuestr)
        queryfunc = basequery.exclude if exclude else basequery.filter
        return queryfunc(**{kwarg: qvalue})


class BoolField(SearchField):
    VALID_OPERATORS = ('=',)

    def __init__(self, searchkey, modelfield=None, modifier=None, desc=None):
        super().__init__(searchkey, modelfield, modifier, desc)
        self.modifier = self.modifier or modifiers.boolean


class DateField(SearchField):
    VALID_OPERATORS = ('=', '>', '>=', '<=', '<')

    def __init__(self, searchkey, modelfield=None, modifier=None, desc=None):
        super().__init__(searchkey, modelfield, modifier, desc)
        self.modifier = self.modifier or modifiers.date

    def get_qvalue(self, valuestr, searchobj):
        if utils.is_none(valuestr): return None
        return modifiers.date(valuestr, searchobj.tzinfo)


class NumField(SearchField):
    def __init__(self, searchkey, modelfield=None, modifier=None, desc=None):
        super().__init__(searchkey, modelfield, modifier, desc)
        self.modifier = self.modifier or modifiers.num

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
        qvalue = abs(float(self.get_qvalue(valuestr, self)))
        sigdigs = len(valuestr.split('.')[1]) if '.' in valuestr else 0
        variance = round(.1 ** sigdigs, sigdigs)
        negfilter = {f'{self.modelfield}__lte': -qvalue, f'{self.modelfield}__gt': -qvalue - variance}
        subquery = basequery.filter(**negfilter)
        if ispositive:
            posfilter = {f'{self.modelfield}__gte': qvalue, f'{self.modelfield}__lt': qvalue + variance}
            subquery |= basequery.filter(**posfilter)
        return subquery


class StrField(SearchField):
    VALID_OPERATORS = ('=', ':')

    def __init__(self, searchkey, modelfield=None, modifier=None, desc=None):
        super().__init__(searchkey, modelfield, modifier, desc)
        default_modifier = lambda valuestr, _: valuestr
        self.modifier = self.modifier or default_modifier
    
    def get_subquery(self, basequery, valuestr, operator=':', exclude=False):
        """ Returns list of subqueries for the given valuestr and operator. """
        if operator not in self.VALID_OPERATORS:
            raise SearchError(f"Invalid operator '{operator}' for string field")
        return super().get_subquery(basequery, valuestr, operator, exclude)
