# Package tockloader.jlinkexe Documentation


Interface for boards using Segger's JLinkExe program.

All communication with the board is done using JLinkExe commands and scripts.

Different MCUs require different command line arguments so that the JLinkExe
tool knows which JTAG interface it is talking to. Since we don't want to burden
the user with specifying the board each time, we default to using a generic
cortex-m0 target, and use that to read the bootloader attributes to get the
correct version. Once we know more about the board we are talking to we use the
correct command line argument for future communication.

## Class JLinkExe
Base class for interacting with hardware boards. All of the class functions
should be overridden to support a new method of interacting with a board.
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



Write using JTAG


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



Open a connection to the board.


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



Use JLinkRTTClient to listen for RTT messages.


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



### \_get\_tockloader\_board\_from\_emulators
```py

def _get_tockloader_board_from_emulators(self, emulators)

```



Returns None or a board name if we can parse the emulators list
and find a valid board.


### \_list\_emulators
```py

def _list_emulators(self)

```



Retrieve a list of JLink compatible devices.


### \_run\_jtag\_commands
```py

def _run_jtag_commands(self, commands, binary, write=True)

```



- `commands`: List of JLinkExe commands. Use {binary} for where the name
  of the binary file should be substituted.
- `binary`: A bytes() object that will be used to write to the board.
- `write`: Set to true if the command writes binaries to the board. Set
  to false if the command will read bits from the board.



