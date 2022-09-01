# Package tockloader.tbfh Documentation

## Class TBFHeader
Tock Binary Format header class. This can parse TBF encoded headers and
return various properties of the application.
### \_\_init\_\_
```py

def __init__(self, buffer)

```



Initialize self.  See help(type(self)) for accurate signature.


### adjust\_starting\_address
```py

def adjust_starting_address(self, address)

```



Alter this TBF header so the fixed address in flash will be correct
if the entire TBF binary is loaded at address `address`.


### delete\_tlv
```py

def delete_tlv(self, tlvid)

```



Delete a particular TLV by ID if it exists.


### get\_app\_name
```py

def get_app_name(self)

```



Return the package name if it was encoded in the header, otherwise
return a tuple of (package_name_offset, package_name_size).


### get\_app\_size
```py

def get_app_size(self)

```



Get the total size the app takes in bytes in the flash of the chip.


### get\_binary
```py

def get_binary(self)

```



Get the TBF header in a bytes array.


### get\_fixed\_addresses
```py

def get_fixed_addresses(self)

```



Return (fixed_address_ram, fixed_address_flash) if there are fixed
addresses, or None.


### get\_header\_size
```py

def get_header_size(self)

```



Get the size of the header in bytes. This includes any alignment
padding at the end of the header.


### get\_kernel\_version
```py

def get_kernel_version(self)

```



Return (kernel_major, kernel_minor) if there is kernel version present,
or None.


### get\_size\_before\_app
```py

def get_size_before_app(self)

```



Get the number of bytes before the actual app binary in the .tbf file.


### has\_fixed\_addresses
```py

def has_fixed_addresses(self)

```



Return true if this TBF header includes the fixed addresses TLV.


### has\_kernel\_version
```py

def has_kernel_version(self)

```



Return true if this TBF header includes the kernel version TLV.


### is\_app
```py

def is_app(self)

```



Whether this is an app or padding.


### is\_enabled
```py

def is_enabled(self)

```



Whether the application is marked as enabled. Enabled apps start when
the board boots, and disabled ones do not.


### is\_modified
```py

def is_modified(self)

```



Whether the TBF header has been modified by Tockloader after it was
initially read in (either from a new TAB or from the board).


### is\_sticky
```py

def is_sticky(self)

```



Whether the app is marked sticky and won't be erase during normal app
erases.


### is\_valid
```py

def is_valid(self)

```



Whether the CRC and other checks passed for this header.


### modify\_tlv
```py

def modify_tlv(self, tlvid, field, value)

```



Modify a TLV by setting a particular field in the TLV object to value.


### object
```py

def object(self)

```



### set\_app\_size
```py

def set_app_size(self, size)

```



Set the total size the app takes in bytes in the flash of the chip.

Since this does not change the header size we do not need to update
any other fields in the header.


### set\_flag
```py

def set_flag(self, flag_name, flag_value)

```



Set a flag in the TBF header.

Valid flag names: `enable`, `sticky`


### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).


### \_checksum
```py

def _checksum(self, buffer)

```



Calculate the TBF header checksum.


### \_get\_tlv
```py

def _get_tlv(self, tlvid)

```



Return the TLV from the self.tlvs array if it exists.




## Class TBFHeaderPadding
TBF Header that is only padding between apps. Since apps are packed as
linked-list, this allows apps to be pushed to later addresses while
preserving the linked-list structure.
### \_\_init\_\_
```py

def __init__(self, size)

```



Create the TBF header. All we need to know is how long the entire
padding should be.


### adjust\_starting\_address
```py

def adjust_starting_address(self, address)

```



Alter this TBF header so the fixed address in flash will be correct
if the entire TBF binary is loaded at address `address`.


### delete\_tlv
```py

def delete_tlv(self, tlvid)

```



Delete a particular TLV by ID if it exists.


### get\_app\_name
```py

def get_app_name(self)

```



Return the package name if it was encoded in the header, otherwise
return a tuple of (package_name_offset, package_name_size).


### get\_app\_size
```py

def get_app_size(self)

```



Get the total size the app takes in bytes in the flash of the chip.


### get\_binary
```py

def get_binary(self)

```



Get the TBF header in a bytes array.


### get\_fixed\_addresses
```py

def get_fixed_addresses(self)

```



Return (fixed_address_ram, fixed_address_flash) if there are fixed
addresses, or None.


### get\_header\_size
```py

def get_header_size(self)

```



Get the size of the header in bytes. This includes any alignment
padding at the end of the header.


### get\_kernel\_version
```py

def get_kernel_version(self)

```



Return (kernel_major, kernel_minor) if there is kernel version present,
or None.


### get\_size\_before\_app
```py

def get_size_before_app(self)

```



Get the number of bytes before the actual app binary in the .tbf file.


### has\_fixed\_addresses
```py

def has_fixed_addresses(self)

```



Return true if this TBF header includes the fixed addresses TLV.


### has\_kernel\_version
```py

def has_kernel_version(self)

```



Return true if this TBF header includes the kernel version TLV.


### is\_app
```py

def is_app(self)

```



Whether this is an app or padding.


### is\_enabled
```py

def is_enabled(self)

```



Whether the application is marked as enabled. Enabled apps start when
the board boots, and disabled ones do not.


### is\_modified
```py

def is_modified(self)

```



Whether the TBF header has been modified by Tockloader after it was
initially read in (either from a new TAB or from the board).


### is\_sticky
```py

def is_sticky(self)

```



Whether the app is marked sticky and won't be erase during normal app
erases.


### is\_valid
```py

def is_valid(self)

```



Whether the CRC and other checks passed for this header.


### modify\_tlv
```py

def modify_tlv(self, tlvid, field, value)

```



Modify a TLV by setting a particular field in the TLV object to value.


### object
```py

def object(self)

```



### set\_app\_size
```py

def set_app_size(self, size)

```



Set the total size the app takes in bytes in the flash of the chip.

Since this does not change the header size we do not need to update
any other fields in the header.


### set\_flag
```py

def set_flag(self, flag_name, flag_value)

```



Set a flag in the TBF header.

Valid flag names: `enable`, `sticky`


### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).


### \_checksum
```py

def _checksum(self, buffer)

```



Calculate the TBF header checksum.


### \_get\_tlv
```py

def _get_tlv(self, tlvid)

```



Return the TLV from the self.tlvs array if it exists.




## Class TBFTLV
None
### get\_size
```py

def get_size(self)

```



### get\_tlvid
```py

def get_tlvid(self)

```





## Class TBFTLVFixedAddress
None
### \_\_init\_\_
```py

def __init__(self, buffer)

```



Initialize self.  See help(type(self)) for accurate signature.


### get\_size
```py

def get_size(self)

```



### get\_tlvid
```py

def get_tlvid(self)

```



### object
```py

def object(self)

```



### pack
```py

def pack(self)

```



### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).




## Class TBFTLVKernelVersion
None
### \_\_init\_\_
```py

def __init__(self, buffer)

```



Initialize self.  See help(type(self)) for accurate signature.


### get\_size
```py

def get_size(self)

```



### get\_tlvid
```py

def get_tlvid(self)

```



### object
```py

def object(self)

```



### pack
```py

def pack(self)

```



### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).




## Class TBFTLVMain
None
### \_\_init\_\_
```py

def __init__(self, buffer)

```



Initialize self.  See help(type(self)) for accurate signature.


### get\_size
```py

def get_size(self)

```



### get\_tlvid
```py

def get_tlvid(self)

```



### object
```py

def object(self)

```



### pack
```py

def pack(self)

```



### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).




## Class TBFTLVPackageName
None
### \_\_init\_\_
```py

def __init__(self, buffer)

```



Initialize self.  See help(type(self)) for accurate signature.


### get\_size
```py

def get_size(self)

```



### get\_tlvid
```py

def get_tlvid(self)

```



### object
```py

def object(self)

```



### pack
```py

def pack(self)

```



### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).




## Class TBFTLVPicOption1
None
### \_\_init\_\_
```py

def __init__(self, buffer)

```



Initialize self.  See help(type(self)) for accurate signature.


### get\_size
```py

def get_size(self)

```



### get\_tlvid
```py

def get_tlvid(self)

```



### object
```py

def object(self)

```



### pack
```py

def pack(self)

```



### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).




## Class TBFTLVUnknown
None
### \_\_init\_\_
```py

def __init__(self, tipe, buffer)

```



Initialize self.  See help(type(self)) for accurate signature.


### get\_size
```py

def get_size(self)

```



### get\_tlvid
```py

def get_tlvid(self)

```



### pack
```py

def pack(self)

```





## Class TBFTLVWriteableFlashRegions
None
### \_\_init\_\_
```py

def __init__(self, buffer)

```



Initialize self.  See help(type(self)) for accurate signature.


### get\_size
```py

def get_size(self)

```



### get\_tlvid
```py

def get_tlvid(self)

```



### object
```py

def object(self)

```



### pack
```py

def pack(self)

```



### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).




### roundup
```py

def roundup(x, to)

```


