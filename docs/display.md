# Package tockloader.display Documentation


Utilities for creating output in various formats.

## Class Display
None
### \_\_init\_\_
```py

def __init__(self, show_headers)

```



Arguments:
- show_headers: bool, if True, label each section in the display output.


### bootloader\_version
```py

def bootloader_version(self, version)

```



Show the bootloader version stored in the bootloader itself.


### get
```py

def get(self)

```



### list\_apps
```py

def list_apps(self, apps, verbose, quiet)

```



Show information about a list of apps.


### list\_attributes
```py

def list_attributes(self, attributes)

```



Show the key value pairs for a list of attributes.




## Class HumanReadableDisplay
Format output as a string meant to be human readable.
### \_\_init\_\_
```py

def __init__(self, show_headers=False)

```



Arguments:
- show_headers: bool, if True, label each section in the display output.


### bootloader\_version
```py

def bootloader_version(self, version)

```



Show the bootloader version stored in the bootloader itself.


### get
```py

def get(self)

```



### list\_apps
```py

def list_apps(self, apps, verbose, quiet)

```



Show information about a list of apps.


### list\_attributes
```py

def list_attributes(self, attributes)

```



Show the key value pairs for a list of attributes.




## Class JSONDisplay
Format output as JSON.
### \_\_init\_\_
```py

def __init__(self)

```



Arguments:
- show_headers: bool, if True, label each section in the display output.


### bootloader\_version
```py

def bootloader_version(self, version)

```



Show the bootloader version stored in the bootloader itself.


### get
```py

def get(self)

```



### list\_apps
```py

def list_apps(self, apps, verbose, quiet)

```



Show information about a list of apps.


### list\_attributes
```py

def list_attributes(self, attributes)

```



Show the key value pairs for a list of attributes.



