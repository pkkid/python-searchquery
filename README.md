# django-querysearch
Simple query search module for Django

## Installation
```
pip install git+https://github.com/pkkid/django-searchquery.git
```

## Usage
Once you define the searchable columns, the user will be able to search the 
result set using a friendly syntax. The module will parse the search string and
return a Djazngo Query object.

```python
from django_searchquery.search import FIELDTYPES, SearchField
from myapp.applications.models import Application

SEARCH_FIELDS = [
    SearchField('name', FIELDTYPES.STR, 'name'),
    SearchField('age', FIELDTYPES.NUM, 'age'),
    SearchField('date', FIELDTYPES.NUM, 'date'),
]

basequeryset = Application.objects.all()
search = Search(basequeryset, SEARCH_FIELDS, 'age>30 date>"2 weeks ago" name=Michael')
results = search.queryset()
```

