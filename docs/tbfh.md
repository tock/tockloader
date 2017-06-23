# Package tockloader.tbfh Documentation

## Class TBFHeader
Tock Binary Format header class. This can parse TBF encoded headers and
return various properties of the application.
### \_\_init\_\_
```py

def __init__(self, buffer)

```



Initialize self.  See help(type(self)) for accurate signature.


### get\_app\_size
```py

def get_app_size(self)

```



Get the total size the app takes in bytes in the flash of the chip.


### get\_binary
```py

def get_binary(self)

```



Get the TBF header in a bytes array.


### get\_name\_length
```py

def get_name_length(self)

```



Get the number of bytes for the application name.


### get\_name\_offset
```py

def get_name_offset(self)

```



Get the offset in the application binary where the application name is.


### is\_enabled
```py

def is_enabled(self)

```



Whether the application is marked as enabled. Enabled apps start when
the board boots, and disabled ones do not.


### is\_sticky
```py

def is_sticky(self)

```



Whether the app is marked sticky and won't be erase during normal app
erases.


### is\_valid
```py

def is_valid(self)

```



Whether the CRC and other checks passed for this header.


### set\_flag
```py

def set_flag(self, flag_name, flag_value)

```



Set a flag in the TBF header.

Valid flag names: `enable`, `sticky`


### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).


### \_checksum
```py

def _checksum(self)

```



Calculate the TBF header checksum.



