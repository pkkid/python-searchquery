# encoding: utf-8
import logging
from functools import reduce
from pyparsing import ParseResults
from pyparsing.exceptions import ParseException
from . import parser, searchfields, utils
from .exceptions import SearchError
log = logging.getLogger(__name__)


class BaseSearch:
    NORESULTS = None    # Queryset will never have results; defined in subclass
    NOOP = None         # Queryset that does nothing; defined in subclass
    
    def __init__(self, fields, allow_partial_fieldnames=True):
        self.fields = {f.search_key.lower():f for f in fields}      # Field objects to filter on
        self.allow_partial_fieldnames = allow_partial_fieldnames    # Allow specifying partial field names
        self._searchstr = ''    # Last searchstr used
        self._qobject = None    # Q object from last search
        self._order_by = []     # Order By args from last search
        self._error = None      # Error message from last search
    
    def __str__(self):
        return f'<{self.__class__.__name__}>'
    
    def get_queryset(self, queryset, searchstr):
        """ Given a base queryset and a searchstr, return a new filtered queryset. """
        self._searchstr = searchstr     # Save last searchstr
        self._order_by = []             # Reset order_by
        self._error = None              # Reset error message
        if searchstr and searchstr.strip():
            qobject = self._get_qobject(searchstr)
            queryset = queryset.filter(qobject)
        if self._order_by:
            queryset = queryset.order_by(*self._order_by)
        return queryset
    
    @property
    def meta(self):
        """ Returns metadata about the last search. Generally you want
            to be calling this after get_queryset.
        """
        result = {}
        result['fields'] = {}
        for key, field in self.fields.items():
            stype = field.__class__.__name__.replace('Field', '').lower()
            result['fields'][key] = f'{field.desc} ({stype})'
        if self._searchstr:
            result['query'] = self._searchstr or ''
            if self._error:
                result['error'] = self._error
        return result
    
    def _get_qobject(self, node=None, exclude=False):
        """ Recursivly builds the django qobject. """
        try:
            qobjects = []
            if isinstance(node, str):
                node = parser.SearchString.parseString(node)
            if isinstance(node, ParseResults):
                queryfunc = getattr(self, f'_qs_{node.getName()}')
                qobjects.append(queryfunc(node, exclude))
            elif isinstance(node, (parser.UnaryOperator, parser.BinaryOperator)):
                queryfunc = getattr(self, f'_qs_{node.operator}')
                qobjects.append(queryfunc(node, exclude))
            self._qobject = utils.merge_qobjects(qobjects)
            return self._qobject
        except ParseException as err:
            self._error = f"Unknown symbol '{err.line[err.loc]}' at position {err.loc}"
        except SearchError as err:
            self._error = str(err)
        # return no results
        self._qobject = self.NORESULTS
        return self._qobject
        
    def _get_field(self, searchkey):
        """ Returns the field object for the given searchkey. """
        key = searchkey.lower()
        field = self.fields.get(key)
        if field:
            return field
        if self.allow_partial_fieldnames:
            matches = [f for k,f in self.fields.items() if key in k]
            if len(matches) == 1:
                return matches[0]
            if len(matches) >= 2:
                raise SearchError(f"Ambiguous field '{searchkey}'")
        raise SearchError(f"Unknown field '{searchkey}'")

    def _qs_root(self, node, exclude=False):
        """ Iterate through each child node. """
        qobjects = []
        for childnode in node:
            qobjects.append(self._get_qobject(childnode, exclude))
        return utils.merge_qobjects(qobjects, not exclude)
    
    def _qs_and(self, node, exclude=False):
        """ Join two queries with AND. """
        qobjects = []
        for childnode in node.operands:
            qobjects.append(self._get_qobject(childnode, exclude))
        return utils.merge_qobjects(qobjects, not exclude)
    
    def _qs_or(self, node, exclude=False):
        """ Join two queries with AND. """
        qobjects = []
        for childnode in node.operands:
            qobjects.append(self._get_qobject(childnode, exclude))
        return utils.merge_qobjects(qobjects, exclude)
    
    def _qs_not(self, node, exclude=False):
        """ Join two queries with AND. """
        qobjects = []
        exclude = not exclude
        for childnode in node.operands:
            qobjects.append(self._get_qobject(childnode, exclude))
        return reduce(lambda x,y: x | y, qobjects)
    
    def _qs_search_column(self, node, exclude=False):
        """ Search a specific column for the specified string. """
        exclude = not exclude if len(node) == 4 else exclude
        searchkey, operator, valuestr = node[1:] if len(node) == 4 else node
        field = self._get_field(searchkey)
        return field.get_subquery(valuestr, operator, exclude)

    def _qs_search_column_in(self, node, exclude=False):
        """ Search a specific column contains one of many values. """
        # Careful! We could have double exclude here.
        exclude = not exclude if len(node) == 4 else exclude
        searchkey, operator, valuestrs = node[1:] if len(node) == 4 else node
        exclude = not exclude if operator == 'not in' else exclude
        field = self._get_field(searchkey)
        qobjects = []
        for valuestr in valuestrs:
            qobject = field.get_subquery(valuestr, '=', exclude)
            qobjects.append(qobject)
        return utils.merge_qobjects(qobjects, exclude)

    def _qs_search_all_columns(self, node, exclude=False):
        """ Search all columns for the specified string. """
        qobjects = []
        exclude = not exclude if len(node) == 2 else exclude
        valuestr = node[1] if len(node) == 2 else node[0]
        # Search string fields
        strfields = (f for f in self.fields.values() if isinstance(f, searchfields.StrField))
        strfields = (f for f in strfields if f.generic is True)
        for field in strfields:
            subquery = field.get_subquery(valuestr, ':', exclude)
            qobjects.append(subquery)
        # Search all num fields (if applicable)
        if utils.is_number(valuestr):
            numvaluestr = ''.join(node)
            numfields = (f for f in self.fields.values() if isinstance(f, searchfields.NumField))
            numfields = (f for f in numfields if f.generic)
            for field in numfields:
                subquery = field.get_subquery(numvaluestr, ':', exclude)
                qobjects.append(subquery)
        return utils.merge_qobjects(qobjects, exclude) if qobjects else self.NORESULTS
    
    def _qs_orderby(self, node, exclude=False):
        """ Save the order_by arg to self.order_by. """
        desc = '-' if len(node) == 2 else ''
        searchkey = node[1] if len(node) == 2 else node[0]
        field = self._get_field(searchkey)
        self._order_by.append(f'{desc}{field.model_field}')
        return self.NOOP
