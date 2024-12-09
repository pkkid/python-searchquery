#!/usr/bin/env python
# encoding: utf-8
import argparse, json, sys
from os.path import dirname, abspath
from django.apps import apps

# Make sure parent is in the systempath
sys.path.insert(0, dirname(dirname(abspath(__file__))))

from searchquery.django.search import DjangoSearch  # noqa
from tests import conftest as utils  # noqa


if __name__ == '__main__':
    cmdline = argparse.ArgumentParser(description='Test the PyParser')
    cmdline.add_argument('query', help='Search string to test with')
    cmdline.add_argument('-v', '--verbose', default=False, action='store_true', help='Show verbose output')
    opts = cmdline.parse_args()
    # Setup the Search object and get the queryset
    searchfields = utils.django_setup()
    Test = apps.get_model('__main__', 'Test')
    search = DjangoSearch(searchfields)
    results = search.get_queryset(Test.objects.all(), opts.query)
    # Show Verbose output if requested
    if opts.verbose:
        print('\n-- PARSER --')
        utils.pprint_parser_node(None, searchstr=opts.query)
        print('\n-- SEARCH METADATA --')
        print(json.dumps(search.meta, indent=2))
    # Show the resulting SQL query
    print('\n-- QUERY --' if opts.verbose else '')
    utils.pprint_django_sql(results)
