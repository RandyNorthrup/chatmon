"""Files that aren't on disk, as Windows describes them: plain Python, checked everywhere."""

import struct

from chatmon import attachments, winfiles


def descriptor(name: str, size: int | None = None, folder: bool = False) -> bytes:
    flags = (winfiles.FD_FILESIZE if size is not None else 0) | winfiles.FD_ATTRIBUTES
    attributes = winfiles.FILE_ATTRIBUTE_DIRECTORY if folder else 0x80  # FILE_ATTRIBUTE_NORMAL
    size = size or 0
    return struct.pack("<I16s8s8sI8s8s8sII520s", flags, b"", b"", b"", attributes, b"", b"", b"", size >> 32, size & 0xFFFFFFFF,
                       name.encode("utf-16-le"))


def group(*descriptors: bytes) -> bytes:
    return struct.pack("<I", len(descriptors)) + b"".join(descriptors)


def test_descriptions_name_files_and_skip_folders():
    raw = group(descriptor("report.pdf", 1234), descriptor("photos", folder=True), descriptor("photos\\cat.png"),
                descriptor("..\\..\\evil\x07.txt", 5), descriptor(""))
    assert [(o.index, o.name, o.size) for o in winfiles.parse(raw)] == [
        (0, "report.pdf", 1234), (2, "cat.png", None), (3, "evil.txt", 5), (4, "file", None),
    ]
    assert winfiles.parse(b"") == [] and winfiles.parse(struct.pack("<I", 50) + raw[4:600]) == [winfiles.Offered(0, "report.pdf", 1234)]  # cut short
    assert winfiles._DESCRIPTOR.size == 592  # sizeof(FILEDESCRIPTORW)


def test_only_what_can_be_attached_is_read():
    offered = [winfiles.Offered(i, f"{i}.txt", None) for i in range(attachments.MAX_COUNT + 2)]
    offered[1] = winfiles.Offered(1, "huge.iso", 5 * 2**30)
    offered[2] = winfiles.Offered(2, "empty.txt", 0)
    offered[3] = winfiles.Offered(3, "mail.msg", None)
    offered[4] = winfiles.Offered(4, "unsaid.bin", None)
    asked = []

    def fetch(index):
        asked.append(index)
        return {2: b"", 3: None, 4: b"x" * (attachments.MAX_FILE + 1)}.get(index, b"text")

    dropped = winfiles.read(offered, fetch)
    assert 1 not in asked and max(asked) == attachments.MAX_COUNT - 1  # never the one said to be too big, nor past the count
    assert [d.problem for d in dropped[:5]] == ["", "is too big (5120 MB)", "", "couldn't be read", f"is too big (over {attachments.MAX_FILE // 2**20} MB)"]
    assert dropped[0].data == b"text" and dropped[2].data == b"" and all(d.problem == "is one too many" for d in dropped[attachments.MAX_COUNT:])


def test_contents_are_judged_as_a_files_are():
    assert attachments.from_bytes(b"hello", "a.txt").kind == attachments.TEXT
    assert attachments.from_bytes(b"%PDF-1.4 x", "a.pdf").kind == attachments.PDF
    try:
        attachments.from_bytes(b"\x00\x01binary", "a.bin")
    except attachments.AttachError as exc:
        assert "isn't text, an image or a PDF" in str(exc)
    else:
        raise AssertionError("binary attached")
