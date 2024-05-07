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



### kernel\_attributes
```py

def kernel_attributes(self, kern_attrs)

```



Show the kernel attributes stored in the kernel binary.


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



### kernel\_attributes
```py

def kernel_attributes(self, kern_attrs)

```



Show the kernel attributes stored in the kernel binary.


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


### show\_app\_map
```py

def show_app_map(self, apps, start_address)

```



### show\_board\_visual
```py

def show_board_visual(self, apps)

```





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



### kernel\_attributes
```py

def kernel_attributes(self, kern_attrs)

```



Show the kernel attributes stored in the kernel binary.


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




## Class VisualDisplay
Format output as an ASCII art string.

┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────┐
│         | │         | │         | │       |
│         | │         | │         | │       |
│         | │         | │         | │       |
│ version | │ version | │ version | │ blink |
│         | │         | │         | │       |
│         | │         | │         | │       |
│         | │         | │         | │       |
│         | │         | │         | │       |
└─────────┘ └─────────┘ └─────────┘ └───────┘
┌───────────────────────────────────────────┐
│ Kernel                                    |
└───────────────────────────────────────────┘
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



### kernel\_attributes
```py

def kernel_attributes(self, kern_attrs)

```



Show the kernel attributes stored in the kernel binary.


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


### \_width
```py

def _width(self)

```




