# Odessa Phase 1 Hardware Matrix

Captured from the live Android device tree, read-only ADB inspection, the backed-up active boot image, and the matching Motorola Android 11 kernel source. This is an evidence inventory for Moto G9 Plus XT2087-1 (`odessa`, `qcom,sdmmagpie`), not a claim that XNU can use these devices yet. No partition was written during this audit.

Evidence labels:

- **Observed**: directly present in the live device tree, Android sysfs/properties, or stock-image metadata.
- **Source-confirmed**: matches the Motorola `android-11-release-rpa31.q2-59-17` source tree.
- **Unresolved**: the evidence is insufficient to select or safely use this value from XNU.

## CPU, memory, and interrupt platform

| Area | Evidence | State / implication |
|---|---|---|
| CPU identity | CPUs 0–5 report MIDR `0x51df805e` (part `0x805`); CPUs 6–7 report `0x51df804e` (part `0x804`). | Observed. These are two CPU classes; XNU startup on either class is unverified. |
| CPU topology | Linux reports sibling groups `0–5` and `6–7`. FDT CPU nodes are `cpu@0`…`cpu@700`, with `reg` values `0, 0x100, …, 0x700`; the FDT `cpu-map` references all eight nodes in 6+2 clusters. | Observed discrepancy in representation. Preserve both affinity IDs and cluster map; do not infer XNU logical CPU numbering or enable secondary CPUs until a vendor-source/PSCI mapping is proven. The current ADT builder drops the cluster map. |
| CPU features | Android `/proc/cpuinfo` reports FP, ASIMD, AES, PMULL, SHA1/2, CRC32, atomics, FP16, RDM, LRCPC, DCPoP, and dot product. | Observed Linux-exposed features. PAC and 16K granule capability were not exposed by this read-only interface; neither should be assumed from this list. |
| Page size | Running Android kernel config has `CONFIG_ARM64_4K_PAGES=y`, `CONFIG_ARM64_VA_BITS_39=y`; Android reports 4096-byte page size. | Observed kernel configuration, not proof that the CPU lacks 16K support. The XNU build/handoff uses 16K assumptions; compatibility remains unresolved and is a boot blocker. |
| RAM | FDT banks: `[0x80000000, 0x100000000)` and `[0x100000000, 0x17dd00000)`. | Observed. The second bank is `0x7dd00000` bytes. This is physical RAM, not proof that the bootloader transfers ownership of the whole bank to XNU. |
| Reservations | FDT contains fixed carve-outs throughout low RAM, including duplicate/overlapping splash reservations at `0x9c000000` (`0x01700000` and `0x01800000`), and dynamic allocation pools constrained below 4 GiB. No fixed/dynamic reservation intersects the upper bank in this capture. | Observed from this FDT only. Secure-world/XPU ownership, runtime allocations and bootloader allocations are not exhaustively proven. The conservative ADT builder selects the upper bank but must keep this as provisional until handoff ownership is verified. |
| DMA / IOMMU | Running kernel enables IOMMU and ARM SMMU; the device tree describes Qualcomm resources. | Observed capability/configuration only. XNU DMA masks, SMMU context setup, cache coherency and device ownership are unresolved. No DMA-capable driver is safe to enable on this evidence. |
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
| Display | Active panel is TXD FT8756, 1080×2400, DSI video mode at 60 Hz in recovery. Recovery scanout is XBGR8888, linear, pitch 4352. | Observed for recovery only. Bootloader splash `cont_splash_region` begins at `0x9c000000`; its pixel format, stride, cache policy, and ownership are unresolved. Recovery scanout details cannot be substituted for splash details. |
| Touch | FocalTech FT8756 is attached under Qualcomm GENI SPI QUP SE6 at `0x00a80000`, max frequency 20 MHz, reset GPIO 8, IRQ GPIO 9, up to 10 contacts, coordinates 1080×2400. Controller clocks are named `se-clk`, `m-ahb`, and `s-ahb`. | Observed from active FDT. The node is panel-conditional, not unconditionally `okay`. GPIO controller/pinctrl are identified, but rail enablement, firmware, IRQ polarity/trigger, and XNU SPI/GENI behavior remain unresolved. |
| PMIC / keys | Device tree includes PM6150 and PM6150L PMIC nodes over Qualcomm SPMI, plus Qualcomm RPMh clock controller. GPIO keys include volume-up and assist; power-on controller is represented under PMIC PON. | Observed topology. Exact rail votes, RPMh/TCS protocol and key events are not implemented or verified in XNU. |
| USB | Live FDT contains Qualcomm DWC3, QUSB2 HS PHY and QMP SuperSpeed PHY resources; Android currently reports `mtp,adb`. | Observed. This describes Android's active mode, not a safe XNU USB initialization sequence. USB driver and PHY handoff remain unresolved. |

## Required corrections before this phase can be considered hardware-ready

1. Fix or explicitly gate ADT CPU generation: preserve/resolve the FDT CPU affinity values and 6+2 cluster map; don't enable secondary CPUs yet.
2. Resolve the 4K Android versus 16K XNU granule assumptions and verify pointer-authentication capability from architectural ID registers or authoritative SoC documentation.
3. Prove which RAM is handed to the payload and exclude all secure, firmware, DMA and runtime carve-outs from XNU's cacheable mappings.
4. Obtain the bootloader splash format/stride and prove ABL handoff state before enabling framebuffer writes.
5. Keep UFS disabled until the complete Qualcomm resource/power/PHY/ICE sequence and DMA ownership are implemented.
6. Keep touch, PMIC/RPMh, buttons and USB disabled until their power, clock, interrupt and handoff behavior is understood.
7. Resolve the boot-state property/cmdline discrepancy at the bootloader without changing or flashing partitions.

**Phase 1 audit result:** the requested hardware comparison and read-only storage inventory are now documented, including all known unknowns. The Phase 1 *engineering acceptance gate* remains open: the unresolved items above prohibit claiming an XNU-ready hardware profile or a bootable image.

## Primary source references

- Motorola [sdmmagpie device tree](https://github.com/MotorolaMobilityLLC/kernel-msm/blob/android-11-release-rpa31.q2-59-17/arch/arm64/boot/dts/qcom/sdmmagpie.dtsi)
- Motorola [Qualcomm UFS host implementation](https://github.com/MotorolaMobilityLLC/kernel-msm/blob/android-11-release-rpa31.q2-59-17/drivers/scsi/ufs/ufs-qcom.c)
- Motorola [Qualcomm UFS PHY implementation](https://github.com/MotorolaMobilityLLC/kernel-msm/blob/android-11-release-rpa31.q2-59-17/drivers/phy/qualcomm/phy-qcom-ufs.c)
