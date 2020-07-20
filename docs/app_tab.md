# Package tockloader.app_tab Documentation

## Class TabApp
Representation of a Tock app for a specific board from a TAB file. This is
different from a TAB, since a TAB can include compiled binaries for a range
of architectures, or compiled for various scenarios, which may not be
applicable for a particular board.

A TabApp need not be a single (TBF header, binary) pair, as an app from a
TAB can include multiple (header, binary) pairs if the app was compiled
multiple times. This could be for any reason (e.g. it was signed with
different keys, or it uses different compiler optimizations), but typically
this is because it is compiled for specific addresses in flash and RAM, and
there are multiple linked versions present in the TAB. If so, there will be
multiple (header, binary) pairs included in this App object, and the correct
one for the board will be used later.
### \_\_init\_\_
```py

def __init__(self, tbfs)

```



Create a `TabApp` from a list of (TBF header, app binary) pairs.


### get\_binary
```py

def get_binary(self, address)

```



Return the binary array comprising the entire application.

`address` is the address of flash the _start_ of the app will be placed
at. This means where the TBF header will go.


### get\_crt0\_header\_str
```py

def get_crt0_header_str(self)

```



Return a string representation of the crt0 header some apps use for
doing PIC fixups. We assume this header is positioned immediately
after the TBF header (AKA at the beginning of the application binary).


### get\_fixed\_addresses\_flash
```py

def get_fixed_addresses_flash(self)

```



Return a list of all addresses in flash this app is compiled for.


### get\_header
```py

def get_header(self)

```



Return a header if there is only one.


### get\_name
```py

def get_name(self)

```



Return the app name.


### get\_next\_loadable\_address
```py

def get_next_loadable_address(self, address)

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


### get\_size
```py

def get_size(self)

```



Return the total size (including TBF header) of this app in bytes.


### has\_app\_binary
```py

def has_app_binary(self)

```



Return true if we have an application binary with this app.


### has\_fixed\_addresses
```py

def has_fixed_addresses(self)

```



Return true if any TBF binary in this app is compiled for a fixed
address. That likely implies _all_ binaries are compiled for a fixed
address.


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



Returns whether this app needs to be flashed on to the board. Since this
is a TabApp, we did not get this app from the board and therefore we
have to flash this to the board.


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



