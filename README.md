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
from django_searchquery import searchfields as sf
from myapp.applications.models import Application

SEARCH_FIELDS = [
    sf.StrField(searchkey='name', modelfield='name'),
    sf.NumField(searchkey='age', modelfield='age'),
    sf.DateField(searchkey='date', modelfield='date'),
]

basequeryset = Application.objects.all()
search = Search(basequeryset, SEARCH_FIELDS, 'age>30 date>"2 weeks ago" name=Michael')
results = search.queryset()
```

