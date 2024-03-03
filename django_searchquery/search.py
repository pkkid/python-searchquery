# encoding: utf-8
import logging
from functools import reduce
from pyparsing import ParseResults
from pyparsing.exceptions import ParseException
from . import parser, searchfields, utils
from .exceptions import SearchError
log = logging.getLogger(__name__)


class Search:
    
    def __init__(self, basequery, fields, searchstr, tzinfo=None):
        self.error = None                               # List of errors to display
        self.basequery = basequery                      # Base queryset to filter in Search
        self.fields = {f.searchkey:f for f in fields}   # Field objects to filter on
        self.searchstr = searchstr                      # Orignal search string
        self.tzinfo = tzinfo                            # TZ info for datetime fields
    
    def __str__(self):
        return f'<{self.__class__.__name__}:{self.basequery.model.__name__}>'

    @property
    def meta(self):
        """ Returns metadata about this Search object. """
        result = {}
        result['fields'] = {k:f.desc for k,f in self.fields.items()}
        if self.searchstr:
            result['query'] = self.searchstr or ''
            # result['filters'] = self.filterstrs
            if self.error:
                result['error'] = self.error
        return result

    def queryset(self, node=None, exclude=False):
        """ Recursivly builds the django queryset. """
        try:
            subqueries = []
            node = node or parser.SearchString.parseString(self.searchstr)
            if isinstance(node, ParseResults):
                queryfunc = getattr(self, f'_qs_{node.getName()}')
                subqueries.append(queryfunc(node, exclude))
            elif isinstance(node, (parser.UnaryOperator, parser.BinaryOperator)):
                queryfunc = getattr(self, f'_qs_{node.operator}')
                subqueries.append(queryfunc(node, exclude))
            return self._merge_subqueries(subqueries)
        except ParseException as err:
            self.error = f"Unknown symbol '{err.line[err.loc]}' at position {err.loc}"
        except SearchError as err:
            self.error = str(err)
        return self.basequery.none()
        
    def _get_field(self, searchkey):
        """ Returns the field object for the given searchkey. """
        field = self.fields.get(searchkey)
        if not field:
            raise SearchError(f"Unknown field '{searchkey}'")
        return field
    
    def _merge_subqueries(self, subqueries, andjoin=True):
        """ Merge all subqueries into a single query. """
        # The logic here can be a bit tangled up as the method to join queries
        # with pretty tightly coupled with exlude. In short, if we are excluding,
        # we generally want to join with AND (unless were doing a bitwise AND,
        # then its backwards).
        if andjoin:
            return reduce(lambda x,y: x & y, subqueries)
        return reduce(lambda x,y: x | y, subqueries)

    def _qs_root(self, node, exclude=False):
        """ Iterate through each subquery. """
        return self.queryset(node[0], exclude)
        # subqueries = []
        # for childnode in node:
        #     subqueries.append(self.queryset(childnode, exclude))
        # return reduce(lambda x,y: x & y, subqueries)
    
    def _qs_and(self, node, exclude=False):
        """ Join two queries with AND. """
        subqueries = []
        for childnode in node.operands:
            subqueries.append(self.queryset(childnode, exclude))
        return self._merge_subqueries(subqueries, not exclude)
    
    def _qs_or(self, node, exclude=False):
        """ Join two queries with AND. """
        subqueries = []
        for childnode in node.operands:
            subqueries.append(self.queryset(childnode, exclude))
        return self._merge_subqueries(subqueries, exclude)
    
    def _qs_not(self, node, exclude=False):
        """ Join two queries with AND. """
        subqueries = []
        exclude = not exclude
        for childnode in node.operands:
            print(childnode)
            subqueries.append(self.queryset(childnode, exclude))
        return reduce(lambda x,y: x | y, subqueries)
    
    def _qs_search_column(self, node, exclude=False):
        """ Search a specific column for the specified string. """
        exclude = not exclude if len(node) == 4 else exclude
        searchkey, operator, valuestr = node[1:] if len(node) == 4 else node
        field = self._get_field(searchkey)
        return field.get_subquery(self.basequery, valuestr, operator, exclude)

    def _qs_search_column_in(self, node, exclude=False):
        """ Search a specific column contains one of many values. """
        # Careful! We could have double exclude here.
        subqueries = []
        exclude = not exclude if len(node) == 4 else exclude
        searchkey, operator, valuestrs = node[1:] if len(node) == 4 else node
        exclude = not exclude if operator == 'not in' else exclude
        field = self._get_field(searchkey)
        subquery = self.basequery
        for valuestr in valuestrs:
            subquery = field.get_subquery(self.basequery, valuestr, '=', exclude)
            subqueries.append(subquery)
        return self._merge_subqueries(subqueries, exclude)

    def _qs_search_all_columns(self, node, exclude=False):
        """ Search all columns for the specified string. """
        subqueries = []
        exclude = not exclude if len(node) == 2 else exclude
        valuestr = node[1] if len(node) == 2 else node[0]
        # Search string fields
        strfields = (f for f in self.fields.values() if isinstance(f, searchfields.StrField))
        for field in strfields:
            subquery = field.get_subquery(self.basequery, valuestr, ':', exclude)
            subqueries.append(subquery)
        # Search all num fields (if applicable)
        if utils.is_number(valuestr):
            numvaluestr = ''.join(node)
            numfields = (f for f in self.fields.values() if isinstance(f, searchfields.NumField))
            for field in numfields:
                subquery = field.get_subquery(self.basequery, numvaluestr, ':', exclude)
                subqueries.append(subquery)
        return self._merge_subqueries(subqueries, exclude)
