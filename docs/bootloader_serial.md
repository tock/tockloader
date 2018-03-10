# Package tockloader.bootloader_serial Documentation


Interface with a board over serial that is using the
[Tock Bootloader](https://github.com/tock/tock-bootloader).

## Class BootloaderSerial
Implementation of `BoardInterface` for the Tock Bootloader over serial.
### \_\_init\_\_
```py

def __init__(self, args)

```



Initialize self.  See help(type(self)) for accurate signature.


### bootloader\_is\_present
```py

def bootloader_is_present(self)

```



For this communication protocol we can safely say the bootloader is
present.


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



Reset the chip and assert the bootloader select pin to enter bootloader
mode. Handle retries if necessary.


### erase\_page
```py

def erase_page(self, address)

```



Erase a specific page of internal flash.


### exit\_bootloader\_mode
```py

def exit_bootloader_mode(self)

```



Reset the chip to exit bootloader mode.


### flash\_binary
```py

def flash_binary(self, address, binary, pad=True)

```



Write pages until a binary has been flashed. binary must have a length
that is a multiple of 512.


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



Open the serial port to the chip/bootloader.

Also sets up a local port for determining when two Tockloader instances
are running simultaneously.


### read\_range
```py

def read_range(self, address, length)

```



Read a specific range of flash.


### run\_terminal
```py

def run_terminal(self)

```



Run miniterm for receiving data from the board.


### set\_attribute
```py

def set_attribute(self, index, raw)

```



Set a single attribute.


### \_change\_baud\_rate
```py

def _change_baud_rate(self, baud_rate)

```



If the bootloader on the board supports it and if it succeeds, try to
increase the baud rate to make everything faster.


### \_check\_crc
```py

def _check_crc(self, address, binary)

```



Compares the CRC of the local binary to the one calculated by the
bootloader.


### \_decode\_attribute
```py

def _decode_attribute(self, raw)

```



### \_get\_crc\_internal\_flash
```py

def _get_crc_internal_flash(self, address, length)

```



Get the bootloader to compute a CRC.


### \_get\_serial\_port\_hash
```py

def _get_serial_port_hash(self)

```



Get an identifier that will be consistent for this serial port on this
machine that is also guaranteed to not have any special characters (like
slashes) that would interfere with using as a file name.


### \_issue\_command
```py

def _issue_command(self, command, message, sync, response_len, response_code, show_errors=True)

```



Setup a command to send to the bootloader and handle the response.


### \_ping\_bootloader\_and\_wait\_for\_response
```py

def _ping_bootloader_and_wait_for_response(self)

```



Throws an exception if the device does not respond with a PONG.


### \_server\_thread
```py

def _server_thread(self)

```



### \_toggle\_bootloader\_entry
```py

def _toggle_bootloader_entry(self)

```



Reset the chip and assert the bootloader select pin to enter bootloader
mode.



