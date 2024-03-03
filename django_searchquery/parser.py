# encoding: utf-8
import sys
from pyparsing import ParseResults
from pyparsing import CaselessKeyword, QuotedString
from pyparsing import Word, Group
from pyparsing import alphanums, printables
from pyparsing import delimitedList, oneOf, infixNotation, opAssoc
from pyparsing import Suppress, StringEnd, OneOrMore


class UnOp:
    def __init__(self, tokens):
        self.operator = tokens[0][0]
        self.operands = [tokens[0][1]]

class BinOp:
    def __init__(self, tokens):
        self.operator = tokens[0][1]
        self.operands = tokens[0][::2]


EXCLUDECHARS = r'(,) \'"'

# Keywords
AND = CaselessKeyword('AND')
OR = CaselessKeyword('OR')
IN = CaselessKeyword('IN')
NOT = CaselessKeyword('NOT')
NOTIN = CaselessKeyword('NOT IN')

# Basic Value Search (no column specified)
basicValue = Word(printables, excludeChars=EXCLUDECHARS)
quoteValue = (QuotedString("'", escChar='\\') | QuotedString('"', escChar='\\'))
singleValue = (basicValue | quoteValue)

# Column Search (column <op> value)
operator = oneOf(': = != < > >= <=')
column = Word(alphanums+'_')
multiValues = delimitedList(singleValue, delim=',').setResultsName('values')


# Single Search
singleQuery = Group(
    (column + operator + singleValue).setResultsName('SearchColumn')
    | (column + (IN | NOTIN) + Suppress('(') + Group(multiValues) + Suppress(')')).setResultsName('SearchColumnIn')
    | singleValue.setResultsName('SearchAllColumns')
)

# multiQueryWithSpace = OneOrMore(singleQuery).setResultsName('multiQueryWithSpace')
multiQueryWithOp = infixNotation(singleQuery, [
    (NOT, 1, opAssoc.RIGHT, UnOp),
    (AND, 2, opAssoc.LEFT, BinOp),
    (OR, 2, opAssoc.LEFT, BinOp),
]).setResultsName('multiQueryWithOp')
searchQuery = OneOrMore(multiQueryWithOp) + StringEnd()


def parseResult(node, indent=0):
    indentstr = ' ' * indent
    if isinstance(node, ParseResults):
        print(f'{indentstr}{node.getName()}:')
        for child in node:
            parseResult(child, indent+2)
    elif isinstance(node, (UnOp, BinOp)):
        print(f'{indentstr}{node.operator}:')
        for child in node.operands:
            parseResult(child, indent+2)
    else:
        print(f'{indentstr}{node}')


if __name__ == "__main__":
    tests = [
        'singleword',                       # 0
        'multiple AND words',               # 1
        'allow_underscore',                 # 2
        'random\'_quote_"inside',           # 3 err
        "'single quoted value'",            # 4
        '"double quoted value"',            # 5
        '"escaped \\"\'quote"',             # 6
        '"parens(need) quotes"',            # 7
        'parens(no) quotes',                # 8 err
        'foo = bar',                        # 9
        'foo=bar',                          # 10
        '(foo, bar)',                       # 11 err
        'foo in (bar, baz)',                # 12
        'foo in (bar, baz, "Honey dew")',   # 13
        'foo >= moon',                      # 14
        'hello foo not in (bar, baz, "Honey dew") AND eat OR (it AND bar) AND foo=bar OR (eatme AND "soda bar")',   # 15
        'implicit foobar query foo=bar AND likeme',      # 16
    ]
    # searchQuery.run_tests(tests[8])
    result = searchQuery.parseString(tests[int(sys.argv[1])])
    parseResult(result)
