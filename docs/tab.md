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



Return an `App` object from this TAB. You must specify the desired
MCU architecture so the correct binary can be retrieved.


### get\_crt0\_header\_str
```py

def get_crt0_header_str(self, arch)

```



Return a string representation of the crt0 header some apps use for
doing PIC fixups. We assume this header is positioned immediately
after the TBF header.


### get\_supported\_architectures
```py

def get_supported_architectures(self)

```



Return a list of architectures that this TAB has compiled binaries for.


### get\_tbf\_header
```py

def get_tbf_header(self)

```



Return a TBFHeader object with the TBF header from the app in the TAB.
TBF headers are not architecture specific, so we pull from a random
binary if there are multiple architectures supported.


### is\_compatible\_with\_board
```py

def is_compatible_with_board(self, board)

```



Check if the Tock app is compatible with a particular Tock board.


### parse\_metadata
```py

def parse_metadata(self)

```



Open and parse the included metadata file in the TAB.


### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).



