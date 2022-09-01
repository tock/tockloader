# Package tockloader.helpers Documentation


Various helper functions that tockloader uses. Mostly for interacting with
users in a nice way.

## Class ListToDictAction
`argparse` action to convert `[['key', 'val'], ['key2', 'val2']]` to
`{'key': 'val', 'key2': 'val2'}`.

This will also do the following conversions:
- `[[]]` -> `{}`
- `[['k': 'v'], []]` -> `{'k': 'v'}`
- `[['k': 'v'], ['']]` -> `{'k': 'v'}`
- `[['k': 'v'], ['a']]` -> `{'k': 'v', 'a': ''}`
### \_\_init\_\_
```py

def __init__(self, option_strings, dest, nargs=None, const=None, default=None, type=None, choices=None, required=False, help=None, metavar=None)

```



Initialize self.  See help(type(self)) for accurate signature.


### format\_usage
```py

def format_usage(self)

```



### \_\_call\_\_
```py

def __call__(self, parser, namespace, values, option_string=None)

```



Call self as a function.


### \_\_repr\_\_
```py

def __repr__(self)

```



Return repr(self).


### \_get\_args
```py

def _get_args(self)

```



### \_get\_kwargs
```py

def _get_kwargs(self)

```





### menu
```py

def menu(options, *, return_type, default_index=0, prompt='Which option? ', title='')

```



Present a menu of choices to a user

`options` should be a like-list object whose iterated objects can be coerced
into strings.

`return_type` must be set to one of
  - "index" - for the index into the options array
  - "value" - for the option value chosen

`default_index` is the index to present as the default value (what happens
if the user simply presses enter). Passing `None` disables default
selection.


### menu\_new
```py

def menu_new(options, *, return_type, default_index=None, prompt='', title='')

```



Present an interactive menu of choices to a user.

`options` should be a like-list object whose iterated objects can be coerced
into strings.

`return_type` must be set to one of:
  - "index" - for the index into the options array
  - "value" - for the option value chosen

`default_index` is the index to present as the default value (what happens
if the user simply presses enter). Passing `None` disables default
selection.


### plural
```py

def plural(value)

```



Return '' or 's' based on whether the `value` means a string should have
a plural word.

`value` can be a list or a number. If the number or the length of the list
is 1, then '' will be returned. Otherwise 's'.


### set\_terminal\_title
```py

def set_terminal_title(title)

```



### set\_terminal\_title\_from\_port
```py

def set_terminal_title_from_port(port)

```



Set the title of the user's terminal for Tockloader.


### set\_terminal\_title\_from\_port\_info
```py

def set_terminal_title_from_port_info(info)

```



Set a terminal title from a `pyserial` object.


### text\_in\_box
```py

def text_in_box(string, box_width)

```



Return a string like:
```
┌───────────────┐
│ str           │
└───────────────┘
```

