# Package tockloader.app_padding Documentation

## Class InstalledPaddingApp
Representation of a placeholder app that is only padding between other apps
that was extracted from a board.
### \_\_init\_\_
```py

def __init__(self, tbfh, address)

```



Create a `InstalledPaddingApp` from an extracted TBFH.


### get\_binary
```py

def get_binary(self, address=None)

```



Return the binary array comprising the header and the padding between
apps.


### get\_header
```py

def get_header(self)

```



Return the header for this padding.


### get\_size
```py

def get_size(self)

```



Return the total size of the padding in bytes.


### get\_tbfh
```py

def get_tbfh(self)

```



Return the TBF header.


### info
```py

def info(self, verbose=False)

```



Get a string describing various properties of the padding.


### is\_app
```py

def is_app(self)

```



Whether this is an app or padding.


### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).




## Class PaddingApp
Representation of a placeholder app that is only padding between other apps.
### \_\_init\_\_
```py

def __init__(self, size)

```



Create a `PaddingApp` based on the amount of size needing in the
padding.


### get\_binary
```py

def get_binary(self, address=None)

```



Return the binary array comprising the header and the padding between
apps.


### get\_header
```py

def get_header(self)

```



Return the header for this padding.


### get\_size
```py

def get_size(self)

```



Return the total size of the padding in bytes.


### get\_tbfh
```py

def get_tbfh(self)

```



Return the TBF header.


### info
```py

def info(self, verbose=False)

```



Get a string describing various properties of the padding.


### is\_app
```py

def is_app(self)

```



Whether this is an app or padding.


### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).



