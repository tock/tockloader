# Package tockloader.app_padding Documentation

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

def get_binary(self, address)

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


### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).



