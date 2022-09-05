# Package tockloader.tab Documentation

## Class TAB
Tock Application Bundle object. This class handles the TAB format.
### \_\_init\_\_
```py

def __init__(self, tab_path, args=Namespace())

```



Initialize self.  See help(type(self)) for accurate signature.


### extract\_app
```py

def extract_app(self, arch)

```



Return a `TabApp` object from this TAB, or `None` if the requested
architecture is not present in the TAB. You must specify the desired MCU
architecture so the correct App object can be retrieved. Note that an
architecture may have multiple TBF files if the app is compiled for a
fixed address, and multiple fixed address versions are included in the
TAB.


### extract\_tbf
```py

def extract_tbf(self, tbf_name)

```



Return a `TabApp` object from this TAB. You must specify the
desired TBF name, and only that TBF will be returned.


### get\_app\_name
```py

def get_app_name(self)

```



Return the app name from the metadata file.


### get\_compatible\_boards
```py

def get_compatible_boards(self)

```



Return a list of compatible boards from the metadata file.


### get\_supported\_architectures
```py

def get_supported_architectures(self)

```



Return a list of architectures that this TAB has compiled binaries for.
Note that this will return all architectures that have any TBF binary,
but some of those TBF binaries may be compiled for very specific
addresses. That is, there isn't a guarantee that the TBF file will work
on any chip with one of the supported architectures.


### get\_tbf\_names
```py

def get_tbf_names(self)

```



Returns a list of the names of all of the .tbf files contained in the
TAB, without the extension.


### is\_compatible\_with\_board
```py

def is_compatible_with_board(self, board)

```



Check if the Tock app is compatible with a particular Tock board.


### is\_compatible\_with\_kernel\_version
```py

def is_compatible_with_kernel_version(self, kernel_version)

```



Check if the Tock app is compatible with the version of the kernel.
Default to yes unless we can be confident the answer is no.

`kernel_version` should be a string, or None if the kernel API version
is unknown.


### update\_tbf
```py

def update_tbf(self, app)

```



Inserts a new or modified `TabApp` into the .tab file.

Only works with .tab files stored locally.


### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).


### \_get\_metadata\_key
```py

def _get_metadata_key(self, key)

```



Return the value for a specific key from the metadata file.


### \_parse\_metadata
```py

def _parse_metadata(self)

```



Open and parse the included metadata file in the TAB, returning the
key-value pairs as a dict.



