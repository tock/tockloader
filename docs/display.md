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


### show\_app\_map\_actual\_address
```py

def show_app_map_actual_address(self, apps)

```



Show a map of installed applications with known addresses. Example:

```
0x30000┬──────────────────────────────────────────────────┐
       │App: blink                             [Installed]│
       │  Length: 16384 (0x4000)                          │
0x34000┴──────────────────────────────────────────────────┘
0x38000┬──────────────────────────────────────────────────┐
       │App: blink                             [Installed]│
       │  Length: 16384 (0x4000)                          │
0x3c000┴──────────────────────────────────────────────────┘
```


### show\_app\_map\_from\_address
```py

def show_app_map_from_address(self, apps, start_address)

```



Print a layout map of apps assuming they are located back-to-back
starting from `start_address`. Example:

```
0x30000┬──────────────────────────────────────────────────┐
       │App: blink                             [Installed]│
       │  Length: 16384 (0x4000)                          │
0x34000┼──────────────────────────────────────────────────┤
       │App: blink                             [Installed]│
       │  Length: 16384 (0x4000)                          │
0x3c000┴──────────────────────────────────────────────────┘
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





### app\_bracket
```py

def app_bracket(width, left, right)

```



### choose
```py

def choose(b, t, f)

```



### end\_of\_app
```py

def end_of_app(width, address, continuing)

```



### start\_of\_app
```py

def start_of_app(width, address)

```


