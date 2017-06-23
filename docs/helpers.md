# Package tockloader.helpers Documentation


Various helper functions that tockloader uses. Mostly for interacting with
users in a nice way.

### menu
```py

def menu(options, *, return_type, default_index=0, prompt='Which option? ')

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

