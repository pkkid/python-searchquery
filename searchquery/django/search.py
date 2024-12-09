# encoding: utf-8
from django.db.models import Q
from ..basesearch import BaseSearch


class Search(BaseSearch):
    NORESULTS = Q(pk__in=[])
    NOOP = Q()

    pass
