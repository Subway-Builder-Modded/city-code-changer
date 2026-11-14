#! /usr/bin/env python
"""
Loads a .metro save and converts the city code to a different code,
to migrate from SJU to PR, LA to LAX, LAXM to LAX, etc.

Heavily informed by EJ's metro-savefile-doctor:
https://github.com/ejfox/metro-savefile-doctor/blob/main/core/src/metro-loader.ts
"""

import sys, os
import json
import struct
import warnings
import zlib
import time
import uuid


MAGIC = "METR"
HEADER_SIZE = 4096


class HeaderData:
    """
    A simple container class to match JS object structure
    """

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def read_string(buffer: bytes, offset: int, max_len: int) -> str:
    """
    Reads a null-terminated string from a buffer at a given offset.
    """
    # Slice the chunk from the buffer
    chunk = buffer[offset : offset + max_len]
    # Split at the first null byte and decode
    null_index = chunk.find(b"\x00")
    if null_index != -1:
        chunk = chunk[:null_index]
    return chunk.decode("utf-8", errors="ignore")


def parse_header(buffer: bytes) -> HeaderData:
    """
    Parse .metro header from bytes
    """

    # Unpack the initial 40 bytes containing magic and 32-bit integers
    # Format string layout:
    # 4s  = 4-byte string (magic)
    # 4x  = 4 bytes padding (skipping bytes 4-7 to hit offset 8)
    # 6I  = Six 32-bit unsigned integers (little-endian: <)
    # I i = One 32-bit unsigned int (low), one 32-bit signed int (high)
    magic_bytes, *offsets, timestamp_low, timestamp_high = struct.unpack(
        "<4s4x6IIi", buffer[0:40]
    )

    magic = magic_bytes.decode("utf-8", errors="ignore")

    # Destructure the 6 offset/size integers unpacked into `offsets`
    (
        autosave_index_offset,
        autosave_index_size,
        thumbnail_offset,
        thumbnail_size,
        game_data_offset,
        game_data_size,
    ) = offsets

    # Reconstruct the 64-bit timestamp from low and high 32-bit components
    timestamp = timestamp_low + (timestamp_high * 0x100000000)

    # Read strings using the specific character buffer sizes
    name = read_string(buffer, 40, 256)
    city_code = read_string(buffer, 296, 32)
    game_session_id = read_string(buffer, 328, 64)
    stats_json = read_string(buffer, 392, 512)

    # Default stats dictionary
    stats = {"stations": 0, "routes": 0, "trains": 0, "money": 0}

    # Attempt to parse JSON stats payload
    try:
        if stats_json.strip():  # Make sure it isn't an empty string
            stats = json.loads(stats_json)
    except (json.JSONDecodeError, TypeError):
        raise ValueError("Failed to parse stats from header")

    return HeaderData(
        magic=magic,
        autosaveIndexOffset=autosave_index_offset,
        autosaveIndexSize=autosave_index_size,
        thumbnailOffset=thumbnail_offset,
        thumbnailSize=thumbnail_size,
        gameDataOffset=game_data_offset,
        gameDataSize=game_data_size,
        timestamp=timestamp,
        name=name,
        cityCode=city_code,
        gameSessionId=game_session_id,
        stats=stats,
    )


def calculate_checksum(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def write_string(buffer: bytearray, offset: int, string_val: str, max_len: int):
    """
    Encodes a string to bytes and writes it into a bytearray at an offset, 
    padded with null bytes.
    """
    encoded = string_val.encode("utf-8")[:max_len]
    buffer[offset : offset + len(encoded)] = encoded
    # Null padding for the rest of the fixed space
    remaining = max_len - len(encoded)
    if remaining > 0:
        buffer[offset + len(encoded) : offset + max_len] = b"\x00" * remaining


def parse_metro_buffer(buffer: bytes) -> dict:
    """
    Parse a .metro save from bytes
    """

    # Verify magic
    magic = buffer[0:4].decode("utf-8", errors="ignore")
    if magic != MAGIC:
        raise ValueError(
            f'Invalid .metro file: magic bytes "{magic}" != "{MAGIC}"'
        )

    header = parse_header(buffer[0:HEADER_SIZE])

    # Read autosave index
    autosave_index = []
    if header.autosaveIndexSize > 0:
        index_bytes = buffer[
            header.autosaveIndexOffset : header.autosaveIndexOffset
            + header.autosaveIndexSize
        ]
        try:
            autosave_index = json.loads(index_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            warnings.warn("Failed to parse autosave index")

    # Read and decompress game data
    compressed_data = buffer[
        header.gameDataOffset : header.gameDataOffset + header.gameDataSize
    ]

    decompressed = zlib.decompress(compressed_data, 15 + 32)
    bundle = json.loads(decompressed.decode("utf-8"))

    # Extract main save data
    game_data = bundle.get("mainSave", bundle)

    return {
        "name": header.name,
        "cityCode": header.cityCode,
        "timestamp": header.timestamp,
        "gameSessionId": header.gameSessionId,
        "stats": header.stats,
        "data": game_data.get("data", game_data),
        "_headerBuffer": buffer[0:HEADER_SIZE],
        "_autosaveIndex": autosave_index,
    }


def serialize_metro_save(save_data: dict) -> bytes:
    """
    Serialize .metro save data to bytes
    """

    # Reconstruct bundle
    bundle = {
        "mainSave": {
            "id": save_data["gameSessionId"],
            "name": save_data["name"],
            "timestamp": save_data["timestamp"],
            "cityCode": save_data["cityCode"],
            "stats": save_data["stats"],
            "data": save_data["data"],
        },
        "autosaves": save_data.get("_autosaveIndex") or [],
    }

    # Compress bundle
    bundle_json = json.dumps(bundle, separators=(",", ":"))
    compressor = zlib.compressobj(
        wbits=16 + zlib.MAX_WBITS
    )  # 16 + MAX_WBITS forces gzip headers
    compressed = compressor.compress(bundle_json.encode("utf-8")) + compressor.flush()

    # Prepare autosave index
    autosave_index_json = json.dumps(
        save_data.get("_autosaveIndex") or [], separators=(",", ":")
    )
    autosave_index_buffer = autosave_index_json.encode("utf-8")

    # Calculate offsets
    autosave_index_offset = HEADER_SIZE
    autosave_index_size = len(autosave_index_buffer)
    game_data_offset = autosave_index_offset + autosave_index_size
    game_data_size = len(compressed)

    # Create header
    if save_data.get("_headerBuffer"):
        header = bytearray(save_data["_headerBuffer"])
    else:
        header = bytearray(HEADER_SIZE)

    # Write magic
    magic_bytes = MAGIC.encode("utf-8")
    header[0 : len(magic_bytes)] = magic_bytes

    # Write offsets using struct pack
    struct.pack_into("<I", header, 8, autosave_index_offset)
    struct.pack_into("<I", header, 12, autosave_index_size)
    struct.pack_into("<I", header, 24, game_data_offset)
    struct.pack_into("<I", header, 28, game_data_size)

    # Write timestamp (64-bit split into two 32-bit fields)
    timestamp = save_data["timestamp"]
    struct.pack_into("<I", header, 32, timestamp & 0xFFFFFFFF)
    struct.pack_into("<i", header, 36, int(timestamp // 0x100000000))

    # Write strings
    write_string(header, 40, save_data["name"], 256)
    write_string(header, 296, save_data["cityCode"], 32)
    write_string(header, 328, save_data["gameSessionId"], 64)
    write_string(
        header, 392, json.dumps(save_data["stats"], separators=(",", ":")), 512
    )

    # Calculate and write checksum
    checksum = calculate_checksum(compressed)
    struct.pack_into("<I", header, 912, checksum)

    # Combine all parts
    result = bytearray()
    result.extend(header)
    result.extend(autosave_index_buffer)
    result.extend(compressed)

    return bytes(result)


def is_metro_format(buffer: bytes) -> bool:
    """
    Check if buffer is .metro format
    """
    if len(buffer) < 4:
        return False

    try:
        magic = buffer[0:4].decode("utf-8")
        return magic == MAGIC
    except UnicodeDecodeError:
        return False


if __name__ == '__main__':
    fmetro, new_city_code = sys.argv[1], sys.argv[2] 
    with open(fmetro, 'rb') as f:
        metrodata = f.read()
    
    assert is_metro_format(metrodata), f"Unable to detect .metro format for file '{fmetro}'"
    
    data = parse_metro_buffer(metrodata)
    data['cityCode'] = new_city_code
    data['name'] = f"{new_city_code}_{data['name']}"
    
    updated_data = serialize_metro_save(data)

    parent = os.path.dirname(fmetro) # Returns empty string when fmetro is a bare filename
    fname_out = f"{new_city_code}_{os.path.basename(fmetro)}"
    fout = os.path.join(parent, fname_out) if parent else fname_out
    
    with open(fout, 'wb') as f:
        f.write(updated_data)
