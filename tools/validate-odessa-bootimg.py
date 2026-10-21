#!/usr/bin/env python3
"""Check an Odessa boot-image package against the exact host-side inputs.

This validates Android boot header v2 layout and byte-for-byte component
placement. It does not establish that the shim is safe to run on a phone.
"""
import argparse
import struct
import sys


PAGE_SIZE = 4096
ANDROID_VERSION = 0x20000198  # Android 16.0.0 / 2025-08 from stock boot_b.


def read(path):
    with open(path, "rb") as stream:
        return stream.read()


def align(value, alignment):
    return (value + alignment - 1) // alignment * alignment


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", help="generated Android boot image")
    parser.add_argument("kernel", help="expected kernel Image")
    parser.add_argument("ramdisk", help="expected ramdisk")
    parser.add_argument("dtb", help="expected stock Odessa DTB")
    args = parser.parse_args()

    image, kernel, ramdisk, dtb = map(read, (args.image, args.kernel, args.ramdisk, args.dtb))
    require(image[:8] == b"ANDROID!", "bad Android boot image magic")
    fields = struct.unpack_from("<10I", image, 8)
    kernel_size, kernel_addr, ramdisk_size, ramdisk_addr, second_size, _, tags_addr, page_size, version, os_version = fields
    require(version == 2, f"expected header v2, got v{version}")
    require(page_size == PAGE_SIZE, f"expected {PAGE_SIZE}-byte pages, got {page_size}")
    require(second_size == 0, f"unexpected second-stage component: {second_size} bytes")
    require((kernel_addr, ramdisk_addr, tags_addr) == (0x8000, 0x1000000, 0x100), "boot component addresses differ from stock boot_b")
    require(os_version == ANDROID_VERSION, f"unexpected Android version/patch metadata: 0x{os_version:08x}")
    require(kernel_size == len(kernel), "kernel size in header does not match input")
    require(ramdisk_size == len(ramdisk), "ramdisk size in header does not match input")

    recovery_size, _, header_size = struct.unpack_from("<IQI", image, 1632)
    dtb_size, dtb_addr = struct.unpack_from("<IQ", image, 1648)
    require(recovery_size == 0, f"unexpected recovery DTBO component: {recovery_size} bytes")
    require(header_size == 1660, f"unexpected v2 header size: {header_size}")
    require(dtb_addr == 0x1F00000, f"unexpected DTB load address: 0x{dtb_addr:x}")
    require(dtb_size == len(dtb), "DTB size in header does not match input")

    kernel_off = page_size
    ramdisk_off = kernel_off + align(kernel_size, page_size)
    second_off = ramdisk_off + align(ramdisk_size, page_size)
    dtb_off = second_off + align(second_size, page_size) + align(recovery_size, page_size)
    require(image[kernel_off:kernel_off + kernel_size] == kernel, "kernel bytes in image differ from input")
    require(image[ramdisk_off:ramdisk_off + ramdisk_size] == ramdisk, "ramdisk bytes in image differ from input")
    require(image[dtb_off:dtb_off + dtb_size] == dtb, "DTB bytes in image differ from input")
    require(len(image) == align(dtb_off + dtb_size, page_size), "unexpected trailing bytes or image length")

    cmdline = (image[64:576] + image[608:1632]).split(b"\0", 1)[0].decode("ascii", "replace")
    require(cmdline == "console=null", f"unexpected boot command line: {cmdline!r}")
    print(f"[OK] boot.img v2 layout matches inputs: kernel={kernel_size}, ramdisk={ramdisk_size}, dtb={dtb_size} bytes")
    print("[OK] offsets, addresses, OS metadata, command line, and image size match the Odessa boot_b profile")
    print("[INFO] This is a packaging check only; inherited SWEET code is not safe to boot on Odessa.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, struct.error) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)