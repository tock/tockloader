# Package tockloader.app Documentation

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


### get\_app\_binary
```py

def get_app_binary(self)

```



Return just the compiled application code binary. Does not include
the TBF header.


### get\_binary
```py

def get_binary(self)

```



Return the binary array comprising the entire application.


### get\_crt0\_header\_str
```py

def get_crt0_header_str(self)

```



Return a string representation of the crt0 header some apps use for
doing PIC fixups. We assume this header is positioned immediately
after the TBF header.


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


### info
```py

def info(self, verbose=False)

```



Get a string describing various properties of the app.


### set\_address
```py

def set_address(self, address)

```



Set the address of flash where this app is or should go.


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



