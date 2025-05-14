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

def collect_tabs(args)

```



Load in Tock Application Bundle (TAB) files. If none are specified, this
searches for them in subfolders.

Also allow downloading apps by name from a server.


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



### command\_list\_known\_boards
```py

def command_list_known_boards(args)

```



### command\_listen
```py

def command_listen(args)

```



### command\_read
```py

def command_read(args)

```



Read the correct flash range from the chip.


### command\_remove\_attribute
```py

def command_remove_attribute(args)

```



### command\_set\_attribute
```py

def command_set_attribute(args)

```



### command\_set\_start\_address
```py

def command_set_start_address(args)

```



### command\_sticky\_app
```py

def command_sticky_app(args)

```



### command\_tbf\_convert
```py

def command_tbf_convert(args)

```



### command\_tbf\_credential\_add
```py

def command_tbf_credential_add(args)

```



### command\_tbf\_credential\_delete
```py

def command_tbf_credential_delete(args)

```



### command\_tbf\_tlv\_add
```py

def command_tbf_tlv_add(args)

```



### command\_tbf\_tlv\_delete
```py

def command_tbf_tlv_delete(args)

```



### command\_tbf\_tlv\_modify
```py

def command_tbf_tlv_modify(args)

```



### command\_tickv\_append
```py

def command_tickv_append(args)

```



### command\_tickv\_append\_rsa\_key
```py

def command_tickv_append_rsa_key(args)

```



Helper operation to store an RSA public key in a TicKV database. This adds
two key-value pairs:

1. `rsa<bits>-key-n`
2. `rsa<bits>-key-e`

where `<bits>` is the size of the key. So, for 2048 bit RSA keys the two
TicKV keys will be `rsa2048-key-n` and `rsa2048-key-e`.

The actual values for n and e are stored as byte arrays.


### command\_tickv\_cleanup
```py

def command_tickv_cleanup(args)

```



### command\_tickv\_dump
```py

def command_tickv_dump(args)

```



### command\_tickv\_get
```py

def command_tickv_get(args)

```



### command\_tickv\_hash
```py

def command_tickv_hash(args)

```



### command\_tickv\_invalidate
```py

def command_tickv_invalidate(args)

```



### command\_tickv\_reset
```py

def command_tickv_reset(args)

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



### command\_write
```py

def command_write(args)

```



Write flash range on the chip with a specific value.


### get\_addable\_tlvs
```py

def get_addable_tlvs()

```



Return a list of (tlv_name, #parameters) tuples for all TLV types that
tockloader can add.


### main
```py

def main()

```



Read in command line arguments and call the correct command function.

