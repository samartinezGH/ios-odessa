# Odessa XNU bring-up notes

This file tracks the first target-specific XNU work for the Moto G9 Plus
(XT2087-1). It is an engineering note, not a claim that an Odessa kernel can
already be built or booted.

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
6. Add read-only UFS and a RAM-disk root path; only then investigate the
   prepared iOS userland image.

## Current gate

An initial isolated `ODESSA` machine configuration is now represented by
`xnu/patches/0082-odessa-machine-config.patch`. It is an unbuilt scaffold:
there is no Odessa platform expert, XNU kernel artifact, or XNU boot test yet.
The current phone image is a diagnostic shim only. The next milestone is a CI
build with `MACHINE_CONFIG=ODESSA`, then fixes based on its build log; no device
boot or storage write is part of that milestone.
