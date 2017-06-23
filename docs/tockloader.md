# Package tockloader.tockloader Documentation

## Class TockLoader
None
### \_\_init\_\_
```py

def __init__(self, args)

```



Initialize self.  See help(type(self)) for accurate signature.


### erase\_apps
```py

def erase_apps(self, address, force=False)

```



### flash\_binary
```py

def flash_binary(self, binary, address)

```



### info
```py

def info(self, app_address)

```



### install
```py

def install(self, tabs, address, replace='yes', erase=False)

```



### list\_apps
```py

def list_apps(self, address, verbose, quiet)

```



### list\_attributes
```py

def list_attributes(self)

```



### open
```py

def open(self, args)

```



### remove\_attribute
```py

def remove_attribute(self, key)

```



### run\_terminal
```py

def run_terminal(self)

```



### set\_attribute
```py

def set_attribute(self, key, value)

```



### set\_flag
```py

def set_flag(self, app_names, flag_name, flag_value, address)

```



### uninstall\_app
```py

def uninstall_app(self, app_names, address, force=False)

```



### \_app\_is\_aligned\_correctly
```py

def _app_is_aligned_correctly(self, address, size)

```



### \_bootloader\_is\_present
```py

def _bootloader_is_present(self)

```



### \_extract\_all\_app\_headers
```py

def _extract_all_app_headers(self, address)

```



### \_extract\_apps\_from\_tabs
```py

def _extract_apps_from_tabs(self, tabs)

```



### \_get\_app\_name
```py

def _get_app_name(self, address, length)

```



### \_print\_apps
```py

def _print_apps(self, apps, verbose, quiet)

```



### \_print\_attributes
```py

def _print_attributes(self, attributes)

```



### \_reflash\_app\_headers
```py

def _reflash_app_headers(self, apps)

```



### \_reshuffle\_apps
```py

def _reshuffle_apps(self, address, apps)

```



### \_start\_communication\_with\_board
```py

def _start_communication_with_board(*args, **kwds)

```




