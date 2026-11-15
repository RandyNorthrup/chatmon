"""Files that aren't on disk, as Windows hands them over: an attachment dragged (or copied) out of Outlook, a
file out of a zip folder in Explorer, a picture out of a browser. They come as a list of descriptions
(FileGroupDescriptorW) and each one's contents (FileContents, by its place in the list), never as paths.
What's here is plain Python, so it's checked everywhere; windrop.py asks Windows for them.
https://learn.microsoft.com/en-us/windows/win32/shell/clipboard#cfstr_filedescriptor
https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/ns-shlobj_core-filedescriptorw
"""

from __future__ import annotations

import re
import struct
from collections.abc import Callable
from dataclasses import dataclass

from .attachments import MAX_COUNT, MAX_FILE
from .i18n import _

FD_ATTRIBUTES, FD_FILESIZE = 0x4, 0x40  # which of a description's fields are filled in
FILE_ATTRIBUTE_DIRECTORY = 0x10
# FILEDESCRIPTORW: flags, CLSID, SIZEL, POINTL, attributes, three FILETIMEs, size (high, low), name[260]
_DESCRIPTOR = struct.Struct("<I16s8s8sI8s8s8sII520s")


@dataclass(frozen=True)
class Offered:
    index: int  # its place in the list: which FileContents is its
    name: str
    size: int | None  # None: the source didn't say


@dataclass(frozen=True)
class Dropped:
    name: str
    data: bytes
    problem: str = ""  # why it wasn't read, as a sentence that names it: then `data` is empty


def parse(raw: bytes) -> list[Offered]:
    """The files a FILEGROUPDESCRIPTORW describes (never its folders), each named by its name alone: one in a
    folder of a zip comes as "folder\\name"."""
    if len(raw) < 4:
        return []
    (count,) = struct.unpack_from("<I", raw)
    offered = []
    for index in range(min(count, (len(raw) - 4) // _DESCRIPTOR.size)):
        flags, _, _, _, attributes, _, _, _, high, low, name = _DESCRIPTOR.unpack_from(raw, 4 + index * _DESCRIPTOR.size)
        if flags & FD_ATTRIBUTES and attributes & FILE_ATTRIBUTE_DIRECTORY:
            continue
        name = name.decode("utf-16-le", errors="replace").split("\0", 1)[0]
        name = "".join(c for c in re.split(r"[\\/]", name)[-1] if c.isprintable()).strip() or "file"
        offered.append(Offered(index, name, (high << 32 | low) if flags & FD_FILESIZE else None))
    return offered


def read(offered: list[Offered], fetch: Callable[[int], bytes | None]) -> list[Dropped]:
    """Each one's contents, from `fetch(index)` (at most MAX_FILE + 1 bytes; None if it couldn't be had): no
    more than can be attached to one question, and never one already said to be too big."""
    dropped = []
    for i, item in enumerate(offered):
        if i >= MAX_COUNT:
            # Never read: one question can't take it.
            dropped.append(Dropped(item.name, b"", _("{file} is one too many").format(file=item.name)))
            continue
        if item.size is not None and item.size > MAX_FILE:
            dropped.append(Dropped(item.name, b"", _("{file} is too big ({size} MB)").format(file=item.name, size=item.size // 2**20)))
            continue
        data = fetch(item.index)
        if data is None or (not data and item.size != 0):
            # An email out of Outlook, say, which comes as a store of its own, not as a file's bytes.
            dropped.append(Dropped(item.name, b"", _("{file} couldn't be read").format(file=item.name)))
        elif len(data) > MAX_FILE:
            dropped.append(Dropped(item.name, b"", _("{file} is too big (over {size} MB)").format(file=item.name, size=MAX_FILE // 2**20)))
        else:
            dropped.append(Dropped(item.name, data))
    return dropped
