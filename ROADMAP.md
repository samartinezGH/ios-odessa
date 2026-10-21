# Odessa Porting Roadmap

This roadmap tracks the work required to move the inherited iOS-sweet/XNU bring-up to the Motorola Moto G9 Plus (odessa). A checked box means the listed evidence exists; it does not imply later phases are complete.

## Phase 0 — Establish the target and preserve a safe baseline

- [x] Create the ios-odessa fork and identify the target as Moto G9 Plus XT2087-1.
- [x] Collect an initial live device-tree dump through read-only inspection.
- [ ] Record the exact regional variant, stock firmware build, bootloader state, and Android slot layout.
- [ ] Back up modem, persist, and calibration partitions outside the repository after validating the exact partition map and readback method.
- [x] Back up `super` and both slots of `boot`, `dtbo`, `vbmeta`, and `recovery` outside Git; verify exact sizes and SHA-256 hashes.
- [x] Record a clean upstream commit and keep Odessa changes separate from inherited SWEET history.

**Acceptance:** the project identifies one exact device variant and has a reproducible, sanitized hardware-data source. No partition has been written.

**Read-only snapshot (2026-10-21):** ADB sees XT2087-1 in recovery, active slot `_b`, DTB index 0, DTBO index 2, eight CPU entries, and 3734384 kB `MemTotal`. Recovery reports `ro.boot.flash.locked=0` and orange verified-boot state; the recovery environment identifies as `infinity_odessa` and runs kernel `4.14.190-FlopX-Kernel`, with 3383784 kB available memory. Its build fingerprint indicates Android 11 while release/SDK say 16/36; the backed-up active-slot boot header independently encodes Android 16.0.0 / 2025-08, but the installed system build ID still needs verification. No partition was written. A read-only backup of `super`, both `boot`/`dtbo`/`vbmeta`/`recovery` slots now exists outside Git; hashes and exact sizes have been verified. It excludes personal `userdata` and radio calibration partitions, which remain untouched.

The backed-up `boot_b` uses Android boot header v2 with 4096-byte pages and an embedded DTB. The backed-up `dtbo_b` contains three entries. Recovery reports applied index 2 (zero-based); that entry carries board ID `0x49`, revision `0xc0`, and contains the TXD FT8756 1080 × 2400 video-panel configuration. This matches the panel identified in the live device-tree inventory, but the overlay's presence does not establish that an iOS display driver can use it.

The sanitized hardware and recovery observations are also recorded in [`boards/odessa/profile.json`](boards/odessa/profile.json). This profile deliberately does not feed the inherited SWEET generators: reserved-memory ownership, boot handoff, and board-specific initialization still need verification first.

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

**Display evidence (2026-10-21):** recovery's DRM sysfs reports the TXD FT8756 DSI connector enabled at 1080 × 2400 / 60 Hz. Read-only DRM debugfs reports recovery's active plane as `XB24` / `DRM_FORMAT_XBGR8888`, linear, with a 4352-byte pitch. Its GEM allocation is separate from the boot DTB's `cont_splash_region`; this recovery buffer cannot stand in for the bootloader splash layout. The DTB has no simple-framebuffer node or splash stride/pixel-format property, so console writes remain disabled for device testing.

## Phase 2 — Understand the Motorola boot chain

- [x] Unpack the backed-up active-slot boot image and identify its Android boot header version, page size, kernel/ramdisk/DTB layout, and command line.
- [x] Inspect the active slot and match the bootloader-reported DTBO index to the backed-up overlay table.
- [x] Determine which boot-image packaging and signature/verification constraints apply to temporary fastboot boot.
- [x] Adapt the build helper to accept the Odessa stock DTB explicitly and fail early when required toolchain inputs are missing.
- [x] Emit and inspect a host-only packaging smoke image with the verified Odessa DTB and boot metadata; this image still contains unverified SWEET code and is not for device boot.
- [x] Add host-side parsing checks that compare the generated image components with the intended inputs byte-for-byte.
- [x] Make the empty diagnostic ramdisk deterministic so repeated builds with identical inputs produce the same image.

**Acceptance:** a generated image can be unpacked and all component offsets, sizes, DTB contents, and boot arguments match expectations. No image is flashed.

**Host-only packaging check (2026-10-21):** an initial smoke image's boot header and components were parsed and compared byte-for-byte against the intended inputs; that older image included inherited SWEET code and must not be booted. A later dedicated Odessa CPU/DTB diagnostic is built and validated separately, but its ABL entry-state and framebuffer assumptions still need device verification.

**Temporary boot check (2026-10-21):** after explicit approval, ABL accepted the inspected 446,464-byte diagnostic with `fastboot boot` and returned `OKAY`; no partition was written. The user clarified that the bootloader menu remained on **START**, which led to a normal Android startup; no diagnostic screen was observed. A subsequent read-only ADB check found Android 16 / SDK 36, active slot `_b`, and build display ID `infinity_odessa-userdebug 16 BP2A.250605.031.A2 eng.androi.20250809.184834 release-keys`; the reported fingerprint says Android 11 and remains inconsistent. The result does not confirm that the shim ran correctly; ABL handoff and framebuffer remain unresolved. The current rebuild is a different artifact and is not covered by the one-time approval.

**Reproducible host build (2026-10-21):** the generated empty `newc` ramdisk now uses fixed metadata and a normalized gzip header. Two consecutive builds with the same inputs produced identical kernel, ramdisk, and boot-image hashes. The image remains a diagnostic artifact and requires a new review/approval before any further device test.

## Phase 3 — Make the shim target-aware

- [x] Build a dedicated audit entry point that excludes inherited loader, UFS, MMU, GIC, PSCI, and reset probes; hold unexpected secondary CPUs in a WFE loop.
- [ ] Replace hard-coded SWEET framebuffer, GIC, UFS, reset, and memory values with an Odessa board profile or verified live-tree discovery.
- [ ] Keep register access read-only until each writable register and its required power/clock state are understood.
- [ ] Add a compact framebuffer diagnostic for exceptions and a persistent or host-readable log path.
- [ ] Confirm the shim's MMU mappings do not overlap secure memory or reserved carve-outs.
- [x] Build and inspect the audit image on the host; run its host-render and package-component checks.

**Acceptance:** the shim builds reproducibly for the Odessa profile and its host-side checks pass. It has not altered storage or boot partitions.

**Audit baseline (2026-10-21):** the build now compiles a dedicated Odessa entry point, startup, and console only. Unexpected secondary CPUs wait in an assembly WFE loop; no inherited hardware tests or SMC calls are included. One user-approved temporary boot of the inspected image was accepted by fastboot without flashing partitions. The phone returned to Android normally, but the user did not observe the diagnostic screen. The shim still writes to the reserved splash area using an unverified pixel format/stride; ABL entry-state assumptions remain unverified. Any next device test needs review of the exact image and separate approval.

## Phase 4 — Bring up XNU on Odessa

- [x] Define a distinct ODESSA machine configuration while retaining SWEET as a separate upstream target.
- [x] Add an isolated ODESSA machine-config scaffold in `xnu/patches/0082-odessa-machine-config.patch`, without enabling Sweet-only hardware behavior.
- [x] Record the initial XNU port boundary and target-specific bring-up order in [`xnu/ODESSA_PORTING.md`](xnu/ODESSA_PORTING.md).
- [x] Build the scaffold with `MACHINE_CONFIG=ODESSA` in CI and resolve all compile/configuration failures.
- [ ] Adapt the boot arguments, Apple Device Tree generation, and boot_args memory/video fields to the verified Motorola boot handoff.
- [x] Generate a host-only Odessa ADT and first XNU handoff image using the active FDT, conservative high-memory selection, separate payload magic, and video-disabled loader.
- [ ] Verify one CPU first: exception vectors, MMU, 16K page support, timer interrupts, GIC group/routing, and PSCI SMC calls.
- [ ] Bring up additional CPUs only after CPU identity, cluster topology, and CPU_ON behavior are verified.
- [ ] Adapt or disable SWEET-only drivers and patches until their hardware assumptions are proven.
- [ ] Keep QEMU regression checks for generic XNU and loader behavior; treat QEMU as insufficient evidence for Motorola hardware.

**Acceptance:** an Odessa-configured kernel reaches a stable diagnostic console and reports CPU, memory, timer, and interrupt state without mounting or writing a device partition.

**Compile-only milestone (2026-10-21):** GitHub Actions run [39644845368](https://github.com/samartinezGH/ios-odessa/actions/runs/39644845368) successfully built and linked the `DEVELOPMENT_ARM64_ODESSA` kernel from XNU 8796.141.3. The `xnu-kernel` artifact contains `kernel.development.odessa` (Mach-O arm64, 16,490,008 bytes; SHA-256 `03c3aef448ef889c12b2a2536a888204782a0e2c87d099cf0c315dea644aac38`). This verified compile/link only; the host handoff candidate and its remaining hardware/runtime blockers are documented below.

**Host-only Odessa handoff candidate (2026-10-21):** captured the active FDT read-only from `/sys/firmware/fdt` with ADB root. It reports RAM banks `[0x80000000, 0x100000000)` and `[0x100000000, 0x17dd00000)`. All fixed reserved-memory ranges are below 4 GiB; dynamic reserved pools declare allocation ranges ending below 4 GiB. `tools/mkadt_odessa.py` therefore selects only the upper 0x7dd00000-byte bank for the candidate ADT, and refuses the stock boot DTB because its `/memory/reg` is unpopulated. The generated ADT records eight CPU MPIDRs, PSCI by SMC, GICv3 at `0x17a00000` / `0x17a60000`, virtual timer PPI 19, and 19.2 MHz timer frequency. `shim/build_odessa_xnu.sh` packages the CI kernel as an `ODESSAXN` payload behind a loader that bounds-checks segments and leaves the framebuffer disabled. The latest Android boot image passed byte-for-byte header/component validation and is 16,318,464 bytes (SHA-256 `b077eae9f376b317680bef98575a2e5cf6ab2c79bfc523ed5f414a1f3c319d8d`). This is a host artifact only: it has not been booted, no console or root-storage path is enabled, and GIC/timer/PSCI and the ABL entry contract remain unverified. It is not an iOS image ready for device boot.

## Phase 5 — Add storage and a minimal root safely

- [ ] Verify the UFS controller and PHY sequencing; begin with read-only commands and non-user data.
- [ ] Map the Motorola partition table and A/B slots from stock metadata; do not reuse Redmi partition indices.
- [ ] Boot a RAM-disk test root before attempting any internal-storage root.
- [ ] Add read-only UFS support and confirm block addresses against recovery/Android metadata.
- [ ] Design an HFS+ or other supported test root image outside the phone and validate it on the host.
- [ ] Decide whether a device-resident root is necessary; document exactly which data would be overwritten before any write.

**Acceptance:** XNU can read a known test image and start a minimal init without modifying stock partitions. Any later write requires a verified backup and explicit user approval.

## Phase 6 — Start the iOS 16 userland

- [x] Acquire and inspect the iPhone X iOS 16.7.16 IPSW (build 20H392); its manifest supports iPhone10,3/iPhone10,6 and includes the D22AP tree. Keep firmware artifacts outside Git.
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

- Each device boot requires review of the exact diagnostic image and explicit approval; approval for an earlier image or one-time boot does not cover another test.
- Do not run fastboot flash or write to userdata, boot, vendor_boot, dtbo, vbmeta, recovery, modem, or persist as part of routine port development.
- Before any proposed write, state the exact partition, data loss, backup, and recovery path and obtain explicit approval.
