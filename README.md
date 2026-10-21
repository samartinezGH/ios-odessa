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
- Touch: FocalTech FT8756 over Qualcomm GENI SPI (QUP SE6, 0xa80000)

These are initial observations from the device tree, not a complete hardware bring-up. The raw dump is intentionally not included because it contains device identifiers and network addresses. Verify every address, clock, interrupt, memory reservation, and peripheral initialization sequence before using it in kernel code.

## Current status

| Area | Status |
| --- | --- |
| Fork and target identification | Complete |
| Read-only hardware inventory | Started; sanitized facts are recorded above |
| Odessa-specific shim and boot-image packaging | Not implemented |
| Odessa XNU machine configuration | Not implemented |
| iOS root image for Odessa | Not built |
| Kernel boot on the Moto G9 Plus | Not tested |
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
| shim/ | Inherited bare-metal boot shim; currently SWEET-specific |
| xnu/patches/ | Inherited XNU patches; hardware assumptions require review |
| tools/mkadt.py | Inherited Apple Device Tree generator; currently describes SWEET |
| tools/mkpayload.py | Packs an XNU kernel, Apple Device Tree, and boot arguments |
| tools/unpack_bootv2.py | Parses Android boot-image versions supported by the current helper |
| tools/ | Image, logging, validation, and QEMU helpers inherited from ios-sweet |
| NOTES.md | Active Odessa handoff followed by clearly marked upstream SWEET history |
| ROADMAP.md | Porting stages and completion criteria |

Names containing “sweet” remain in legacy source paths and symbols until the Odessa-specific implementation is designed. They do not imply support for Odessa.

## Language and contributions

Use English for documentation, code comments, commit messages, and build instructions so other Moto G9 Plus owners can follow the work. Include the exact device variant, firmware build, command, and observed result in engineering notes. Mark unverified assumptions as such.

## Upstream and firmware

This fork is based on [dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet). Apple's iOS firmware is not included; distribute or use it only in accordance with Apple's terms. This project is an experimental research port, not a secure or production-ready phone operating system.