#!/usr/bin/env python
# encoding: utf-8
# Sets up a fake Django application and passes a search string
# from the command line. It will print out the parser result as well
# as the resulting SQL query.
#
# Testing requires additional requirements:
#   pip install django sqlparse pygments pytz
#
# Example Test Call:
#  python test.py -- "testpath:foo -path:failcount running in (true, 1) ORDER BY -path, date"
#
# If looking at this as an example, you should only need the following:
#   1. Define the SEARCHFIELDS to reference your model fields.
#   2. Define search = Search(SEARCHFIELDS)
#   3. Call search.get_queryset(Test.objects.all(), opts.query)
#
import json, re
import argparse, pytz, django
from django.conf import settings
from django.core.exceptions import EmptyResultSet
from django.db import models
from searchquery import modifiers as mods
from searchquery.parser import BinaryOperator, UnaryOperator, SearchString
from searchquery.django.search import Search
from searchquery.django import searchfields as sf
from pygments import formatters, highlight, lexers
from pyparsing.exceptions import ParseException
from pyparsing import ParseResults
import sqlparse

APPNAME = '__main__'
TZINFO = pytz.timezone('America/New_York')
settings.configure(
    TIME_ZONE='America/New_York',
    INSTALLED_APPS=[APPNAME],
    DATABASES={'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:'
    }}
)
django.setup()


class Environment(models.Model):
    """ Tests defined in pytest-automation. """
    branch = models.CharField(max_length=256)
    build = models.IntegerField()


class Test(models.Model):
    """ Tests defined in pytest-automation. """
    testpath = models.CharField(max_length=256, unique=True, db_index=True)
    filepath = models.CharField(max_length=256)
    title = models.CharField(max_length=256, null=True)
    date = models.DateTimeField()
    runtime = models.IntegerField()
    failcount = models.IntegerField()
    running = models.BooleanField()
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE)


SEARCHFIELDS = [
    sf.StrField('testpath', 'testpath'),
    sf.StrField('path', 'filepath'),
    sf.StrField('title', 'title'),
    sf.DateField('date', 'date'),
    sf.NumField('runtime', 'runtime', mod=mods.duration),
    sf.NumField('failcount', 'failcount'),
    sf.BoolField('running', 'running'),
    sf.StrField('branch', 'environment__branch'),
    sf.NumField('build', 'environment__build'),
]


def pprint_parser_node(node, indent=0, searchstr=None):
    """ Prints a parsed search string. """
    try:
        node = node or SearchString.parseString(searchstr)
        indentstr = ' ' * indent
        if isinstance(node, ParseResults):
            print(f'{indentstr}{node.getName()}:')
            for child in node:
                pprint_parser_node(child, indent+2)
        elif isinstance(node, (UnaryOperator, BinaryOperator)):
            print(f'{indentstr}{node.operator}:')
            for child in node.operands:
                pprint_parser_node(child, indent+2)
        else:
            print(f'{indentstr}{node}')
    except ParseException as err:
        print(err)


def pprint_sql(queryset):
    """ Format the SQL query for display. """
    try:
        query = str(queryset.query).replace(APPNAME, 'app')
        query = re.sub(r'SELECT(.+?)FROM', 'SELECT * FROM', query)
        formatted = sqlparse.format(query, reindent=True)
        formatted = formatted.replace(' OR ', '\n  OR ')
        formatted = formatted.replace(' AND ', '\n  AND ')
        formatted = formatted.replace(" ESCAPE '\\'", '')
        formatted = '\n'.join([x for x in formatted.split('\n') if x.strip()])
        formatted = highlight(formatted, lexers.SqlLexer(), formatters.TerminalFormatter())
        indent = 0
        for line in formatted.split('\n'):
            print(f'{"  "*indent}{line}')
            indent += line.count('(')
            indent -= line.count(')')
    except EmptyResultSet:
        print('No query generated')


if __name__ == '__main__':
    cmdline = argparse.ArgumentParser(description='Test the PyParser')
    cmdline.add_argument('query', help='Search string to test with')
    cmdline.add_argument('-v', '--verbose', default=False, action='store_true', help='Show verbose output')
    opts = cmdline.parse_args()
    # Setup the Search object and get the queryset
    search = Search(SEARCHFIELDS)
    results = search.get_queryset(Test.objects.all(), opts.query)
    # Show Verbose output if requested
    if opts.verbose:
        print('\n-- PARSER --')
        pprint_parser_node(None, searchstr=opts.query)
        print('\n-- Search Metadata --')
        print(json.dumps(search.meta, indent=2))
    # Show the resulting SQL query
    print('\n-- QUERY --' if opts.verbose else '')
    pprint_sql(results)
    
