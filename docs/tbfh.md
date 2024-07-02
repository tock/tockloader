# Package tockloader.tbfh Documentation

## Class TBFFooter
Represent an optional footer after the application binary in the TBF.
### \_\_init\_\_
```py

def __init__(self, tbfh, app_binary, buffer)

```



Initialize self.  See help(type(self)) for accurate signature.


### add\_credential
```py

def add_credential(self, credential_type, public_key, private_key, integrity_blob, cleartext_id)

```



Add credential by credential type name.


### delete\_credential
```py

def delete_credential(self, credential_type)

```



Remove credential by credential type.


### delete\_tlv
```py

def delete_tlv(self, tlvid)

```



Delete a particular TLV by ID if it exists.


### get\_binary
```py

def get_binary(self)

```



Get the TBF footer in a bytes array.


### get\_size
```py

def get_size(self)

```



### object
```py

def object(self)

```



### shrink
```py

def shrink(self, number_bytes)

```



Try to shrink the footer `number_bytes`. Shrink as much as possible up
to the number by removing padding.


### to\_str\_at\_address
```py

def to_str_at_address(self, address)

```



### verify\_credentials
```py

def verify_credentials(self, public_keys, integrity_blob)

```



Check credential TLVs with an optional array of public keys (stored as
binary arrays).


### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).




## Class TBFFooterTLVCredentials
Represent a Credentials TLV in the footer of a TBF.
### \_\_init\_\_
```py

def __init__(self, buffer, integrity_blob)

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



### shrink
```py

def shrink(self, num_bytes)

```



Shrink a reserved credential by the number of bytes specified. Do
nothing if this is not a reserved credential.


### verify
```py

def verify(self, keys, integrity_blob)

```



### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).


### \_credentials\_name\_to\_id
```py

def _credentials_name_to_id(credential_type)

```



### \_credentials\_type\_to\_str
```py

def _credentials_type_to_str(self)

```





## Class TBFFooterTLVCredentialsConstructor
Represent a Credentials TLV in the footer of a TBF.
### \_\_init\_\_
```py

def __init__(self, credential_id)

```



Initialize self.  See help(type(self)) for accurate signature.


### compute
```py

def compute(self, public_key, private_key, integrity_blob, cleartext_id)

```



Actually generate the credential.


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



### shrink
```py

def shrink(self, num_bytes)

```



Shrink a reserved credential by the number of bytes specified. Do
nothing if this is not a reserved credential.


### verify
```py

def verify(self, keys, integrity_blob)

```



### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).


### \_credentials\_name\_to\_id
```py

def _credentials_name_to_id(credential_type)

```



### \_credentials\_type\_to\_str
```py

def _credentials_type_to_str(self)

```





## Class TBFHeader
Tock Binary Format header class. This can parse TBF encoded headers and
return various properties of the application.
### \_\_init\_\_
```py

def __init__(self, buffer)

```



Initialize self.  See help(type(self)) for accurate signature.


### add\_tlv
```py

def add_tlv(self, tlvname, parameters)

```



### adjust\_starting\_address
```py

def adjust_starting_address(self, address)

```



Alter this TBF header so the fixed address in flash will be correct
if the entire TBF binary is loaded at address `address`.


### corrupt\_tbf
```py

def corrupt_tbf(self, field_name, value)

```



Give a field name and value to set when creating the binary.


### delete\_tlv
```py

def delete_tlv(self, tlvname)

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


### get\_app\_version
```py

def get_app_version(self)

```



Return the version number of the application, if there is one.


### get\_binary
```py

def get_binary(self)

```



Get the TBF header in a bytes array.


### get\_binary\_end\_offset
```py

def get_binary_end_offset(self)

```



Return at what offset the application binary ends. Remaining space
is taken up by footers.


### get\_fixed\_addresses
```py

def get_fixed_addresses(self)

```



Return (fixed_address_ram, fixed_address_flash) if there are fixed
addresses, or None.


### get\_footer\_size
```py

def get_footer_size(self)

```



Return the size in bytes of the footer. If no footer is included this
will return 0.


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


### has\_footer
```py

def has_footer(self)

```



Return true if this TBF has a footer.


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

def modify_tlv(self, tlvname, field, value)

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


### to\_str\_at\_address
```py

def to_str_at_address(self, address)

```



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


### \_get\_binary\_tlv
```py

def _get_binary_tlv(self)

```



Get the TLV for the binary header, whether it's a program or main.


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


### add\_tlv
```py

def add_tlv(self, tlvname, parameters)

```



### adjust\_starting\_address
```py

def adjust_starting_address(self, address)

```



Alter this TBF header so the fixed address in flash will be correct
if the entire TBF binary is loaded at address `address`.


### corrupt\_tbf
```py

def corrupt_tbf(self, field_name, value)

```



Give a field name and value to set when creating the binary.


### delete\_tlv
```py

def delete_tlv(self, tlvname)

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


### get\_app\_version
```py

def get_app_version(self)

```



Return the version number of the application, if there is one.


### get\_binary
```py

def get_binary(self)

```



Get the TBF header in a bytes array.


### get\_binary\_end\_offset
```py

def get_binary_end_offset(self)

```



Return at what offset the application binary ends. Remaining space
is taken up by footers.


### get\_fixed\_addresses
```py

def get_fixed_addresses(self)

```



Return (fixed_address_ram, fixed_address_flash) if there are fixed
addresses, or None.


### get\_footer\_size
```py

def get_footer_size(self)

```



Return the size in bytes of the footer. If no footer is included this
will return 0.


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


### has\_footer
```py

def has_footer(self)

```



Return true if this TBF has a footer.


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

def modify_tlv(self, tlvname, field, value)

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


### to\_str\_at\_address
```py

def to_str_at_address(self, address)

```



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


### \_get\_binary\_tlv
```py

def _get_binary_tlv(self)

```



Get the TLV for the binary header, whether it's a program or main.


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

def __init__(self, buffer, parameters=[])

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

def __init__(self, buffer, parameters=[])

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

def __init__(self, buffer, parameters=[])

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




## Class TBFTLVPermissions
None
### \_\_init\_\_
```py

def __init__(self, buffer, parameters=[])

```



Initialize self.  See help(type(self)) for accurate signature.


### add
```py

def add(self, parameters)

```



### get\_allowed\_commands
```py

def get_allowed_commands(self)

```



Returns a dict of the format:

```
{
    driver_number: [allowed command ID list]
}
```


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




## Class TBFTLVPersistentACL
None
### \_\_init\_\_
```py

def __init__(self, buffer, parameters=[])

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




## Class TBFTLVProgram
None
### \_\_init\_\_
```py

def __init__(self, buffer, total_size=0)

```



Create a Program TLV. To create an empty program TLV, pass `None` in as
the buffer and the total size of the app in `total_size`.


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




## Class TBFTLVShortId
None
### \_\_init\_\_
```py

def __init__(self, buffer, parameters=[])

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



### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).




## Class TBFTLVWriteableFlashRegions
None
### \_\_init\_\_
```py

def __init__(self, buffer, parameters=[])

```



Initialize self.  See help(type(self)) for accurate signature.


### add
```py

def add(self, parameters)

```



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




### get\_addable\_tlvs
```py

def get_addable_tlvs()

```



Return a list of (tlv_name, #parameters) tuples for all TLV types that
tockloader can add.


### get\_tlv\_names
```py

def get_tlv_names()

```



Return a list of all TLV names.


### get\_tlvid\_from\_name
```py

def get_tlvid_from_name(tlvname)

```



### roundup
```py

def roundup(x, to)

```


