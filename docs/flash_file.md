# Package tockloader.flash_file Documentation


Interface to a board's flash file. This module does not directly interface to a
proper board, but can be used to manipulate a board's flash dump.

## Class FlashFile
Implementation of `BoardInterface` for flash files.
### \_\_init\_\_
```py

def __init__(self, args)

```



Initialize self.  See help(type(self)) for accurate signature.


### attached\_board\_exists
```py

def attached_board_exists(self)

```



For this particular board communication channel, check if there appears
to be a valid board attached to the host that tockloader can communicate
with.


### bootloader\_is\_present
```py

def bootloader_is_present(self)

```



Check for the Tock bootloader. Returns `True` if it is present, `False`
if not, and `None` if unsure.


### clear\_bytes
```py

def clear_bytes(self, address)

```



Clear at least one byte starting at `address`.

This API is designed to support "ending the linked list of apps", or
clearing flash enough so that the flash after the last valid app will
not parse as a valid TBF header.

Different chips with different mechanisms for writing/erasing flash make
implementing specific erase behavior difficult. Instead, we provide this
rough API, which is sufficient for the task of ending the linked list,
but doesn't guarantee exactly how many bytes after address will be
cleared, or how they will be cleared.


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


### get\_kernel\_version
```py

def get_kernel_version(self)

```



Return the kernel ABI version installed on the board. If the version
cannot be determined, return `None`.


### get\_page\_size
```py

def get_page_size(self)

```



Return the size of the page in bytes for the connected board.


### open\_link\_to\_board
```py

def open_link_to_board(self)

```



Open a link to the board by opening the flash file for reading and
writing.


### print\_known\_boards
```py

def print_known_boards(self)

```



Display the boards that have settings configured in tockloader.


### read\_range
```py

def read_range(self, address, length)

```



Read a specific range of flash.

If this fails for some reason this should return an empty binary array.


### run\_terminal
```py

def run_terminal(self)

```



### set\_attribute
```py

def set_attribute(self, index, raw)

```



Set a single attribute.


### set\_start\_address
```py

def set_start_address(self, address)

```



Set the address the bootloader jumps to to start the actual code.


### translate\_address
```py

def translate_address(self, address)

```



Translate an address from MCU address space to the address required for
the board interface. This is used for boards where the address passed to
the board interface is not the address where this region is exposed in
the MCU address space. This method must be called from the board
interface implementation prior to memory accesses.


### \_align\_and\_stretch\_to\_page
```py

def _align_and_stretch_to_page(self, address, binary)

```



Return a new (address, binary) that is a multiple of the page size
and is aligned to page boundaries.


### \_configure\_from\_known\_boards
```py

def _configure_from_known_boards(self)

```



If we know the name of the board we are interfacing with, this function
tries to use the `KNOWN_BOARDS` array to populate other needed settings
if they have not already been set from other methods.

This can be used in multiple locations. First, it is used when
tockloader first starts because if a user passes in the `--board`
argument then we know the board and can try to pull in settings from
KNOWN_BOARDS. Ideally, however, the user doesn't have to pass in any
arguments, but then we won't know what board until after we have had a
chance to read its attributes. The board at least needs the "board"
attribute to be set, and then we can use KNOWN_BOARDS to fill in the
rest.


### \_decode\_attribute
```py

def _decode_attribute(self, raw)

```




