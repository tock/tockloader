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

Listen to UART `printf()` data from a board. Use the option `--rtt` to use
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

#### `tockloader read [address] [# bytes]`

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

    tockloader [command] --jlink --arch [arch] --board [board] \
    --jlink-cmd [jlink_cmd] --jlink-device [device] --jlink-speed [speed] --jlink-if [if]

- `jlink_cmd`: The JLink executable to invoke. Defaults to `JLinkExe` on
  Mac/Linux, and `JLink` on Windows.
- `device`: The JLinkExe device identifier.
- `speed`: The speed value to pass to JLink. Defaults to 1200.
- `if`: The interface to pass to JLink.

Tockloader can also do JTAG using OpenOCD. OpenOCD needs to know which config
file to use. Note: you will likely need an up-to-date version of OpenOCD for
everything to work. On MacOS you can use `brew install --HEAD openocd` to get
a version from git.

    tockloader [command] --openocd --arch [arch] --board [board] --openocd-board [openocd_board] \
    --openocd-cmd [openocd_cmd] --openocd-options [openocd_options] \
    --openocd-commands [openocd_commands]

- `openocd_board`: The `.cfg` file in the board folder in OpenOCD to use.
- `openocd_cmd`: The OpenOCD executable to invoke. Defaults to `openocd`.
- `openocd_options`: A list of Tock-specific flags used to customize how
  Tockloader calls OpenOCD based on experience with various boards and their
  quirks. Options include:
    - `noreset`: Removes the command `reset init;` from OpenOCD commands.
    - `nocmdprefix`: Removes the commands `init; reset init; halt;` from OpenOCD
    commands.
    - `workareazero`: Adds the command `set WORKAREASIZE 0;` to OpenOCD commands.
    - `resume`: Adds the commands `soft_reset_halt; resume;` to OpenOCD commands.
- `openocd_commands`: This sets a custom OpenOCD command string to allow
  Tockloader to program arbitrary chips with OpenOCD before support for the
  board is officially include in Tockloader. The following main operations
  can be customized:
    - `program`: Operation used to write a binary to the chip.
    - `read`: Operation used to read arbitrary flash memory on the chip.
    - `erase`: Operation that erases arbitrary ranges of flash memory on the chip.

    The custom values are specified as key=value pairs, for example,
    `--openocd_commands 'program=write_image; halt;' 'erase=flash fillb
    {address:#x} 0xff 512;'`. Operation strings can include wildcards which will
    get set with the correct value by Tockloader:
    - `{{binary}}`: The binary file path.
    - `{address:#x}`: The specified address for the binary to be programmed at.
    - `{length}`: The number of bytes. Only valid for the `read` operation.

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

Additional Flags
----------------

There are additional flags that might be useful for customizing tockloader's
operation based on the requirements of a particular hardware platform.

- `--app-address`: Manually specify the address at the beginning of where apps
  are stored. This can be in hex or decimal.
- `--bundle-apps`: This forces tockloader to write all apps as a concatentated
  bundle using only a single flash command. This will require that anytime any
  app changes in any way (e.g. its header changes or the app is updated or a new
  app is installed.) all apps are re-written.

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

- Windows
    - [Download and Install Python 3](https://www.python.org/downloads/windows/)
    - Execute within CMD/PowerShell/...:
        ```
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
