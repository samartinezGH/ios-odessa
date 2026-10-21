# Odessa Porting Roadmap

This roadmap tracks the work required to move the inherited iOS-sweet/XNU bring-up to the Motorola Moto G9 Plus (odessa). A checked box means the listed evidence exists; it does not imply later phases are complete.

## Phase 0 — Establish the target and preserve a safe baseline

- [x] Create the ios-odessa fork and identify the target as Moto G9 Plus XT2087-1.
- [x] Collect an initial live device-tree dump through read-only inspection.
- [ ] Record the exact regional variant, stock firmware build, bootloader state, and Android slot layout.
- [ ] Keep stock boot, DTB/DTBO, recovery, modem, persist, and calibration backups outside the repository.
- [x] Record a clean upstream commit and keep Odessa changes separate from inherited SWEET history.

**Acceptance:** the project identifies one exact device variant and has a reproducible, sanitized hardware-data source. No partition has been written.

**Read-only snapshot (2026-10-21):** ADB currently sees XT2087-1 in recovery, active slot `_b`, DTB index 0, DTBO index 2, eight CPU entries, and 3734384 kB `MemTotal`. Recovery reports `ro.boot.flash.locked=0` and orange verified-boot state. Its build fingerprint indicates Android 11, but its release/SDK properties say 16/36, so the installed firmware build still needs independent confirmation from the normal OS or stock images. No partition content was read or written.

## Phase 1 — Build a verified hardware comparison

Compare the Odessa device tree and stock images against every hardware assumption in the inherited shim, XNU patches, and tools.

- [ ] Produce a sanitized hardware matrix for CPU MIDR/MPIDR topology, PSCI, timer frequency, GIC, page-size support, and pointer authentication.
- [ ] Reconcile both DDR banks, reserved-memory carve-outs, DMA limits, and the RAM range that XNU may safely own.
- [ ] Verify UFS host/PHY/ICE details and the exact partition map without issuing writes.
- [ ] Trace the boot framebuffer, display controller, panel timings, and handoff format.
- [ ] Trace the FT8756 touchscreen over GENI SPI: controller, clocks, GPIOs, reset, interrupt, power rails, and firmware behavior.
- [ ] Identify PMICs, buttons, regulators, RPMh/TCS requirements, USB controller state, and safe diagnostic access.
- [ ] Separate confirmed observations from hypotheses in NOTES.md.

**Acceptance:** every inherited address or hardware-specific behavior used in an Odessa build is either verified for XT2087-1 or replaced with a target-derived value. No raw serial or network identifiers are committed.

## Phase 2 — Understand the Motorola boot chain

- [ ] Unpack the exact stock boot image and identify its Android boot header version, page size, kernel/ramdisk/DTB layout, and command line.
- [ ] Inspect DTBO selection and the active A/B slot behavior.
- [ ] Determine which boot-image packaging and signature/verification constraints apply to temporary fastboot boot.
- [ ] Adapt the build scripts to consume the Odessa stock DTB and emit a correctly structured diagnostic image.
- [ ] Add host-side parsing checks that compare the generated image components with the intended inputs.

**Acceptance:** a generated image can be unpacked and all component offsets, sizes, DTB contents, and boot arguments match expectations. No image is flashed.

## Phase 3 — Make the shim target-aware

- [ ] Replace hard-coded SWEET framebuffer, GIC, UFS, reset, and memory values with an Odessa board profile or verified live-tree discovery.
- [ ] Keep register access read-only until each writable register and its required power/clock state are understood.
- [ ] Add a compact framebuffer diagnostic for exceptions and a persistent or host-readable log path.
- [ ] Confirm the shim's MMU mappings do not overlap secure memory or reserved carve-outs.
- [ ] Build and inspect the shim on the host; run its existing host-render checks.

**Acceptance:** the shim builds reproducibly for the Odessa profile and its host-side checks pass. It has not altered storage or boot partitions.

## Phase 4 — Bring up XNU on Odessa

- [ ] Define a distinct ODESSA machine configuration while retaining SWEET as a separate upstream target.
- [ ] Adapt the boot arguments, Apple Device Tree generation, and boot_args memory/video fields to the verified Motorola boot handoff.
- [ ] Verify one CPU first: exception vectors, MMU, 16K page support, timer interrupts, GIC group/routing, and PSCI SMC calls.
- [ ] Bring up additional CPUs only after CPU identity, cluster topology, and CPU_ON behavior are verified.
- [ ] Adapt or disable SWEET-only drivers and patches until their hardware assumptions are proven.
- [ ] Keep QEMU regression checks for generic XNU and loader behavior; treat QEMU as insufficient evidence for Motorola hardware.

**Acceptance:** an Odessa-configured kernel reaches a stable diagnostic console and reports CPU, memory, timer, and interrupt state without mounting or writing a device partition.

## Phase 5 — Add storage and a minimal root safely

- [ ] Verify the UFS controller and PHY sequencing; begin with read-only commands and non-user data.
- [ ] Map the Motorola partition table and A/B slots from stock metadata; do not reuse Redmi partition indices.
- [ ] Boot a RAM-disk test root before attempting any internal-storage root.
- [ ] Add read-only UFS support and confirm block addresses against recovery/Android metadata.
- [ ] Design an HFS+ or other supported test root image outside the phone and validate it on the host.
- [ ] Decide whether a device-resident root is necessary; document exactly which data would be overwritten before any write.

**Acceptance:** XNU can read a known test image and start a minimal init without modifying stock partitions. Any later write requires a verified backup and explicit user approval.

## Phase 6 — Start the iOS 16 userland

- [ ] Reuse the iPhone X iOS 16.7.16 userland only after validating its architecture, cache, and platform assumptions on the Odessa kernel.
- [ ] Build and inspect the root image entirely on the host; keep Apple firmware out of Git.
- [ ] Bring up dyld, launchd, essential daemons, and crash/log collection in small steps.
- [ ] Keep SWEET-specific identity, activation, storage, display, and watchdog workarounds disabled until independently justified for this port.

**Acceptance:** launchd remains running on a host-built test root and each failure can be diagnosed from captured logs. This milestone does not imply a working GUI or phone.

## Phase 7 — Display, touch, and basic interaction

- [ ] Present the Motorola 1080 × 2400 panel mode using the Odessa bootloader framebuffer or a verified display path.
- [ ] Add a CPU-rendered display service before attempting GPU support.
- [ ] Implement FT8756 SPI transactions using the verified GPIO, interrupt, clock, reset, and power configuration.
- [ ] Translate touch events to the HID interface expected by the iOS 16 userland.
- [ ] Bring up power and volume keys and verify wake/lock behavior.

**Acceptance:** a stable lock screen or equivalent test UI renders, and touch/buttons produce correct events across repeated temporary boots.

## Phase 8 — Expand device support

- [ ] Bring up USB logging and networking without depending on an unverified iOS network interface.
- [ ] Investigate audio, Wi-Fi, Bluetooth, cameras, sensors, battery reporting, and GPU independently.
- [ ] Document unsupported features, security limitations, performance, and variant-specific differences.
- [ ] Avoid security-sensitive workarounds that are not required for the research goal.

**Acceptance:** each feature has a reproducible test and a clearly documented supported/unsupported state.

## Phase 9 — Reproducible public release

- [ ] Add an Odessa-specific build workflow and pin all external source revisions.
- [ ] Ensure no private device dumps, keys, Apple firmware, or generated root images enter GitHub.
- [ ] Publish exact build requirements, checksums for project-produced artifacts, and recovery instructions.
- [ ] Have another XT2087-1 owner reproduce the host build from a clean checkout before claiming device support.

**Acceptance:** a clean checkout builds the documented diagnostic image and another owner can reproduce the same result without relying on private files.

## Explicit safety gates

- Do not run fastboot boot until a specific diagnostic image has been inspected and the user explicitly approves that device test.
- Do not run fastboot flash or write to userdata, boot, vendor_boot, dtbo, vbmeta, recovery, modem, or persist as part of routine port development.
- Before any proposed write, state the exact partition, data loss, backup, and recovery path and obtain explicit approval.
