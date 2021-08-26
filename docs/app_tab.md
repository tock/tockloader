# Package tockloader.app_tab Documentation

## Class TabApp
Representation of a Tock app for a specific architecture and board from a
TAB file. This is different from a TAB, since a TAB can include compiled
binaries for a range of architectures, or compiled for various scenarios,
which may not be applicable for a particular board.

A TabApp need not be a single TabTbf, as an app from a TAB can include
multiple TabTbfs if the app was compiled multiple times. This could be for
any reason (e.g. it was signed with different keys, or it uses different
compiler optimizations), but typically this is because it is compiled for
specific addresses in flash and RAM, and there are multiple linked versions
present in the TAB. If so, there will be multiple TabTbfs included in this
App object, and the correct one for the board will be used later.
### \_\_init\_\_
```py

def __init__(self, tbfs)

```



Create a `TabApp` from a list of TabTbfs.


### delete\_tbfh\_tlv
```py

def delete_tbfh_tlv(self, tlvid)

```



Delete a particular TLV from each TBF header.


### fix\_at\_next\_loadable\_address
```py

def fix_at_next_loadable_address(self, address)

```



Calculate the next reasonable address where we can put this app where
the address is greater than or equal to `address`. The `address`
argument is the earliest address the app can be at, either the start of
apps or immediately after a previous app. Then return that address.
If we can't satisfy the request, return None.

The "fix" part means remove all TBFs except for the one that we used
to meet the address requirements.

If the app doesn't have a fixed address, then we can put it anywhere,
and we just return the address. If the app is compiled with fixed
addresses, then we need to calculate an address. We do a little bit of
"reasonable assuming" here. Fixed addresses are based on where the _app
binary_ must be located. Therefore, the start of the app where the TBF
header goes must be before that. This can be at any address (as long as
the header will fit), but we want to make this simpler, so we just
assume the TBF header should start on a 1024 byte alignment.


### get\_binary
```py

def get_binary(self, address)

```



Return the binary array comprising the entire application.

This is only valid if there is one TBF file.

`address` is the address of flash the _start_ of the app will be placed
at. This means where the TBF header will go.


### get\_crt0\_header\_str
```py

def get_crt0_header_str(self)

```



Return a string representation of the crt0 header some apps use for
doing PIC fixups. We assume this header is positioned immediately
after the TBF header (AKA at the beginning of the application binary).


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



Return a header if there is only one.


### get\_name
```py

def get_name(self)

```



Return the app name.


### get\_names\_and\_binaries
```py

def get_names_and_binaries(self)

```



Return (filename, binary) tuples for each contained TBF. This is for
updating a .tab file.


### get\_size
```py

def get_size(self)

```



Return the total size (including TBF header) of this app in bytes.

This is only valid if there is only one TBF.


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


### info
```py

def info(self, verbose=False)

```



Get a string describing various properties of the app.


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


### modify\_tbfh\_tlv
```py

def modify_tbfh_tlv(self, tlvid, field, value)

```



Modify a particular TLV from each TBF header to set field=value.


### set\_minimum\_size
```py

def set_minimum_size(self, size)

```



Force each version of the entire app to be a certain size. If `size` is
smaller than the actual app nothing happens.


### set\_size
```py

def set_size(self, size)

```



Force the entire app to be a certain size. If `size` is smaller than the
actual app an error will be thrown.


### set\_size\_constraint
```py

def set_size_constraint(self, constraint)

```



Change the entire app size for each compilation and architecture based
on certain rules.

Valid rules:
- None: do nothing
- 'powers_of_two': make sure the entire size is a power of two.
- ('multiple', value): make sure the entire size is a multiple of value.


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


### \_truncate\_binary
```py

def _truncate_binary(self, binary)

```



Optionally truncate binary if the header+protected size has grown, and
the actual machine code binary is now too long.




## Class TabTbf
Representation of a compiled app in the Tock Binary Format for use in
Tockloader.

This correlates to a specific .tbf file storing a .tab file.
### \_\_init\_\_
```py

def __init__(self, filename, tbfh, binary)

```



- `filename` is the identifier used in the .tab.
- `tbfh` is the header object
- `binary` is the actual compiled binary code



