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

Load Tock applications on to the board. Use `--no-replace` to install
multiple copies of the same app.

### `tockloader update`

Update an application that is already flashed to the board with a new
binary.

### `tockloader uninstall [application name(s)]`

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

### `tockloader remove-attribute [attribute key]`

Remove a particular attribute from the board.

### `tockloader inspect`

Show details about a compiled TAB file.


Features
--------

- Supported communication protocols
  - Serial over USB
  - Segger JLinkExe JTAG support


Complete Install Instructions
-----------------------------

Tockloader is a Python script that is installed as an executable.
To use Tockloader, you need python3, a couple dependencies, and
the Tockloader package.

- Ubuntu
    ```
    sudo apt install python3-pip
    sudo pip3 install -U pip      # update pip
    sudo pip3 install tockloader
    ```

- MacOS
    ```
    brew install python3
    pip3 install tockloader
    ```


Upload to PyPI
--------------

Internal note.

    python3 setup.py sdist bdist_wheel
    twine upload dist/*
