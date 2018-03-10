# Package tockloader.board_interface Documentation

## Class BoardInterface
Base class for interacting with hardware boards. All of the class functions
should be overridden to support a new method of interacting with a board.
### \_\_init\_\_
```py

def __init__(self, args)

```



Initialize self.  See help(type(self)) for accurate signature.


### bootloader\_is\_present
```py

def bootloader_is_present(self)

```



Check for the Tock bootloader. Returns `True` if it is present, `False`
if not, and `None` if unsure.


### determine\_current\_board
```py

def determine_current_board(self)

```



Figure out which board we are connected to. Most likely done by reading
the attributes. Doesn't return anything.


### enter\_bootloader\_mode
```py

def enter_bootloader_mode(self)

```



Get to a mode where we can read & write flash.


### erase\_page
```py

def erase_page(self, address)

```



Erase a specific page of internal flash.


### exit\_bootloader\_mode
```py

def exit_bootloader_mode(self)

```



Get out of bootloader mode and go back to running main code.


### flash\_binary
```py

def flash_binary(self, address, binary)

```



Write a binary to the address given.


### get\_all\_attributes
```py

def get_all_attributes(self)

```



Get all attributes on a board. Returns an array of attribute dicts.


### get\_apps\_start\_address
```py

def get_apps_start_address(self)

```



Return the address in flash where applications start on this platform.
This might be set on the board itself, in the command line arguments
to Tockloader, or just be the default.


### get\_attribute
```py

def get_attribute(self, index)

```



Get a single attribute. Returns a dict with two keys: `key` and `value`.


### get\_board\_arch
```py

def get_board_arch(self)

```



Return the architecture of the board we are connected to.


### get\_board\_name
```py

def get_board_name(self)

```



Return the name of the board we are connected to.


### get\_bootloader\_version
```py

def get_bootloader_version(self)

```



Return the version string of the bootloader. Should return a value
like `0.5.0`, or `None` if it is unknown.


### open\_link\_to\_board
```py

def open_link_to_board(self)

```



Open a connection to the board.


### read\_range
```py

def read_range(self, address, length)

```



Read a specific range of flash.


### set\_attribute
```py

def set_attribute(self, index, raw)

```



Set a single attribute.


### \_decode\_attribute
```py

def _decode_attribute(self, raw)

```




