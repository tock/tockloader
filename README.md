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

This tool installs a binary called `tockloader`, which supports several commands.

### Primary Commands

These are the main commands for managing apps on a board.

#### `tockloader install`

Load Tock applications on to the board. Use `--no-replace` to install
multiple copies of the same app.

#### `tockloader update`

Update an application that is already flashed to the board with a new
binary.

#### `tockloader uninstall [application name(s)]`

Remove an application from flash by its name.


### Board Inspection Commands

These query the board for its current state.

#### `tockloader list`

Print information about the apps currently loaded onto the board.

#### `tockloader info`

Show all properties of the board.


### Utility Commands

These provide other helpful features.

#### `tockloader listen`

Listen to UART `printf()` data from a board. Use the option `--jlink` to use
Segger's RTT listener instead of using a serial port.


### Other Commands

These provide more internal functionality.

#### `tockloader flash`

Load binaries onto hardware platforms that are running a compatible bootloader.
This is used by the [TockOS](https://github.com/helena-project/tock) Make system
when kernel binaries are programmed to the board with `make program`.

#### `tockloader inspect-tab`

Show details about a compiled TAB file.

#### `tockloader enable-app [application name(s)]`

Enable an app so that the kernel will run it at boot.

#### `tockloader disable-app [application name(s)]`

Disable an app so that the kernel will not start it at boot.

#### `tockloader sticky-app [application name(s)]`

Mark an app as sticky so that the `--force` flag is required to uninstall it.

#### `tockloader unsticky-app [application name(s)]`

Remove the sticky flag from an app.

#### `tockloader list-attributes`

Show all of the attributes that are stored on the board.

#### `tockloader set-attribute [attribute key] [attribute value]`

Set a particular attribute key to the specified value. This will overwrite
an existing attribute if the key matches.

#### `tockloader remove-attribute [attribute key]`

Remove a particular attribute from the board.

#### `tockloader dump-flash-page [page number]`

Show the contents of a page of flash.

#### `tockloader read --address [address] --length [# bytes]`

Read arbitrary flash memory from the board.

#### `tockloader list-known-boards`

Print which boards tockloader has default settings for built-in.

Specifying the Board
--------------------

For tockloader to know how to interface with a particular hardware board, it
typically reads attributes from the bootloader to identify properties of the
board. If those are unavailable, they can be specified as command line
arguments.

    tockloader [command] --arch [arch] --board [board]

- `arch`: The architecture of the board. Likely `cortex-m0` or `cortex-m4`.
- `board`: The name of the board. This helps prevent incompatible applications
  from being flashed on the wrong board.

Tockloader also supports a JTAG interface using JLinkExe. JLinkExe requires
knowing the device type of the MCU on the board.

    tockloader [command] --jlink --arch [arch] --board [board] --jlink-device [device]

- `device`: The JLinkExe device identifier.

Tockloader can also do JTAG using OpenOCD. OpenOCD needs to know which config
file to use. Note: you will likely need an up-to-date version of OpenOCD for
everything to work. On MacOS you can use `brew install --HEAD openocd` to get
a version from git.

    tockloader [command] --openocd --arch [arch] --board [board] --openocd-board [openocd_board]

- `openocd_board`: The `.cfg` file in the board folder in OpenOCD to use.


Example Usage
-------------

Install an app, make sure it's up to date, and make sure it's the only app on
the board:

    tockloader install --make --erase

Get all info from the board that can be used to help debugging:

    tockloader info

Print additionally debugging information. This can be helpful when using JTAG.

    tockloader install --debug

Get `printf()` data from a board:

    tockloader listen


Features
--------

- Supported communication protocols
  - Serial over USB
  - Segger JLinkExe JTAG support
  - OpenOCD JTAG support
- JLink RTT listener


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


Internal Notes
--------------

### Test Locally

To test the code locally without installing as a package, from the top-level
directory:

    python3 -m tockloader.main <COMMANDS>


### Upload to PyPI

    python3 setup.py sdist bdist_wheel
    twine upload dist/*


### Build Docs

    pip3 install mkdocs
    cd docs
    ./generate_docs.py
    cd ..
    mkdocs serve --dev-addr=0.0.0.0:8001
