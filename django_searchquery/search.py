# encoding: utf-8
import argparse, calendar, datetime, logging, re, shlex, timelib
from dateutil.relativedelta import relativedelta
from django.db.models import Q
from functools import reduce
from pyparsing import ParseResults
from pyparsing import CaselessKeyword, QuotedString
from pyparsing import Word, Group
from pyparsing import alphanums, printables
from pyparsing import delimitedList, oneOf, infixNotation, opAssoc
from pyparsing import Suppress, StringEnd, OneOrMore
from types import SimpleNamespace
log = logging.getLogger(__name__)

NONE = ('none', 'null')
OPERATORS = {'=':'__iexact', '>':'__gt', '>=':'__gte', '<=':'__lte', '<':'__lt', ':': '__icontains'}
# REVERSEOP = {'__gt':'__lte', '__gte':'__lt', '__lte':'__gt', '__lt':'__gte'}
# STOPWORDS = ('and', '&&', '&', 'or', '||', '|')
MONTHNAMES = [m.lower() for m in list(calendar.month_name)[1:] + list(calendar.month_abbr)[1:] + ['sept']]
DEFAULT_MODIFIER = lambda value: value

FIELDTYPES = SimpleNamespace()
FIELDTYPES.BOOL = 'bool'
FIELDTYPES.DATE = 'date'
FIELDTYPES.NUM = 'numeric'
FIELDTYPES.STR = 'string'

# PyParse Variables
AND,OR,IN,NOT = map(CaselessKeyword, 'and or in not'.split())
NOTIN = CaselessKeyword('not in')
LISTVALUES = 'listValues'
SEARCHCOLUMN = 'SearchColumn'
SEARCHCOLUMNIN = 'SearchColumnIn'
SEARCHALLCOLUMNS = 'SearchAllColumns'
MULTIQUERYWITHOP = 'multiQueryWithOp'


class UnaryOperator:
    def __init__(self, tokens):
        self.operator = tokens[0][0]
        self.operands = [tokens[0][1]]

class BinaryOperator:
    def __init__(self, tokens):
        self.operator = tokens[0][1]
        self.operands = tokens[0][::2]


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
    
    @classmethod
    def parser(cls):
        """ Returns the PyParse object we'll pass the search string to. """
        # Basic Value Search (no column specified)
        basicValue = Word(printables, excludeChars=r'(,) \'"')
        quoteValue = (QuotedString("'", escChar='\\') | QuotedString('"', escChar='\\'))
        singleValue = (basicValue | quoteValue)
        # Column Search (column <op> value)
        operator = oneOf(OPERATORS.keys())
        column = Word(alphanums+'_')
        listValues = delimitedList(singleValue, delim=',').setResultsName(LISTVALUES)
        listValues = Suppress('(') + Group(listValues) + Suppress(')')
        # Single Search Query
        singleQuery = Group(
            (column + operator + singleValue).setResultsName(SEARCHCOLUMN)
            | (column + (IN | NOTIN) + listValues).setResultsName(SEARCHCOLUMNIN)
            | singleValue.setResultsName(SEARCHALLCOLUMNS)
        )
        # Mutliple Search Queries (joined by operators)
        multiQuery = infixNotation(singleQuery, [
            (NOT, 1, opAssoc.RIGHT, UnaryOperator),
            (AND, 2, opAssoc.LEFT, BinaryOperator),
            (OR, 2, opAssoc.LEFT, BinaryOperator),
        ]).setResultsName(MULTIQUERYWITHOP)
        return OneOrMore(multiQuery) + StringEnd()


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


def parseNodeTest(node, indent=0):
    """ Tests the parser with the search string. """
    indentstr = ' ' * indent
    if isinstance(node, ParseResults):
        print(f'{indentstr}{node.getName()}:')
        for child in node:
            parseNodeTest(child, indent+2)
    elif isinstance(node, (UnaryOperator, BinaryOperator)):
        print(f'{indentstr}{node.operator}:')
        for child in node.operands:
            parseNodeTest(child, indent+2)
    else:
        print(f'{indentstr}{node}')


if __name__ == '__main__':
    # Test the parser
    # python search2.py "hello foo not in (bar, baz, 'Honey, dew') AND eat OR (it AND bar) AND foo=bar OR (eatme AND 'soda bar')"
    parser = argparse.ArgumentParser(description='Test the Search Parser')
    parser.add_argument('query', help='Search string to test with')
    searchstr = parser.parse_args().query
    parseNodeTest(Search.parser().parseString(searchstr))
