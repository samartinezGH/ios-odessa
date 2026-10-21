#!/usr/bin/env python3
"""Write a deterministic gzip-compressed newc archive containing only its root."""

import pathlib
import struct
import sys
import zlib


def newc_entry(name, *, ino, mode, nlink):
	name_bytes = name.encode("ascii") + b"\0"
	fields = (
		ino,
		mode,
		0,  # uid
		0,  # gid
		nlink,
		0,  # mtime
		0,  # file size
		0,  # device major
		0,  # device minor
		0,  # special-device major
		0,  # special-device minor
		len(name_bytes),
		0,  # checksum (newc)
	)
	entry = b"070701" + b"".join(f"{field:08x}".encode("ascii") for field in fields)
	entry += name_bytes
	entry += b"\0" * (-len(entry) % 4)
	return entry


def main():
	if len(sys.argv) != 2:
		raise SystemExit(f"usage: {sys.argv[0]} OUTPUT.gz")

	archive = newc_entry(".", ino=1, mode=0o040755, nlink=2)
	archive += newc_entry("TRAILER!!!", ino=0, mode=0, nlink=1)
	archive += b"\0" * (-len(archive) % 512)

	compressor = zlib.compressobj(level=9, wbits=-zlib.MAX_WBITS)
	deflate = compressor.compress(archive) + compressor.flush()
	gzip_header = b"\x1f\x8b\x08\x00" + struct.pack("<I", 0) + b"\x02\xff"
	gzip_trailer = struct.pack("<II", zlib.crc32(archive), len(archive) & 0xFFFFFFFF)
	pathlib.Path(sys.argv[1]).write_bytes(gzip_header + deflate + gzip_trailer)


if __name__ == "__main__":
	main()
