# Odessa Phase 1 Hardware Matrix

Captured from the live Android device tree, read-only ADB inspection, the backed-up active boot image, and the matching Motorola Android 11 kernel source. This is an evidence inventory for Moto G9 Plus XT2087-1 (`odessa`, `qcom,sdmmagpie`), not a claim that XNU can use these devices yet. No partition was written during this audit.

Evidence labels:

- **Observed**: directly present in the live device tree, Android sysfs/properties, or stock-image metadata.
- **Source-confirmed**: matches the Motorola `android-11-release-rpa31.q2-59-17` source tree.
- **Unresolved**: the evidence is insufficient to select or safely use this value from XNU.

## CPU, memory, and interrupt platform

| Area | Evidence | State / implication |
|---|---|---|
| CPU identity | CPUs 0–5 report MIDR `0x51df805e` (Qualcomm part `0x805`); CPUs 6–7 report `0x51df804e` (part `0x804`). Upstream Linux labels parts `0x805`/`0x804` Kryo 4xx Silver/Gold, respectively. | Observed MIDRs and Linux topology. This is a 6+2 Kryo class split; CPU0 is the observed boot CPU and is the only CPU currently exported to the Odessa ADT. |
| CPU topology | Linux reports sibling groups `0–5` and `6–7`. FDT CPU nodes are `cpu@0`…`cpu@700`, with `reg` values `0, 0x100, …, 0x700`; FDT `cpu-map` references the nodes in 6+2 clusters. | The FDT affinities do not transparently match Linux's logical CPU IDs. The build resolves this by exporting only boot CPU affinity 0 and setting `cpus=1`; no unverified secondary affinity or `CPU_ON` call is used. |
| CPU features / PAC | Android `/proc/cpuinfo` reports FP, ASIMD, AES, PMULL, SHA1/2, CRC32, atomics, FP16, RDM, LRCPC, DCPoP, and dot product. Android's CPU-identification sysfs exposes MIDR/REVIDR only. | PAC is not required by this target build: ODESSA compiles as plain `arm64`/ARMv8.2-A and does not enable `arm64e` or PAC instructions. Exact PAC hardware capability is therefore not assumed or used. |
| Page size | Running Android config uses 4K pages and 39-bit VA. Arm Cortex-A76 and Cortex-A55 reference manuals specify 16K translation-granule support; Qualcomm identifies the Snapdragon 730G CPU as Kryo 470, based on Arm Cortex technology. | Android's 4K choice is an OS configuration, not a CPU limitation. The XNU build uses plain arm64 with a 16K kernel granule. The exact Qualcomm-masked ID register was not exposed by Android, so first-XNU MMU startup remains a runtime check before any root or peripheral driver. |
| RAM | FDT banks: `[0x80000000, 0x100000000)` and `[0x100000000, 0x17dd00000)`. ADB `/proc/iomem` lists the high bank within the running Android kernel's `System RAM` range. | Target-derived and independently used by Android as normal System RAM. The XNU ADT exposes only the high `0x7dd00000`-byte bank; low RAM stays excluded. ABL-to-XNU transfer still requires the later controlled boot check. |
| Reservations | FDT contains fixed carve-outs throughout low RAM, including duplicate/overlapping splash reservations at `0x9c000000` (`0x01700000` and `0x01800000`), and six dynamic allocation ranges ending below 4 GiB. The high bank has no FDT reservation overlap and is in Android `System RAM`. | The build uses only this FDT-derived high bank and does not map low carve-outs. Device-specific secure-world ownership beyond the published DT and Android System RAM map is outside this host acceptance and remains a boot-stage check. |
| DMA / IOMMU | Running kernel enables IOMMU/ARM SMMU; the device tree describes Qualcomm resources. | No DMA-capable driver is active in the host candidate. UFS and other DMA device paths remain opt-in/disabled pending driver bring-up; therefore no unverified DMA mapping is used by the accepted Phase 1 profile. |
| PSCI | `/psci` is `arm,psci-1.0`, method `smc`; all CPU nodes say `enable-method = psci`. | Observed DT declaration. XNU SMC conduit, affinity mapping and `CPU_ON` behavior are unverified on this device in this audit. |
| Timer | ARMv8 generic timer, FDT timebase 19.2 MHz; virtual timer spec resolves to PPI 19. | Observed. Interrupt delivery/routing to XNU is unverified. |
| GIC | GICv3 distributor `0x17a00000`, redistributor `0x17a60000`; FDT resource ranges are recorded in the board profile. | Observed. Group/security state and XNU IRQ setup are unresolved. |
| Boot security state | Android properties report locked/green, while the earlier raw kernel command line reported orange/unlocked-related state. | Conflicting observations. Do not infer whether temporary boot is available from Android properties alone; confirm in the bootloader before any device test. |

## Storage, display, touch, power, and USB

| Area | Evidence | State / implication |
|---|---|---|
| UFS | Live FDT: host `0x01d84000`/`0x3000`, QMP PHY `0x01d87000`/`0xddc`, ICE `0x01d90000`/`0x8000`, one lane each direction, named clocks/resets/supplies. Motorola source includes regulator votes, bus votes, controller reset/clocks, PHY/QMP setup, lane clocks, link startup and ICE integration. | DT and source-confirmed resources. XNU lacks the full power/PHY/link/ICE sequence; issuing UFS commands remains unsafe. |
| Partition map | Read-only GPT inventory is in [`partition-map.json`](partition-map.json); it records six UFS LUNs and A/B boot-critical partitions. | Observed. Starts/sizes are in Linux 512-byte sectors. No partition was opened for writing. `userdata` is the existing Android user-data partition; never use it as an iOS root image target. |
| Boot image | Active `boot_b`: Android boot header v2, 4096-byte page, embedded DTB; active slot `_b`. Applied DTBO index 2 of 3, entry board ID `0x49`, revision `0xc0`. | Observed from stock metadata and read-only Android state. This does not validate an XNU boot image or display handoff. |
| Display | Active panel is TXD FT8756, 1080×2400, DSI video mode at 60 Hz in recovery. Recovery scanout is XBGR8888, linear, pitch 4352. | Recovery facts are recorded. Splash layout remains unknown and is no longer written by the Odessa audit build: it links a no-op console and leaves boot video fields zero. |
| Touch | FocalTech FT8756 is attached under Qualcomm GENI SPI QUP SE6 at `0x00a80000`, max frequency 20 MHz, reset GPIO 8, IRQ GPIO 9, up to 10 contacts, coordinates 1080×2400. Controller clocks are named `se-clk`, `m-ahb`, and `s-ahb`. | Observed from active FDT. The node is panel-conditional, not unconditionally `okay`. GPIO controller/pinctrl are identified, but rail enablement, firmware, IRQ polarity/trigger, and XNU SPI/GENI behavior remain unresolved. |
| PMIC / keys | Device tree includes PM6150 and PM6150L PMIC nodes over Qualcomm SPMI, plus Qualcomm RPMh clock controller. GPIO keys include volume-up and assist; power-on controller is represented under PMIC PON. | Observed topology. Exact rail votes, RPMh/TCS protocol and key events are not implemented or verified in XNU. |
| USB | Live FDT contains Qualcomm DWC3, QUSB2 HS PHY and QMP SuperSpeed PHY resources; Android currently reports `mtp,adb`. | Observed. This describes Android's active mode, not a safe XNU USB initialization sequence. USB driver and PHY handoff remain unresolved. |

## Acceptance status and remaining runtime checks

1. Validate the ABL-to-XNU handoff and the 16K XNU MMU on-device before enabling memory allocation beyond the initial single CPU.
2. Reconcile the full CPU affinity map and validate PSCI before exporting secondary CPUs.
3. Obtain the splash format/stride before enabling framebuffer writes; the current Odessa audit build has framebuffer writes removed.
4. Port the full Qualcomm UFS resource/power/PHY/ICE sequence and DMA ownership before selecting `rd=ufsroot0`.
5. Keep touch, PMIC/RPMh, buttons and USB drivers disabled until their power, clock, interrupt and handoff behavior is implemented.
6. Resolve the Android-property/bootloader security-state discrepancy before any later temporary boot; no partition write is part of this phase.

**Phase 1 acceptance:** satisfied for the host-only Odessa profile. All addresses used by its single-CPU ADT are derived from the live Odessa FDT; Android independently reports the selected high-memory bank as `System RAM`. Unknown SMP, splash, DMA, UFS, touch, PMIC and USB behavior is removed from or disabled in the Odessa audit path. This closes the hardware-inventory acceptance, not the later device-boot or iOS-root milestones.

## Primary source references

- Motorola [sdmmagpie device tree](https://github.com/MotorolaMobilityLLC/kernel-msm/blob/android-11-release-rpa31.q2-59-17/arch/arm64/boot/dts/qcom/sdmmagpie.dtsi)
- Motorola [Qualcomm UFS host implementation](https://github.com/MotorolaMobilityLLC/kernel-msm/blob/android-11-release-rpa31.q2-59-17/drivers/scsi/ufs/ufs-qcom.c)
- Motorola [Qualcomm UFS PHY implementation](https://github.com/MotorolaMobilityLLC/kernel-msm/blob/android-11-release-rpa31.q2-59-17/drivers/phy/qualcomm/phy-qcom-ufs.c)
- Qualcomm [Snapdragon 730G product brief](https://www.qualcomm.com/content/dam/qcomm-martech/dm-assets/documents/qualcomm-snapdragon-730g-mobile-platform-product-brief.pdf) identifies Kryo 470 and a 2+6 performance/efficiency CPU topology.
- Upstream Linux [Qualcomm MIDR definitions](https://github.com/torvalds/linux/blob/master/arch/arm64/include/asm/cputype.h) identify Kryo 4xx Gold as part `0x804` and Silver as `0x805`.
- Arm [Cortex-A76 Technical Reference Manual](https://documentation-service.arm.com/static/5e81c5e8c07f701203ad0a9d) and [Cortex-A55 Technical Reference Manual](https://documentation-service.arm.com/static/5e7e1405b471823cb9de57ae) document 16KB translation granule support for those core implementations. Qualcomm's custom Kryo implementation still needs the initial XNU MMU runtime check.
