# -*- Mode: Python -*-

import base58
import codecs
import struct
import hashlib


''' This module provides a number of utility/helper functions that are commonly used with
    Bitcoin related objects. Primarily, the module provides functionality for serializing
    and deserializing various data types according to Bitcoin serialization rules.
'''

def bytes_to_str(b):
    ''' Converts bytes into a hex-encoded string.

    Args:
        b (bytes): bytes to encode

    Returns:
        h (str): hex-encoded string corresponding to b.
    '''
    return codecs.encode(b, 'hex_codec').decode('ascii')

def hex_str_to_bytes(h):
    ''' Converts a hex-encoded string to bytes.

    Args:
        h (str): hex-encoded string to convert.
    
    Returns:
        b (bytes): bytes corresponding to h.
    '''
    return bytes.fromhex(h)

def dhash(s):
    ''' Computes the double SHA-256 hash of the input.

    Args:
        s (bytes): bytes to hash.

    Returns:
        h (bytes): Double SHA-256 hash of s.
    '''
    return hashlib.sha256(hashlib.sha256(s).digest()).digest()

# Is there a better way of doing this?
def render_int(n):
    ''' Renders an int in the shortest possible form.

        When packing the height into the coinbase script, the integer
        representing the height must be encoded in the shortest possible
        manner. See: https://bitcoin.org/en/developer-reference#coinbase.

    Args:
        n (int): number to be encoded.

    Returns:
        b (bytes): bytes representing n in the shortest possible form.
    '''
    # little-endian byte stream
    if n < 0:
        neg = True
        n = -n
    else:
        neg = False
    r = []
    while n:
        r.append(n & 0xff)
        n >>= 8
    if neg:
        if r[-1] & 0x80:
            r.append(0x80)
        else:
            r[-1] |= 0x80
    elif r and (r[-1] & 0x80):
        r.append(0)
    return bytes(r)

def pack_compact_int(i):
    ''' See
        https://bitcoin.org/en/developer-reference#compactsize-unsigned-integers

    Args:
        i (int): Integer to be serialized.

    Returns:
        b (bytes): Serialized bytes corresponding to i.
    '''
    if i < 0xfd:
        return struct.pack('<B', i)
    elif i <= 0xffff:
        return struct.pack('<BH', 0xfd, i)
    elif i <= 0xffffffff:
        return struct.pack('<BI', 0xfe, i)
    else:
        return struct.pack('<BQ', 0xff, i)

def unpack_compact_int(bytestr):
    ''' See
        https://bitcoin.org/en/developer-reference#compactsize-unsigned-integers

    Args:
        bytestr (bytes): bytes containing an unsigned integer to be deserialized.

    Returns:
        n (int): deserialized integer.
    '''

    b0 = bytestr[0]
    if b0 < 0xfd:
        return (b0, bytestr[1:])
    elif b0 == 0xfd:
        return (struct.unpack('<H', bytestr[1:3])[0], bytestr[3:])
    elif b0 == 0xfe:
        return (struct.unpack('<I', bytestr[1:5])[0], bytestr[5:])
    elif b0 == 0xff:
        return (struct.unpack('<Q', bytestr[1:9])[0], bytestr[9:])
    else:
        return None

def make_push_str(s):
    ''' Creates a script to push s onto the stack.

    Args:
        s (bytes): bytes to be pushed onto the stack.

    Returns:
        b (bytes): Serialized bytes containing the appropriate PUSHDATA
                   op for s.
    '''
    ls = len(s)
    hexstr = bytes_to_str(s)
    pd_index = 0

    from two1.bitcoin.script import Script
    
    if ls < Script.BTC_OPCODE_TABLE['OP_PUSHDATA1']:
        return bytes([ls]) + s
    # Determine how many bytes are required for the length
    elif ls < 0xff:
        pd_index = 1
    elif ls < 0xffff:
        pd_index = 2
    else:
        pd_index = 4

    return bytes(Script('OP_PUSHDATA%d 0x%s' % (pd_index, hexstr)))

def make_push_int(i):
    ''' Creates a script to push i onto the stack using the least possible
        number of bytes.

    Args:
        i (int): integer to be pushed onto the stack.

    Returns:
        b (bytes): Serialized bytes containing the appropriate PUSHDATA
                   op for i.
    '''
    from two1.bitcoin.script import Script
    
    if i >= 0 and i <= 16:
        return bytes(Script('OP_%d' % i))
    else:
        return make_push_str(render_int(i))

def pack_u32(i):
    ''' Serializes a 32-bit integer into little-endian form.

    Args:
        i (int): integer to be serialized.

    Returns:
        b (bytes): 4 bytes containing the little-endian serialization of i.
    '''
    return struct.pack('<I', i)

def unpack_u32(b):
    ''' Deserializes a 32-bit integer from bytes.

    Args:
        b (bytes): At least 4 bytes containing the serialized integer.

    Returns:
        (i, b) (tuple): A tuple containing the deserialized integer and the
                        remainder of the byte stream.
    '''
    u32 = struct.unpack('<I', b[0:4])
    return (u32[0], b[4:])

def pack_u64(i):
    ''' Serializes a 64-bit integer into little-endian form.

    Args:
        i (int): integer to be serialized.

    Returns:
        b (bytes): 8 bytes containing the little-endian serialization of i.
    '''
    return struct.pack('<Q', i)

def unpack_u64(b):
    ''' Deserializes a 64-bit integer from bytes.

    Args:
        b (bytes): At least 8 bytes containing the serialized integer.

    Returns:
        (i, b) (tuple): A tuple containing the deserialized integer and the
                        remainder of the byte stream.
    '''
    u64 = struct.unpack('<Q', b[0:8])
    return (u64[0], b[8:])

def pack_var_str(s):
    ''' Serializes a variable length byte stream.

    Args:
        s (bytes): byte stream to serialize

    Return:
        b (bytes): Serialized bytes, prepended with the length of the byte stream.
    '''
    return pack_compact_int(len(s)) + s

def unpack_var_str(b):
    ''' Deserializes a variable length byte stream.
    
    Args:
        b (bytes): variable length byte stream to deserialize

    Returns:
        (s, b) (tuple): A tuple containing the variable length byte stream
                        and the remainder of the input byte stream.
    '''
    strlen, b0 = unpack_compact_int(b)
    return (b0[:strlen], b0[strlen:])

def decode_compact_target(bits):
    ''' Decodes the full target from a compact representation.
        See: https://bitcoin.org/en/developer-reference#target-nbits

    Args:
        bits (int): Compact target (32 bits)

    Returns:
        target (Bignum): Full 256-bit target
    '''
    shift = bits >> 24
    target = (bits & 0xffffff) * (1 << (8 * (shift - 3)))
    return target

def encode_compact_target(target):
    ''' Encodes the full target to a compact representation.

    Args:
        target (Bignum): Full 256-bit target

    Returns:
        bits (int): Compact target (32 bits)
    '''
    hex_target = '%x' % target
    shift = (len(hex_target) + 1) / 2
    prefix = target >> (8 * (shift - 3))
    return (shift << 24) + prefix

def bits_to_difficulty(bits):
    ''' Determines the difficulty corresponding to bits.
        See: https://en.bitcoin.it/wiki/Difficulty
    
    Args:
        bits (int): Compact target (32 bits)

    Returns:
        diff (float): Measure of how hard it is to find a solution
                      below the target represented by bits.
    '''
    target = decode_compact_target(bits)
    return 0xffff0000000000000000000000000000000000000000000000000000 / target

def address_to_key(s):
    ''' Given a Bitcoin address decodes the version and 
        RIPEMD-160 hash of the public key.

    Args:
        s (bytes): The Bitcoin address to decode

    Returns:
        (version, h160) (tuple): A tuple containing the version and RIPEMD-160
                                 hash of the public key.
    '''
    n = base58.b58decode_check(s)
    version = n[0]
    h160 = n[1:]
    return version, h160

def compute_reward(height):
    ''' Computes the block reward for a block at the supplied height.
        See: https://en.bitcoin.it/wiki/Controlled_supply for the reward
        schedule.

    Args:
        height (int): Block height

    Returns:
        reward (int): Number of satoshis rewarded for solving a block at the
                      given height.
    '''
    era = height // 210000
    return 50 * 100000000 / (era + 1)