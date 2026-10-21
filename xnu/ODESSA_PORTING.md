# Odessa XNU bring-up notes

This file tracks the target-specific XNU work for the Moto G9 Plus
(XT2087-1). The current kernel has passed a CI compile and link; it has not
been configured as a safe, bootable Odessa image or tested on the phone.

## Target facts

- Board identity: `odessa`, DT compatible `qcom,sdmmagpie`.
- Qualcomm platform: Snapdragon 730G / SM7150-AB, Kryo 470 CPU, Adreno 618.
- Live DTB CPU nodes use only the generic `arm,armv8` compatible and
  `enable-method = "psci"`. Read-only Android sysfs resolves the CPU groups:
  CPUs 0-5 share MIDR `0x51df805e` / capacity 492, while CPUs 6-7 share MIDR
  `0x51df804e` / capacity 1024. This establishes two groups for planning, but
  not XNU CPU startup or `CPU_ON` behavior.
- PSCI conduit: SMC.
- GICv3 bases from the sanitized device-tree inventory: distributor
  `0x17a00000`, redistributor `0x17a60000`.
- RAM banks and the phone's actual reservations are recorded in
  `boards/odessa/profile.json`; XNU must not claim all listed RAM blindly.

The live Android `/proc/cpuinfo` reports AES, PMULL, SHA, CRC32, atomics, and
other ARM features, and the MIDRs confirm two distinct Qualcomm core groups.
The isolated config uses plain arm64 and ARMv8.2-A + crypto as a compile-time
starting point. It does not enable optimized startup, timer routing, or SMP.

## Port boundary

`xnu/patches/` is a patch series against the pinned XNU build tree; it is not
an Odessa kernel tree. The current series changes board configuration,
platform expert, CPU startup, GIC/timer handling, PSCI/SMP, boot arguments,
ADT creation, framebuffer, UFS, and many iOS userland dependencies. Several
patches are explicitly guarded by `SWEET` and contain Sweet-specific
assumptions. Defining `SWEET` for Odessa to reuse them would also select
Sweet's identity and hardware behavior, so that is not a safe port strategy.

The new Odessa configuration must be independently selectable and must not
enable device drivers until each resource is derived from the Odessa DTB or
otherwise verified. The existing Sweet configuration remains unchanged.

## Bring-up order

1. Add `ODESSA` as a separate XNU machine configuration and an Odessa board
   header. Initially allow only generic arm64 startup and a one-CPU diagnostic
   path; do not inherit Sweet storage, display, touch, USB, or reset code.
2. Build XNU with `MACHINE_CONFIG=ODESSA` in CI and resolve compile/config
   failures before making a phone image.
3. Implement the Odessa DT/ADT-to-XNU boot handoff and memory map. Validate
   RAM exclusions against reserved-memory and bootloader ownership.
4. Bring up the boot CPU, exception vectors, MMU, and serial/host-readable
   diagnostics. Confirm timer INTID, GIC security/group routing, and PSCI
   behavior from target evidence before enabling interrupts or secondaries.
5. Add additional CPUs only after decoding affinity levels and checking MIDR,
   cache topology, and PSCI `CPU_ON` behavior. Do not reuse Sweet's topology
   limits.
6. Add read-only UFS and validate the controller's handoff/DMA path before
   using the prepared iOS userland image as a root volume.

## Current gate

An initial isolated `ODESSA` machine configuration is represented by
`xnu/patches/0082-odessa-machine-config.patch`. CI run
[39644845368](https://github.com/samartinezGH/ios-odessa/actions/runs/39644845368)
successfully compiled and linked `kernel.development.odessa` for XNU
8796.141.3. This establishes a compile scaffold only. The current Android boot
host candidate contains a separate Odessa XNU handoff loader, but no successful
device entry has been observed. The existing SWEET ADT generator and loader
must not be reused for Odessa without replacing their device-specific
assumptions.

An initial host-only Odessa ADT and XNU loader candidate now exist. The ADT
uses a live-FDT-derived upper RAM bank that does not overlap fixed reservations
or dynamic allocation ranges; the loader accepts an Odessa-specific payload,
checks payload bounds, and leaves video disabled. It carries the diagnostic
arguments `-v debug=0x14e cpus=1 keepsyms=1`; `shim/build_odessa_xnu.sh` accepts
an override through `XNU_CMDLINE`. A distinct Odessa read-only UFS patch
compiles and links in CI, but its root path is unvalidated; `rd=ufsroot0`
would select `userdata` by default, which is Android's encrypted data
partition, not the prepared HFS+ image. The loader has no verified diagnostic
output, and this candidate is not validated boot code or an iOS installer.

The matching Motorola source branch
[`android-11-release-rpa31.q2-59-17`](https://github.com/MotorolaMobilityLLC/kernel-msm/tree/android-11-release-rpa31.q2-59-17)
contains the `sdmmagpie` UFS host and Odessa DTS. Its Qualcomm driver sequences
regulators, bus votes, controller clocks/reset, QMP PHY power/configuration,
lane clocks, link startup, and ICE integration. The current XNU patch only
checks ABL's apparent live host state and replaces the UTRL; it does not port
those setup/resume paths or prove SMMU/DMA/cache behavior. Compile success is
not evidence that issuing even a read command is safe. Keep `rd=ufsroot0`
disabled until that sequence and hardware ownership are ported and reviewed.

## Audit findings for the first Odessa handoff

The inherited `tools/mkadt.py` and `shim/loader.c` are not suitable starting
inputs for a device image without substantial replacement:

- `mkadt.py --highmem` describes one contiguous range of `0x100000000` to
  `0x1fcc00000` (4.18 GiB). The sanitized Odessa profile observes a range of
  `0x100000000` to `0x17dd00000` (~1.96 GiB), before reservations. The low
  bank also has numerous secure, modem, multimedia, and splash carve-outs.
- The generator advertises Sweet identity, CPU topology, display, and boot
  values, including a synthetic Sweet ECID. Those values are not Odessa
  platform data. The shared GIC/UFS addresses alone do not make the ADT valid.
- `shim/loader.c` still has a SWEET path and hard-coded SWEET video values; the
  separate Odessa build selects `ODESSAXN`, omits video boot arguments, and
  bounds-checks its payload. The XNU entry contract remains unverified.
- The stock boot DTB gives a complex `/reserved-memory` map. A live FDT was
  captured read-only; use its reservation and allocation ranges, and do not
  derive a contiguous XNU RAM map by subtracting only obvious fixed carve-outs.
  Bootloader and secure-firmware ownership also matter.

## Experimental UFS scaffold

`xnu/patches/0083-odessa-readonly-ufs.patch` adapts the project's read-only
Qualcomm UFSHCI block driver as an Odessa-only device. It is selected only by
`rd=ufsroot0`; it checks that the controller is enabled and idle, verifies
64-bit DMA capability when the XNU allocation is above 4 GiB, then uses a
single polled request list and refuses block writes. The Odessa ADT generator
derives the UFS memory range from the active FDT and emits `/odessa-ufs` for
the driver. This is compile/bring-up scaffolding: the QCOM PHY/ICE state,
SMMU/IOMMU mapping, DMA coherence, and ABL controller handoff have not been
verified on Odessa. Do not set `rd=ufsroot0` against the current encrypted
Android userdata and do not overwrite userdata without an explicit, separate
approval for that exact operation.

The next engineering gate is observable, controlled XNU entry: verify the
ABL handoff contract and boot arguments, add a safe diagnostic path, then
validate early MMU/CPU startup, GIC interrupt routing, timer delivery, and
PSCI behavior. The current candidate has no console or root-storage path, so
it cannot confirm successful XNU entry or launch iOS. It has not been booted on
the phone. Do not attempt installation until a reviewed image has a verified
entry path and a root device that XNU can read.
