"""Minimal NBT reader for Minecraft data files (player .dat files, level.dat).

Only reading is needed, so this stays dependency-free (one less package for
PyInstaller). Compounds become dicts, lists become lists, numbers become
int/float, byte/int/long arrays become lists of ints.
"""

import gzip
import io
import struct
import zlib

TAG_END, TAG_BYTE, TAG_SHORT, TAG_INT, TAG_LONG, TAG_FLOAT, TAG_DOUBLE = range(7)
TAG_BYTE_ARRAY, TAG_STRING, TAG_LIST, TAG_COMPOUND, TAG_INT_ARRAY, TAG_LONG_ARRAY = range(7, 13)

_MAX_DEPTH = 512


class NBTError(ValueError):
    pass


class _Reader:
    def __init__(self, data: bytes):
        self.buf = io.BytesIO(data)

    def _read(self, n):
        b = self.buf.read(n)
        if len(b) != n:
            raise NBTError("Unexpected end of NBT data")
        return b

    def _unpack(self, fmt, n):
        return struct.unpack(fmt, self._read(n))[0]

    def string(self):
        length = self._unpack(">H", 2)
        # Java "modified UTF-8"; plain UTF-8 decoding covers what we display.
        return self._read(length).decode("utf-8", errors="replace")

    def payload(self, tag, depth=0):
        if depth > _MAX_DEPTH:
            raise NBTError("NBT nesting too deep")
        if tag == TAG_BYTE:
            return self._unpack(">b", 1)
        if tag == TAG_SHORT:
            return self._unpack(">h", 2)
        if tag == TAG_INT:
            return self._unpack(">i", 4)
        if tag == TAG_LONG:
            return self._unpack(">q", 8)
        if tag == TAG_FLOAT:
            return self._unpack(">f", 4)
        if tag == TAG_DOUBLE:
            return self._unpack(">d", 8)
        if tag == TAG_BYTE_ARRAY:
            n = self._unpack(">i", 4)
            return list(struct.unpack(f">{n}b", self._read(n)))
        if tag == TAG_STRING:
            return self.string()
        if tag == TAG_LIST:
            item_tag = self._unpack(">b", 1)
            n = self._unpack(">i", 4)
            if n < 0:
                raise NBTError("Negative list length")
            return [self.payload(item_tag, depth + 1) for _ in range(n)]
        if tag == TAG_COMPOUND:
            out = {}
            while True:
                child = self._unpack(">b", 1)
                if child == TAG_END:
                    return out
                name = self.string()
                out[name] = self.payload(child, depth + 1)
        if tag == TAG_INT_ARRAY:
            n = self._unpack(">i", 4)
            return list(struct.unpack(f">{n}i", self._read(4 * n)))
        if tag == TAG_LONG_ARRAY:
            n = self._unpack(">i", 4)
            return list(struct.unpack(f">{n}q", self._read(8 * n)))
        raise NBTError(f"Unknown NBT tag {tag}")


def _decompress(raw: bytes) -> bytes:
    if raw[:2] == b"\x1f\x8b":
        return gzip.decompress(raw)
    if raw[:1] == b"\x78":  # zlib header
        try:
            return zlib.decompress(raw)
        except zlib.error:
            pass
    return raw


def loads(raw: bytes) -> dict:
    """Parse an NBT file's bytes (gzip, zlib or uncompressed) into a dict."""
    r = _Reader(_decompress(raw))
    tag = r._unpack(">b", 1)
    if tag != TAG_COMPOUND:
        raise NBTError("Root tag is not a compound")
    r.string()  # root name, usually empty
    return r.payload(TAG_COMPOUND)


def load(path: str) -> dict:
    with open(path, "rb") as f:
        return loads(f.read())
