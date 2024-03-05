#!/usr/bin/env python
# encoding: utf-8
# Sets up a fake Django application and passes a search string
# from the command line. It will print out the parser result as well
# as the resulting SQL query.
#
# Testing requires additional requirements:
#   pip install django sqlparse pygments pytz
#
# If looking at this as an example, you should only need the following:
#   1. Define the SEARCHFIELDS to reference your model fields.
#   2. Optionally setup tzinfo to avoid naive datetimes.
#   3. Define the basequery to be passed to the Ssarch object.
#   4. Call search.Search(basequery, fields, searchstr, tzinfo=None)
import json, re
import argparse, pytz, django
from django.conf import settings
from django.core.exceptions import EmptyResultSet
from django.db import models
from django_searchquery import modifiers as mods
from django_searchquery.parser import BinaryOperator, UnaryOperator, SearchString
from django_searchquery.search import Search
from django_searchquery import searchfields as sf
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
    opts = cmdline.parse_args()
    # Setup the parser and display the output
    print('\n-- PARSER --')
    pprint_parser_node(None, searchstr=opts.query)
    # Setup and run the search
    print('\n-- Search Metadata --')
    search = Search(SEARCHFIELDS, opts.query)
    results = Test.objects.filter(search.qobject)
    print(json.dumps(search.meta, indent=2))
    print('\n-- QUERY --')
    pprint_sql(results)
    
