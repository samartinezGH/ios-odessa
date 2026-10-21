# iOS 16 on the Motorola Moto G9 Plus (odessa)

**An experimental, device-specific porting project.**

> The Odessa port is not bootable yet. This fork inherits code and research from ios-sweet, whose demonstrated target is the Redmi Note 10 Pro. No inherited kernel, boot image, device-tree configuration, or flashing procedure is validated for the Moto G9 Plus.

This repository is for adapting the XNU kernel and iOS 16 userland bring-up work to the Motorola Moto G9 Plus. The goal is a reproducible, temporary-boot development path that preserves the stock boot partitions while the port is experimental.

## Target device

The current target was identified from a live device-tree dump as:

- Product name: Motorola Moto G9 Plus
- Model variant: XT2087-1
- Device codename: odessa
- Qualcomm platform string: SDMMAGPIE
- Device-tree CPU nodes: eight; PSCI entry method is SMC
- Device-tree RAM map: 2 GiB at 0x80000000 and about 1.97 GiB at 0x100000000, before reserved-memory carve-outs
- GICv3 distributor: 0x17a00000; redistributors: 0x17a60000
- UFS controller: 0x1d84000
- Display: TXD FT8756 panel, 1080 × 2400
- Recovery DRM reports the DSI connector enabled at 1080 × 2400 / 60 Hz. Its active recovery scanout is `XB24` (`DRM_FORMAT_XBGR8888`, per the [Linux DRM FourCC definitions](https://github.com/torvalds/linux/blob/master/include/uapi/drm/drm_fourcc.h)) with a 4352-byte pitch, but this is a separate runtime buffer and does not identify the bootloader splash buffer's layout.
- The recovery environment reported product `infinity_odessa`, kernel `4.14.190-FlopX-Kernel`, and 3,383,784 KiB available memory during the 2026-10-21 read-only ADB snapshot. Recovery's release/SDK/fingerprint properties do not identify the installed system build.
- Boot splash reservation: `0x9c000000`–`0x9d700000` in the backed-up boot DTB; pixel format and row stride remain unverified
- Touch: FocalTech FT8756 over Qualcomm GENI SPI (QUP SE6, 0xa80000)

These are initial observations from the device tree, not a complete hardware bring-up. The raw dump is intentionally not included because it contains device identifiers and network addresses. Verify every address, clock, interrupt, memory reservation, and peripheral initialization sequence before using it in kernel code.

The sanitized, machine-readable inventory is in [`boards/odessa/profile.json`](boards/odessa/profile.json). It is an evidence record, not a boot configuration: all Odessa implementation flags remain false until the corresponding hardware path is verified and implemented.

The backed-up active-slot `boot_b` has Android boot header v2, 4096-byte pages, and embedded-DTB addressing that matches the current shim packager's header layout. Its encoded OS metadata decodes to Android 16.0.0 / 2025-08, so `shim/build.sh` now defaults to those observed values while allowing explicit environment overrides. The backed-up `dtbo_b` contains three overlays; recovery reports zero-based index 2, whose table entry is board ID `0x49`, revision `0xc0`, and includes the TXD FT8756 1080 × 2400 video-panel configuration. This does not make the inherited SWEET shim, ADT, or display path safe to boot on Odessa.

## Host build preparation

`shim/build.sh` uses an AArch64 bare-metal ELF cross-toolchain (`aarch64-none-elf-`) and Android's `mkbootimg` utility. On an Intel Mac, select Arm's `darwin-x86_64` host package and `aarch64-none-elf` target; newer releases may only offer Apple silicon packages, so check the host architecture listed for the selected release. Set `CROSS_COMPILE` to the toolchain's binary prefix and `MKBOOTIMG` to the Android `mkbootimg` executable or script. If the Intel-hosted GCC binary requires a missing Homebrew runtime library, Xcode Clang can compile the freestanding sources with `CC=clang TARGET_FLAGS="-target aarch64-none-elf"`; the cross toolchain's GNU linker and binutils remain in use.

The audit helper accepts the base DTB extracted from the same Moto G9 Plus stock boot image. Set `ODESSA_DTB` to that file before building; the default `../dtb/boot_unpacked/dtb` is only a conventional local path and is not included in Git. Keep the stock image and extracted DTB outside the repository. When no XNU payload is supplied, it creates a deterministic gzip-compressed `newc` root ramdisk. After packaging, the build checks the Android header and compares the embedded kernel, ramdisk, and DTB byte-for-byte with the inputs. Repeated builds with the same toolchain and inputs have been verified byte-for-byte on the development Mac. For example:

```sh
CROSS_COMPILE=/path/to/aarch64-none-elf/bin/aarch64-none-elf- \\
CC=clang TARGET_FLAGS="-target aarch64-none-elf" \\
MKBOOTIMG=/path/to/mkbootimg.py \\
ODESSA_DTB=/path/to/odessa/boot_b-unpacked/dtb \\
shim/build.sh
```

The audit build compiles a dedicated `shim/odessa_audit.c` entry point with startup and console code only; it excludes the inherited UFS, MMU, loader, and GIC probe files. Unexpected secondary CPUs wait without MMIO or PSCI calls, and the build rejects retained hardware-probe symbols or SMC instructions. The diagnostic writes to a framebuffer with unverified format and stride, and its assumed ABL entry state is not verified. One earlier user-approved temporary boot was accepted by fastboot, but Android started from the bootloader menu's **START** selection and no diagnostic screen was observed. This does not confirm that the shim ran or that XNU can boot.

The separate `tools/mkadt_odessa.py` and `shim/build_odessa_xnu.sh` path consumes an active FDT capture, derives an unreserved high-memory candidate, creates a minimal Odessa ADT, and packages the CI XNU kernel behind an Odessa-only loader. The loader leaves video disabled because the boot-splash pixel layout is unknown. The produced candidate is host-validated only: CPU/MMU startup, ABL handoff, GIC/timer/PSCI, diagnostics, and a root-storage path remain unverified. It contains no iOS root image and is not ready for a device boot.

## Current status

| Area | Status |
| --- | --- |
| Fork and target identification | Complete |
| Read-only hardware inventory | Active FDT captured; sanitized facts are recorded above |
| Odessa audit shim and boot-image packaging | Host diagnostic builds and validates; one approved temporary boot was accepted by fastboot, but the screen result is unconfirmed and ABL handoff/framebuffer layout remain unverified |
| Odessa XNU machine configuration | Experimental ODESSA config compiles and links in CI; host-only ADT and loader candidate built, hardware startup is not implemented |
| iOS root image for Odessa | iOS 16.7.16 HFS+ userland image prepared and checked on the Mac; no Odessa root-storage path connects it to XNU |
| XNU kernel boot on the Moto G9 Plus | Not tested; the current XNU handoff image has not been booted |
| iOS userspace on the Moto G9 Plus | Not tested |

The successful iOS home-screen milestone described by the upstream project applies to the Redmi Note 10 Pro only. It is not evidence that this fork boots on Odessa.

## Porting roadmap

See [ROADMAP.md](ROADMAP.md) for the staged work, dependencies, and acceptance criteria.

The existing shim, XNU patch series, device-tree generator, and hardware drivers are inherited SWEET-target work. Reuse them only after checking their assumptions against the Odessa hardware. In particular, the current shim and generator contain SWEET-specific MMIO addresses, memory ranges, CPU topology, touchscreen, panel, and boot-image assumptions.

## Safety and device data

- Do not use an inherited SWEET boot image on the Moto G9 Plus.
- Do not flash partitions as part of early bring-up. The first hardware milestones should use read-only inspection and host-side builds.
- Keep stock boot, DTB/DTBO, recovery, modem, persist, and calibration backups outside Git.
- Never commit raw device-tree dumps, partition images, serial numbers, MAC addresses, or downloaded Apple firmware.
- Treat any future root-image write as a destructive operation that needs a verified backup and a separate, explicit go-ahead.

## Repository map

| Path | Purpose |
| --- | --- |
| shim/ | Odessa audit entry point, experimental XNU loader, and inherited SWEET hardware code |
| xnu/patches/ | Inherited XNU patches; hardware assumptions require review |
| tools/mkadt.py | Inherited SWEET Apple Device Tree generator |
| tools/mkadt_odessa.py | Fail-closed ADT generator using a captured Odessa active FDT |
| tools/mkpayload.py | Packs an XNU kernel, Apple Device Tree, and boot arguments |
| tools/unpack_bootv2.py | Parses Android boot-image versions supported by the current helper |
| tools/ | Image, logging, validation, and QEMU helpers inherited from ios-sweet |
| ROADMAP.md | Porting stages and completion criteria |

Names containing “sweet” remain in legacy source paths and symbols until the Odessa-specific implementation is designed. They do not imply support for Odessa.

## Language and contributions

Use English for documentation, code comments, commit messages, and build instructions so other Moto G9 Plus owners can follow the work. Include the exact device variant, firmware build, command, and observed result in engineering notes. Mark unverified assumptions as such.

## Upstream and firmware

This fork is based on [dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet). Apple's iOS firmware is not included; distribute or use it only in accordance with Apple's terms. The local research input is the iPhone X IPSW for iOS 16.7.16 (build 20H392, D22AP); it supplies iOS userland and Apple device-tree reference material, not a Motorola boot image. Its contents and generated root images stay outside Git. This project is an experimental research port, not a secure or production-ready phone operating system.
