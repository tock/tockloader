# Package tockloader.tockloader Documentation


Main Tockloader interface.

All high-level logic is contained here. All board-specific or communication
channel specific code is in other files.

## Class TockLoader
Implement all Tockloader commands. All logic for how apps are arranged
is contained here.
### \_\_init\_\_
```py

def __init__(self, args)

```



Initialize self.  See help(type(self)) for accurate signature.


### dump\_flash\_page
```py

def dump_flash_page(self, page_num)

```



Print one page of flash contents.


### erase\_apps
```py

def erase_apps(self, address, force=False)

```



Erase flash where apps go. All apps are not actually cleared, we just
overwrite the header of the first app.


### flash\_binary
```py

def flash_binary(self, binary, address)

```



Tell the bootloader to save the binary blob to an address in internal
flash.

This will pad the binary as needed, so don't worry about the binary
being a certain length.


### info
```py

def info(self, app_address)

```



Print all info about this board.


### install
```py

def install(self, tabs, address, replace='yes', erase=False)

```



Add or update TABs on the board.

- `replace` can be either "yes", "no", or "only"
- `erase` if true means erase all other apps before installing


### list\_apps
```py

def list_apps(self, address, verbose, quiet)

```



Query the chip's flash to determine which apps are installed.


### list\_attributes
```py

def list_attributes(self)

```



Download all attributes stored on the board.


### open
```py

def open(self, args)

```



Open the correct channel to talk to the board.

For the bootloader, this means opening a serial port. For JTAG, not much
needs to be done.


### remove\_attribute
```py

def remove_attribute(self, key)

```



Remove an existing attribute already stored on the board.


### run\_terminal
```py

def run_terminal(self)

```



Create an interactive terminal session with the board.


### set\_attribute
```py

def set_attribute(self, key, value)

```



Download all attributes stored on the board.


### set\_flag
```py

def set_flag(self, app_names, flag_name, flag_value, address)

```



Set a flag in the TBF header.


### uninstall\_app
```py

def uninstall_app(self, app_names, address, force=False)

```



If an app by this name exists, remove it from the chip. If no name is
given, present the user with a list of apps to remove.


### \_app\_is\_aligned\_correctly
```py

def _app_is_aligned_correctly(self, address, size)

```



Check if putting an app at this address will be OK with the MPU.


### \_bootloader\_is\_present
```py

def _bootloader_is_present(self)

```



Check if a bootloader exists on this board. It is specified by the
string "TOCKBOOTLOADER" being at address 0x400.


### \_extract\_all\_app\_headers
```py

def _extract_all_app_headers(self, address)

```



Iterate through the flash on the board for the header information about
each app.


### \_extract\_apps\_from\_tabs
```py

def _extract_apps_from_tabs(self, tabs)

```



Iterate through the list of TABs and create the app dict for each.


### \_get\_app\_name
```py

def _get_app_name(self, address, length)

```



Retrieve bytes from the board and interpret them as a string


### \_print\_apps
```py

def _print_apps(self, apps, verbose, quiet)

```



Print information about a list of apps


### \_print\_attributes
```py

def _print_attributes(self, attributes)

```



Print the list of attributes in the bootloader.


### \_reflash\_app\_headers
```py

def _reflash_app_headers(self, apps)

```



Take a list of app headers and reflash them to the chip. This doesn't do
a lot of checking, so you better have not re-ordered the headers or
anything annoying like that.


### \_reshuffle\_apps
```py

def _reshuffle_apps(self, address, apps)

```



Given an array of apps, some of which are new and some of which exist,
sort them in flash so they are in descending size order.


### \_start\_communication\_with\_board
```py

def _start_communication_with_board(*args, **kwds)

```



Based on the transport method used, there may be some setup required
to connect to the board. This function runs the setup needed to connect
to the board. It also times the operation.

For the bootloader, the board needs to be reset and told to enter the
bootloader mode. For JTAG, this is unnecessary.



