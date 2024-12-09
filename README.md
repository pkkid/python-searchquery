# django-querysearch
Simple query search module for Django or Sqlalchemy

## Installation
```
pip install git+https://github.com/pkkid/python-searchquery.git
```

## Usage
Once you define the searchable columns, the user will be able to search the 
result set using a friendly syntax. The module will parse the search string and
return a Query object.

```python
from searchquery import searchfields as sf
from myapp.applications.models import Application

SEARCH_FIELDS = [
    sf.StrField(searchkey='name', modelfield='name'),
    sf.NumField(searchkey='age', modelfield='age'),
    sf.DateField(searchkey='date', modelfield='date'),
]

basequery = Application.objects.all()
seatchstr = 'age>30 date>"2 weeks ago" name=Michael'
search = Search(basequery, SEARCH_FIELDS, seatchstr)
results = search.queryset()
```

## Search Syntax
### Basic Search
All searches are case insensative. Filters are broken apart using a space or the
keywords `and` and `or`. A search of `foo bar` would search all string colums for
the text containing foo and bar. Only results containing both strings would be
displayed. Use quotes to join two words as a single search. A search of
`"foo bar"` would search for an exact match containing "foo bar" together as one
phrase. Use a minus sign `-` or the keyword `not` to exclude results from a search.

* `John Doe` searches all string columns for the words john or doe.
* `"John Doe"` searches for the exact match "john doe".
* `-michael` excludes all rows that contain the word michael in any tring column.

### Specifing a Column
You may optionally target a specific column in your search. Use colon `:` or
equal `=` to seperate the column name and search string. Colon searches for
a value that contains the search text while equal searches for an exact
case-insensative match.

* `error:assertion` searches the error column for a string containing 'assertion'.
* `error="unsupported operand"` searches for the exact match 'unsupported operand`.

### Infix Notation
Infix notation is supported with the keywords `and`, `or`, and `not` as well
as using parenthesis where needed. If there is no keyword specified between
two search strings, an implicit and is inferred.

* `age>30 -foobar` all rows where age>30 and no string columns contain "foo"
* `age > 30 and (not foobar)` the exact same search as above.

### Numeric Columns
Numeric columns can be searched using basic math operations. Available operators
are: `> >= = <= <` and a special contains `:` operator.

* `age >= 200` search all rows with age >= 20
* `price=60` search the exact match of 60.
* `price:60` search all prices >=60 and <61 (60.45 would match as it contains 60).

### Date Columns
Dates can be searched using almost any human readable string. Remember to include
quotes when you have spaces. Timlib.strtodatetime() is used to convert the date
string to datetime object which is then searched. People often refer to dates as
a min and max with a single word. For example, `yesterday` refers to a min date
of the beginning of the day yesterday and a max date of the end of the day. This
is accounted for when searching dates.

* `date > "1 week ago"` search rows with date > whatever one week ago is.
* `date = "last month"` search rows between in the min and max dates of last month.
* `date >= "Feb 2024"` search rows with a date >= 2024-02-01.

### Search None
The keywords `null` and `none` will be treated as such. This can be useful when
simply searching for the existence of values.

* `-error:none` search all rows that have an error.
