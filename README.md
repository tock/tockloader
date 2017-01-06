Tock Loader
===========

Tool for programming Tock onto hardware boards.

Install
-------

```
sudo pip3 install tockloader
```

Usage
-----

This tool installs a binary called `tockloader`, which supports several commands:

### `tockloader listen`

Listen to UART `printf()` data from a board.

### `tockloader flash`

Load binaries onto hardware platforms that are running a compatible bootloader.
This is used by the [TockOS](https://github.com/helena-project/tock) Make system
when application binaries are programmed to the board with `make program`.

### `tockloader list`

Print information about the apps currently loaded onto the board.

### `tockloader replace`

Replace an application that is already flashed to the board with a new
binary.

### `tockloader append`

Add an application binary to the end of the valid array of apps in flash.
