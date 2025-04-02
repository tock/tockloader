# Package tockloader.app_padding Documentation

## Class InstalledPaddingApp
Representation of a placeholder app that is only padding between other apps
that was extracted from a board.
### \_\_init\_\_
```py

def __init__(self, tbfh, address)

```



Create a `InstalledPaddingApp` from an extracted TBFH.


### get\_address
```py

def get_address(self)

```



Get the address of where on the board this padding app is.


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


### has\_app\_binary
```py

def has_app_binary(self)

```



We can always return the binary for a padding app, so we can always
return true.


### has\_fixed\_addresses
```py

def has_fixed_addresses(self)

```



A padding app is not an executable so can be placed anywhere.


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


### verify\_credentials
```py

def verify_credentials(self, public_keys)

```



Padding apps do not have credentials, so we ignore this.


### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).




## Class PaddingApp
Representation of a placeholder app that is only padding between other apps.
### \_\_init\_\_
```py

def __init__(self, size, address=None)

```



Create a `PaddingApp` based on the amount of size needing in the
padding.


### get\_address
```py

def get_address(self)

```



Get the address of where on the board this padding app is.


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


### has\_app\_binary
```py

def has_app_binary(self)

```



We can always return the binary for a padding app, so we can always
return true.


### has\_fixed\_addresses
```py

def has_fixed_addresses(self)

```



A padding app is not an executable so can be placed anywhere.


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


### verify\_credentials
```py

def verify_credentials(self, public_keys)

```



Padding apps do not have credentials, so we ignore this.


### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).



