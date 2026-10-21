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
6. Add read-only UFS and a RAM-disk root path; only then investigate the
   prepared iOS userland image.

## Current gate

An initial isolated `ODESSA` machine configuration is represented by
`xnu/patches/0082-odessa-machine-config.patch`. CI run
[39644845368](https://github.com/samartinezGH/ios-odessa/actions/runs/39644845368)
successfully compiled and linked `kernel.development.odessa` for XNU
8796.141.3. This establishes a compile scaffold only. The current Android boot
image contains a dedicated diagnostic shim, not the XNU loader; the existing
SWEET ADT generator and loader must not be reused for Odessa without replacing
their device-specific assumptions.

The next engineering gate is to implement an Odessa-specific ADT and loader
handoff with a RAM map that excludes all reserved regions, then verify XNU's
boot arguments and early CPU/MMU path. GIC interrupt routing, timer delivery,
and PSCI behavior remain disabled or unverified. Do not package the current
kernel as if it were bootable, and do not test it on the phone until this gate
is met.

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
- `loader.c` accepts only a `SWEETXNU` payload and writes SWEET framebuffer
  constants into XNU `boot_args`. The current build excludes this loader; the
  compiled artifact remains the separate audit shim, not XNU.
- The stock boot DTB gives a complex `/reserved-memory` map, while the current
  unprivileged Android ADB session cannot export the live tree. Do not derive
  a contiguous XNU RAM map by subtracting only the obvious fixed carve-outs;
  dynamic pools and ownership by ABL/secure firmware also matter.

The next host-side implementation should begin with an Odessa-specific
evidence-driven memory/ADT parser and explicit refusal to emit an XNU payload
while required reservations or boot handoff fields are unresolved. A working
image still depends on validated boot arguments, early MMU/CPU startup, GIC,
timer, and PSCI behavior. No new image was built or booted in this audit.
