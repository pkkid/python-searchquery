# encoding: utf-8
from pyparsing import CaselessKeyword, QuotedString
from pyparsing import Group, Literal, Word
from pyparsing import alphanums, printables
from pyparsing import delimitedList, oneOf, infixNotation, opAssoc
from pyparsing import Suppress, StringEnd, Optional, ZeroOrMore

OPERATORS = '= != > >= <= < :'
ORDERBY = Suppress(CaselessKeyword('order by'))
AND,OR,IN,NOT = map(CaselessKeyword, 'and or in not'.split())
NOTIN = CaselessKeyword('not in')
NEG = Literal('-')

class UnaryOperator:
    def __init__(self, tokens):
        self.operator = tokens[0][0]
        self.operands = [tokens[0][1]]

class BinaryOperator:
    def __init__(self, tokens):
        self.operator = tokens[0][1]
        self.operands = tokens[0][::2]


# Basic Value Search (no column specified)
basicValue = Word(printables, excludeChars=r'\'"(,)')
quoteValue = (QuotedString("'", escChar='\\') | QuotedString('"', escChar='\\'))
singleValue = (basicValue | quoteValue)

# Column Search (column <op> value)
column = Word(alphanums+'_')
listValues = delimitedList(singleValue, delim=',').setResultsName('list_values')
listValues = Suppress('(') + Group(listValues) + Suppress(')')

# Single Search Query
searchColumn = (Optional(NEG) + column + oneOf(OPERATORS) + singleValue).setResultsName('search_column')
searchColumnIn = (Optional(NEG) + column + (IN | NOTIN) + listValues).setResultsName('search_column_in')
searchAllColumns = (Optional(NEG) + singleValue).setResultsName('search_all_columns')
singleQuery = Group(searchColumn | searchColumnIn | searchAllColumns)

# Root Queries (joined by operators)
# ~ORDERBY here makes the OneOrMore not greedy
rootQuery = ZeroOrMore(~ORDERBY + infixNotation(singleQuery, [
    (NOT, 1, opAssoc.RIGHT, UnaryOperator),
    (AND, 2, opAssoc.LEFT, BinaryOperator),
    (OR, 2, opAssoc.LEFT, BinaryOperator),
])).setResultsName('root')

# Order By
orderByColumn = Group(Optional(NEG) + column).setResultsName('orderby')
orderBy = Optional(ORDERBY + delimitedList(orderByColumn, delim=','))

# SearchString - Final Parser object
SearchString = rootQuery + orderBy + StringEnd()
