# ![TockLoader](http://www.tockos.org/assets/img/tockloader.svg#a "Tockloader Logo")

Tool for programming Tock onto hardware boards.

Install
-------

```
pip3 install tockloader --user
```

If you want tab completions:

```
register-python-argcomplete tockloader >> ~/.bashrc
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

### `tockloader enable-app [application name(s)]`

Enable an app so that the kernel will run it at boot.

### `tockloader disable-app [application name(s)]`

Disable an app so that the kernel will not start it at boot.

### `tockloader sticky-app [application name(s)]`

Mark an app as sticky so that the `--force` flag is required to uninstall it.

### `tockloader unsticky-app [application name(s)]`

Remove the sticky flag from an app.

### `tockloader flash`

Load binaries onto hardware platforms that are running a compatible bootloader.
This is used by the [TockOS](https://github.com/helena-project/tock) Make system
when kernel binaries are programmed to the board with `make program`.

### `tockloader list-attributes`

Show all of the attributes that are stored on the board.

### `tockloader set-attribute [attribute key] [attribute value]`

Set a particular attribute key to the specified value. This will overwrite
an existing attribute if the key matches.

### `tockloader remove-attribute [attribute key]`

Remove a particular attribute from the board.

### `tockloader info`

Show all properties of the board.

### `tockloader inspect-tab`

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
    pip3 install -U pip --user     # update pip
    pip3 install tockloader --user
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
