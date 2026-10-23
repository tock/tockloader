# Package tockloader.kernel_attributes Documentation


Parse kernel attributes at the end of the kernel flash region.

## Class KATLV
None
### get\_size
```py

def get_size(self)

```



### get\_tlvid
```py

def get_tlvid(self)

```





## Class KATLVAppMemory
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




## Class KATLVKernelBinary
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




## Class KATLVKernelVersion
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




## Class KATLVPublicKey
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


### \_key\_type\_to\_str
```py

def _key_type_to_str(self, type)

```





## Class KernelAttributes
Represent attributes stored at the end of the kernel image that contain metadata
about the installed kernel.
### \_\_init\_\_
```py

def __init__(self, buffer, address)

```



Initialize self.  See help(type(self)) for accurate signature.


### add\_tlv
```py

def add_tlv(self, tlvname, parameters)

```



### get\_app\_memory\_region
```py

def get_app_memory_region(self)

```



Get a tuple of the RAM region for apps. If unknown, return None.

(app_memory_start_address, app_memory_length_bytes)


### get\_binary
```py

def get_binary(self)

```



Get the kernel attributes in a bytes array.


### get\_kernel\_binary\_size
```py

def get_kernel_binary_size(self)

```



Get the length of the actual kernel binary in bytes.

Returns `None` if the kernel binary header is not present.


### get\_size
```py

def get_size(self)

```



Get the size of the kernel attributes in bytes.


### info
```py

def info(self)

```



### object
```py

def object(self)

```



### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).


### \_get\_tlv
```py

def _get_tlv(self, tlvid)

```



Return the TLV from the self.tlvs array if it exists.




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


