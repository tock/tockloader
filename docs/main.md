# Package tockloader.main Documentation


### Main command line interface for Tockloader.

Each `tockloader` command is mapped to a function which calls the correct
tockloader class function. This file also handles discovering and reading in TAB
files.

### check\_and\_run\_make
```py

def check_and_run_make(args)

```



Checks for a Makefile, and it it exists runs `make`.


### collect\_tabs
```py

def collect_tabs(args, wait=True)

```



Load in Tock Application Bundle (TAB) files. If none are specified, this
searches for them in subfolders.


### command\_disable\_app
```py

def command_disable_app(args)

```



### command\_dump\_flash\_page
```py

def command_dump_flash_page(args)

```



### command\_enable\_app
```py

def command_enable_app(args)

```



### command\_erase\_apps
```py

def command_erase_apps(args)

```



### command\_flash
```py

def command_flash(args)

```



### command\_info
```py

def command_info(args)

```



### command\_inspect\_tab
```py

def command_inspect_tab(args)

```



### command\_install
```py

def command_install(args)

```



### command\_list
```py

def command_list(args)

```



### command\_list\_attributes
```py

def command_list_attributes(args)

```



### command\_listen
```py

def command_listen(args)

```



### command\_remove\_attribute
```py

def command_remove_attribute(args)

```



### command\_set\_attribute
```py

def command_set_attribute(args)

```



### command\_sticky\_app
```py

def command_sticky_app(args)

```



### command\_uninstall
```py

def command_uninstall(args)

```



### command\_unsticky\_app
```py

def command_unsticky_app(args)

```



### command\_update
```py

def command_update(args)

```



### main
```py

def main()

```



Read in command line arguments and call the correct command function.

