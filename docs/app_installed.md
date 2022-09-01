# Package tockloader.app_installed Documentation

## Class InstalledApp
Representation of a Tock app that is installed on a specific board. This
object is created when Tockloader finds an app already installed on a board.

At the very least this includes the TBF header and an address of where the
app is on the board. It can also include the actual app binary which is
necessary if the app needs to be moved.
### \_\_init\_\_
```py

def __init__(self, tbfh, address, app_binary=None)

```



Initialize self.  See help(type(self)) for accurate signature.


### fix\_at\_next\_loadable\_address
```py

def fix_at_next_loadable_address(self, address)

```



Calculate the next reasonable address where we can put this app where
the address is greater than or equal to `address`. The `address`
argument is the earliest address the app can be at, either the start of
apps or immediately after a previous app.

If the app doesn't have a fixed address, then we can put it anywhere,
and we just return the address. If the app is compiled with fixed
addresses, then we need to calculate an address. We do a little bit of
"reasonable assuming" here. Fixed addresses are based on where the _app
binary_ must be located. Therefore, the start of the app where the TBF
header goes must be before that. This can be at any address (as long as
the header will fit), but we want to make this simpler, so we just
assume the TBF header should start on a 1024 byte alignment.


### get\_address
```py

def get_address(self)

```



Get the address of where on the board the app is or should go.


### get\_app\_binary
```py

def get_app_binary(self)

```



Return just the compiled application code binary. Does not include
the TBF header.


### get\_binary
```py

def get_binary(self, address)

```



Return the binary array comprising the entire application if it needs to
be written to the board. Otherwise, if it is already installed, return
`None`.


### get\_fixed\_addresses\_flash\_and\_sizes
```py

def get_fixed_addresses_flash_and_sizes(self)

```



Return a list of tuples of all addresses in flash this app is compiled
for and the size of the app at that address.

[(address, size), (address, size), ...]


### get\_header
```py

def get_header(self)

```



Return the TBFH object for the header.


### get\_header\_binary
```py

def get_header_binary(self)

```



Get the TBF header as a bytes array.


### get\_header\_size
```py

def get_header_size(self)

```



Return the size of the TBF header in bytes.


### get\_name
```py

def get_name(self)

```



Return the app name.


### get\_size
```py

def get_size(self)

```



Return the total size (including TBF header) of this app in bytes.


### has\_app\_binary
```py

def has_app_binary(self)

```



Whether we have the actual application binary for this app.


### has\_fixed\_addresses
```py

def has_fixed_addresses(self)

```



Return true if the TBF binary is compiled for a fixed address.


### info
```py

def info(self, verbose=False)

```



Get a string describing various properties of the app.


### is\_app
```py

def is_app(self)

```



Whether this is an app or padding.


### is\_loadable\_at\_address
```py

def is_loadable_at_address(self, address)

```



Check if it is possible to load this app at the given address. Returns
True if it is possible, False otherwise.


### is\_modified
```py

def is_modified(self)

```



Returns whether this app has been modified by tockloader since it was
initially created by `__init__`.


### is\_sticky
```py

def is_sticky(self)

```



Returns true if the app is set as sticky and will not be removed with
a normal app erase command. Sticky apps must be force removed.


### object
```py

def object(self)

```



Return a dict object containing the information about this app.


### set\_app\_binary
```py

def set_app_binary(self, app_binary)

```



Update the application binary. Likely this binary would come from the
existing contents of flash on a board.


### set\_size
```py

def set_size(self, size)

```



Force the entire app to be a certain size. If `size` is smaller than the
actual app an error will be thrown.


### set\_sticky
```py

def set_sticky(self)

```



Mark this app as "sticky" in the app's header. This makes it harder to
accidentally remove this app if it is a core service or debug app.


### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).



