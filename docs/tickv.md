# Package tockloader.tickv Documentation


Manage and use a TicKV formatted database.

TicKV: https://github.com/tock/tock/tree/master/libraries/tickv

## Class TicKV
Interface to a generic TicKV database.
### \_\_init\_\_
```py

def __init__(self, storage_binary, region_size)

```



Create a new TicKV object with a given binary buffer representing
the storage.


### append
```py

def append(self, hashed_key, value)

```



Add a key-value pair to a TicKV database.


### cleanup
```py

def cleanup(self)

```



Remove all invalid keys and re-write existing valid objects.


### get
```py

def get(self, hashed_key)

```



Retrieve a key-value object from a TicKV database.


### get\_all
```py

def get_all(self, region_index)

```



Retrieve all key-value objects from a TicKV database.


### get\_binary
```py

def get_binary(self)

```



Return the TicKV database as a binary object that can be written to the
board.


### invalidate
```py

def invalidate(self, hashed_key)

```



Mark a key-value object as deleted in a TicKV database.


### reset
```py

def reset(self)

```



Reset the database back to an initialized state.


### \_append\_object
```py

def _append_object(self, kv_object)

```



### \_get\_all
```py

def _get_all(self, region_index, valid_only)

```



### \_get\_number\_regions
```py

def _get_number_regions(self)

```



### \_get\_region\_binary
```py

def _get_region_binary(self, region_index)

```



### \_get\_starting\_region
```py

def _get_starting_region(self, hashed_key)

```



We use the lowest two bytes to determine the page we should try to find
or store this key on.


### \_invalidate\_hashed\_key
```py

def _invalidate_hashed_key(self, hashed_key)

```



### \_region\_range
```py

def _region_range(self, starting_region)

```



Provide an iterator for iterating all pages in the database starting
with a specific page.


### \_reset
```py

def _reset(self)

```



### \_update\_region\_binary
```py

def _update_region_binary(self, region_index, region_binary)

```





## Class TicKVObject
A TicKV object that is created in tockloader.
### \_\_init\_\_
```py

def __init__(self, header, value_bytes)

```



Initialize self.  See help(type(self)) for accurate signature.


### get\_binary
```py

def get_binary(self)

```



### get\_checksum
```py

def get_checksum(self)

```



### get\_hashed\_key
```py

def get_hashed_key(self)

```



### get\_value\_bytes
```py

def get_value_bytes(self)

```



### invalidate
```py

def invalidate(self)

```



### is\_valid
```py

def is_valid(self)

```



### length
```py

def length(self)

```



Return the total length of this object in the database in bytes.


### object
```py

def object(self)

```



### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).


### \_calculate\_checksum
```py

def _calculate_checksum(self, object_bytes)

```



### \_get\_object\_bytes
```py

def _get_object_bytes(self)

```





## Class TicKVObjectBase
Shared class representing an item in a TicKV database.
### \_\_init\_\_
```py

def __init__(self, header, checksum=None)

```



Initialize self.  See help(type(self)) for accurate signature.


### get\_binary
```py

def get_binary(self)

```



### get\_checksum
```py

def get_checksum(self)

```



### get\_hashed\_key
```py

def get_hashed_key(self)

```



### invalidate
```py

def invalidate(self)

```



### is\_valid
```py

def is_valid(self)

```



### length
```py

def length(self)

```



Return the total length of this object in the database in bytes.


### object
```py

def object(self)

```



### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).


### \_calculate\_checksum
```py

def _calculate_checksum(self, object_bytes)

```



### \_get\_object\_bytes
```py

def _get_object_bytes(self)

```





## Class TicKVObjectFlash
A TicKV object that is read off of the flash.
### \_\_init\_\_
```py

def __init__(self, binary)

```



Initialize self.  See help(type(self)) for accurate signature.


### get\_binary
```py

def get_binary(self)

```



### get\_checksum
```py

def get_checksum(self)

```



### get\_hashed\_key
```py

def get_hashed_key(self)

```



### get\_value\_bytes
```py

def get_value_bytes(self)

```



### invalidate
```py

def invalidate(self)

```



### is\_valid
```py

def is_valid(self)

```



### length
```py

def length(self)

```



Return the total length of this object in the database in bytes.


### object
```py

def object(self)

```



### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).


### \_calculate\_checksum
```py

def _calculate_checksum(self, object_bytes)

```



### \_get\_object\_bytes
```py

def _get_object_bytes(self)

```





## Class TicKVObjectHeader
The base header for an item in a TicKV database.
### \_\_init\_\_
```py

def __init__(self, hashed_key, version=1, flags=8)

```



Initialize self.  See help(type(self)) for accurate signature.


### get\_binary
```py

def get_binary(self, length)

```



### invalidate
```py

def invalidate(self)

```



### is\_valid
```py

def is_valid(self)

```



### length
```py

def length(self)

```





## Class TicKVObjectHeaderFlash
An item header read from an existing database. This handles parsing the
structure from a byte array.
### \_\_init\_\_
```py

def __init__(self, binary)

```



Initialize self.  See help(type(self)) for accurate signature.


### get\_binary
```py

def get_binary(self, length)

```



### get\_value\_length
```py

def get_value_length(self)

```



### invalidate
```py

def invalidate(self)

```



### is\_valid
```py

def is_valid(self)

```



### length
```py

def length(self)

```





## Class TicKVObjectTock
Tock-formatted object stored in TicKV.
### \_\_init\_\_
```py

def __init__(self, header, storage_object, padding=0, checksum=None)

```



Initialize self.  See help(type(self)) for accurate signature.


### get\_binary
```py

def get_binary(self)

```



### get\_checksum
```py

def get_checksum(self)

```



### get\_hashed\_key
```py

def get_hashed_key(self)

```



### get\_value\_bytes
```py

def get_value_bytes(self)

```



### invalidate
```py

def invalidate(self)

```



### is\_valid
```py

def is_valid(self)

```



### length
```py

def length(self)

```



Return the total length of this object in the database in bytes.


### object
```py

def object(self)

```



### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).


### \_calculate\_checksum
```py

def _calculate_checksum(self, object_bytes)

```



### \_get\_object\_bytes
```py

def _get_object_bytes(self)

```





## Class TicKVObjectTockFlash
Tock-formatted object stored in TicKV and read from flash.
### \_\_init\_\_
```py

def __init__(self, tickv_object)

```



Initialize self.  See help(type(self)) for accurate signature.


### get\_binary
```py

def get_binary(self)

```



### get\_checksum
```py

def get_checksum(self)

```



### get\_hashed\_key
```py

def get_hashed_key(self)

```



### get\_value\_bytes
```py

def get_value_bytes(self)

```



### invalidate
```py

def invalidate(self)

```



### is\_valid
```py

def is_valid(self)

```



### length
```py

def length(self)

```



Return the total length of this object in the database in bytes.


### object
```py

def object(self)

```



### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).


### \_calculate\_checksum
```py

def _calculate_checksum(self, object_bytes)

```



### \_get\_object\_bytes
```py

def _get_object_bytes(self)

```





## Class TockStorageObject
This is the item stored in a TicKV value that Tock processes/kernel can
access.
### \_\_init\_\_
```py

def __init__(self, value_bytes, write_id=0, version=0)

```



Initialize self.  See help(type(self)) for accurate signature.


### get\_binary
```py

def get_binary(self)

```



### length
```py

def length(self)

```



### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).




## Class TockStorageObjectFlash
Tock-formatted K-V object read from a flash binary.

This is useful when reading a Tock K-V from a board.
### \_\_init\_\_
```py

def __init__(self, binary)

```



Initialize self.  See help(type(self)) for accurate signature.


### get\_binary
```py

def get_binary(self)

```



### length
```py

def length(self)

```



### \_\_str\_\_
```py

def __str__(self)

```



Return str(self).




## Class TockTicKV
Extension of a TicKV database that adds an additional header with a
`write_id` to enable enforcing access control.
### \_\_init\_\_
```py

def __init__(self, storage_binary, region_size)

```



Create a new TicKV object with a given binary buffer representing
the storage.


### append
```py

def append(self, key, value, write_id)

```



Add a key-value pair to the database.


### cleanup
```py

def cleanup(self)

```



Remove all invalid keys and re-store valid key-value pairs.


### dump
```py

def dump(self)

```



Display the entire contents of the database.


### get
```py

def get(self, key)

```



Get the Tock-formatted value from the database given the key.


### get\_all
```py

def get_all(self, region_index)

```



Get all Tock objects from the database and assume they are all Tock
formatted.


### get\_binary
```py

def get_binary(self)

```



Return the TicKV database as a binary object that can be written to the
board.


### invalidate
```py

def invalidate(self, key)

```



Delete a key-value pair from the database.


### reset
```py

def reset(self)

```



Reset the database back to an initialized state.


### \_append\_object
```py

def _append_object(self, kv_object)

```



### \_get\_all
```py

def _get_all(self, region_index, valid_only)

```



### \_get\_number\_regions
```py

def _get_number_regions(self)

```



### \_get\_region\_binary
```py

def _get_region_binary(self, region_index)

```



### \_get\_starting\_region
```py

def _get_starting_region(self, hashed_key)

```



We use the lowest two bytes to determine the page we should try to find
or store this key on.


### \_hash\_key
```py

def _hash_key(self, key)

```



Compute the SipHash24 for the given key.


### \_hash\_key\_int
```py

def _hash_key_int(self, key)

```



Compute the SipHash24 for the given key. Return as u64.


### \_invalidate\_hashed\_key
```py

def _invalidate_hashed_key(self, hashed_key)

```



### \_region\_range
```py

def _region_range(self, starting_region)

```



Provide an iterator for iterating all pages in the database starting
with a specific page.


### \_reset
```py

def _reset(self)

```



### \_update\_region\_binary
```py

def _update_region_binary(self, region_index, region_binary)

```




