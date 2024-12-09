# encoding: utf-8
import pytest, re, sqlparse
from pygments import formatters, highlight, lexers
from pyparsing import ParseResults
from pyparsing.exceptions import ParseException
from searchquery import modifiers as mods
from searchquery.django import searchfields as sf
from searchquery.parser import BinaryOperator, UnaryOperator, SearchString


@pytest.fixture(autouse=True, scope="session")
def django_setup_fixture():
    return django_setup()


def django_setup():
    """ Setup fake Django environment with two tables Environment & Test. """
    import django
    from django.conf import settings
    from django.db import models

    settings.configure(
        TIME_ZONE='America/New_York',
        INSTALLED_APPS=['__main__'],
        DATABASES={'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:'
        }}
    )
    django.setup()

    SEARCHFIELDS = [
        sf.StrField('testpath', 'testpath', generic=True),
        sf.StrField('path', 'filepath'),
        sf.StrField('title', 'title'),
        sf.DateField('date', 'date'),
        sf.NumField('runtime', 'runtime', mod=mods.duration),
        sf.NumField('failcount', 'failcount'),
        sf.BoolField('running', 'running'),
        sf.StrField('branch', 'environment__branch'),
        sf.NumField('build', 'environment__build'),
    ]

    class Environment(models.Model):
        """ Fake Environment object. """
        branch = models.CharField(max_length=256)
        build = models.IntegerField()

        class Meta:
            app_label = '__main__'

    class Test(models.Model):
        """ Fake Test object. """
        testpath = models.CharField(max_length=256, unique=True, db_index=True)
        filepath = models.CharField(max_length=256)
        title = models.CharField(max_length=256, null=True)
        date = models.DateTimeField()
        runtime = models.IntegerField()
        failcount = models.IntegerField()
        running = models.BooleanField()
        environment = models.ForeignKey(Environment, on_delete=models.CASCADE)

        class Meta:
            app_label = '__main__'

    return SEARCHFIELDS


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


def pprint_django_sql(queryset):
    """ Format the SQL query for display. """
    from django.core.exceptions import EmptyResultSet
    try:
        query = str(queryset.query).replace('__main__', 'app')
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
