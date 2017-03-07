# ![TockLoader](http://www.tockos.org/assets/img/tockloader.svg#a "Tockloader Logo")

Tool for programming Tock onto hardware boards.

Install
-------

```
(sudo) pip3 install tockloader
```

Usage
-----

This tool installs a binary called `tockloader`, which supports several commands:

### `tockloader listen`

Listen to UART `printf()` data from a board.

### `tockloader list`

Print information about the apps currently loaded onto the board.

### `tockloader install`

Load Tock applications on to the board. This will replace any existing apps
already flashed on the device.

### `tockloader replace`

Replace an application that is already flashed to the board with a new
binary.

### `tockloader add`

Add an application binary (or binaries) to the list of installed apps.

### `tockloader remove [application name]`

Remove an application from flash by its name.

### `tockloader flash`

Load binaries onto hardware platforms that are running a compatible bootloader.
This is used by the [TockOS](https://github.com/helena-project/tock) Make system
when application binaries are programmed to the board with `make program`.

### `tockloader list-attributes`

Show all of the attributes that are stored on the board.

### `tockloader set-attribute [attribute key] [attribute value]`

Set a particular attribute key to the specified value. This will overwrite
an existing attribute if the key matches.


Features
--------

- Supported communication protocols
  - Serial over USB
  - Segger JLinkExe JTAG support
 

Upload to PyPI
--------------

Internal note.

    python3 setup.py sdist bdist_wheel
    twine upload dist/*
