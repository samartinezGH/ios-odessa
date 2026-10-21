#!/usr/bin/env python3
"""Validate repository integrity, patch sequences, and script syntax.

  tools/validate-repo.py [--verbose]

Checks:
  1. Patch sequence in xnu/patches/:
     - Sequential numbering starting at 0001 with no duplicates or gaps.
     - Patch files are non-empty and have valid unified diff markers.
  2. Python script syntax:
     - All tools/*.py compile cleanly via py_compile.
  3. Shell script syntax:
     - All tools/*.sh, shim/*.sh, and xnu/patches/*.sh pass bash -n check.
"""
import argparse, glob, json, os, py_compile, re, subprocess, sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def green(text): return f"\033[92m{text}\033[0m"
def red(text): return f"\033[91m{text}\033[0m"
def bold(text): return f"\033[1m{text}\033[0m"


def validate_patches(verbose=False):
    patch_dir = os.path.join(REPO_ROOT, 'xnu/patches')
    patch_files = sorted(glob.glob(os.path.join(patch_dir, '*.patch')))
    if not patch_files:
        print(red("[-] Error: No patch files found in xnu/patches/"))
        return False

    errors = []
    seen_numbers = {}

    for path in patch_files:
        fname = os.path.basename(path)
        m = re.match(r'^(\d{4})-(.+)\.patch$', fname)
        if not m:
            errors.append(f"Invalid patch filename format: {fname}")
            continue

        num = int(m.group(1))
        if num in seen_numbers:
            errors.append(f"Duplicate patch number {num:04d}: {fname} and {seen_numbers[num]}")
        seen_numbers[num] = fname

        size = os.path.getsize(path)
        if size == 0:
            errors.append(f"Patch is empty: {fname}")
            continue

        with open(path, 'r', errors='ignore') as f:
            head = f.read(2048)
            if not ('--- ' in head or 'diff ' in head or 'Index:' in head):
                errors.append(f"Patch missing standard diff header: {fname}")

    # Check contiguous sequence
    if seen_numbers:
        sorted_nums = sorted(seen_numbers.keys())
        expected = 1
        for num in sorted_nums:
            if num != expected:
                errors.append(f"Gap in patch sequence: expected {expected:04d}, found {num:04d} ({seen_numbers[num]})")
                expected = num + 1
            else:
                expected += 1

    if errors:
        print(red(f"[-] Patch validation failed with {len(errors)} error(s):"))
        for err in errors:
            print(f"    - {err}")
        return False

    print(green(f"[✓] Validated {len(patch_files)} patches (0001-{len(patch_files):04d} contiguous, format OK)"))
    return True


def validate_python_scripts(verbose=False):
    tools_dir = os.path.join(REPO_ROOT, 'tools')
    py_files = sorted(glob.glob(os.path.join(tools_dir, '*.py')))
    errors = []

    for path in py_files:
        fname = os.path.basename(path)
        try:
            py_compile.compile(path, doraise=True)
            if verbose:
                print(f"    [OK] {fname}")
        except py_compile.PyCompileError as e:
            errors.append(f"{fname}: {e}")

    if errors:
        print(red(f"[-] Python syntax validation failed with {len(errors)} error(s):"))
        for err in errors:
            print(f"    - {err}")
        return False

    print(green(f"[✓] Validated {len(py_files)} Python tools (syntax OK)"))
    return True


def validate_shell_scripts(verbose=False):
    sh_files = sorted(
        glob.glob(os.path.join(REPO_ROOT, 'tools/*.sh')) +
        glob.glob(os.path.join(REPO_ROOT, 'shim/*.sh')) +
        glob.glob(os.path.join(REPO_ROOT, 'xnu/patches/*.sh'))
    )
    errors = []

    for path in sh_files:
        rel = os.path.relpath(path, REPO_ROOT)
        res = subprocess.run(['bash', '-n', path], capture_output=True, text=True)
        if res.returncode != 0:
            errors.append(f"{rel}: {res.stderr.strip()}")
        elif verbose:
            print(f"    [OK] {rel}")

    if errors:
        print(red(f"[-] Shell syntax validation failed with {len(errors)} error(s):"))
        for err in errors:
            print(f"    - {err}")
        return False

    print(green(f"[✓] Validated {len(sh_files)} Shell scripts (syntax OK)"))
    return True


def validate_odessa_profile(verbose=False):
    """Keep the Odessa evidence profile explicit and non-bootable until verified."""
    path = os.path.join(REPO_ROOT, 'boards/odessa/profile.json')
    try:
        with open(path, encoding='utf-8') as f:
            profile = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(red(f"[-] Odessa profile could not be read: {e}"))
        return False

    device = profile.get('device', {})
    recovery = profile.get('recovery_snapshot', {})
    display = recovery.get('display', {})
    boot = profile.get('stock_boot_b_observation', {})
    dtbo = profile.get('stock_dtbo_b_observation', {})
    implementation = profile.get('implementation_status', {})
    errors = []
    if (device.get('model'), device.get('codename')) != ('XT2087-1', 'odessa'):
        errors.append('target identity must remain Moto G9 Plus XT2087-1 (odessa)')
    active_scanout = display.get('active_recovery_scanout', {})
    recovery_env = recovery.get('recovery_environment', {})
    if (recovery_env.get('product_name'), recovery_env.get('kernel_release'),
            recovery_env.get('mem_available_kib')) != ('infinity_odessa', '4.14.190-FlopX-Kernel', 3383784):
        errors.append('recovery environment fields must match the sanitized read-only ADB snapshot')
    if (display.get('connector'), display.get('enabled'), display.get('panel_name'), display.get('mode')) != ('DSI-1', True, 'txd_ft8756_fhd_vid', '1080x2400 at 60 Hz'):
        errors.append('recovery display observation must match the read-only DRM connector report')
    if (active_scanout.get('fourcc'), active_scanout.get('drm_format'), active_scanout.get('modifier'), active_scanout.get('pitch_bytes')) != ('XB24', 'DRM_FORMAT_XBGR8888', 'linear', 4352):
        errors.append('active recovery framebuffer must match the read-only DRM debugfs state')
    if (display.get('boot_splash_pixel_format'), display.get('boot_splash_stride_bytes')) != (None, None):
        errors.append('recovery scanout must not be presented as verified boot splash layout')
    if profile.get('status') != 'inventory_only':
        errors.append('profile status must stay inventory_only until the board port is implemented')
    if not implementation or any(implementation.values()):
        errors.append('unimplemented Odessa boot milestones must not be marked complete')
    panel = dtbo.get('panel_overlay', {})
    entry = dtbo.get('reported_entry', {})
    splash = profile.get('device_tree_observations', {}).get('boot_splash_reservation', {})
    if (dtbo.get('entry_count'), dtbo.get('recovery_reported_applied_index'), dtbo.get('indexing')) != (3, 2, 'zero_based'):
        errors.append('DTBO table count and applied zero-based index must match the local recovery observation')
    if (entry.get('id'), entry.get('revision')) != ('0x00000049', '0x000000c0'):
        errors.append('reported DTBO entry ID/revision must match the backed-up index 2 entry')
    if (panel.get('name'), panel.get('controller'), panel.get('mode')) != ('mipi_mot_vid_txd_1080p_681', 'FT8756', 'dsi_video_mode'):
        errors.append('reported Odessa overlay must identify the observed FT8756 TXD video panel')
    if (splash.get('base'), splash.get('size'), splash.get('pixel_format'), splash.get('stride_bytes')) != ('0x9c000000', '0x01700000', None, None):
        errors.append('splash reservation must match the boot DTB and leave unknown pixel layout unset')
    build_path = os.path.join(REPO_ROOT, 'shim/build.sh')
    with open(build_path, encoding='utf-8') as f:
        build_script = f.read()
    boot_args = {
        'android_boot_header_version': (2, '--header_version 2'),
        'page_size': (4096, '--pagesize 4096'),
        'kernel_address': ('0x00008000', '--kernel_offset 0x8000'),
        'ramdisk_address': ('0x01000000', '--ramdisk_offset 0x1000000'),
        'tags_address': ('0x00000100', '--tags_offset 0x100'),
        'dtb_address': ('0x01f00000', '--dtb_offset 0x1f00000'),
    }
    if any(boot.get(key) != value or token not in build_script
           for key, (value, token) in boot_args.items()):
        errors.append('shim boot-image layout no longer matches the observed boot_b header')
    if '--os_version "$OS_VERSION"' not in build_script or '--os_patch_level "$OS_PATCH_LEVEL"' not in build_script:
        errors.append('shim boot-image metadata must be supplied through the observed OS version settings')
    if 'OS_VERSION="${OS_VERSION:-16.0.0}"' not in build_script or 'OS_PATCH_LEVEL="${OS_PATCH_LEVEL:-2025-08}"' not in build_script:
        errors.append('shim OS metadata defaults must match the observed active-slot boot image')
    if 'ODESSA_DTB="${ODESSA_DTB:-../dtb/boot_unpacked/dtb}"' not in build_script or '--dtb "$ODESSA_DTB"' not in build_script:
        errors.append('shim must consume an explicitly supplied Odessa stock DTB')
    if 'CROSS_COMPILE="${CROSS_COMPILE:-aarch64-none-elf-}"' not in build_script:
        errors.append('shim default cross-compiler must target bare-metal AArch64 ELF')
    if 'LD="${LD:-${CROSS_COMPILE}ld}"' not in build_script or '$LD -static -T shim.ld --build-id=none --gc-sections' not in build_script:
        errors.append('shim must link ELF objects with the target linker directly')
    if '-ffunction-sections -fdata-sections' not in build_script or 'inherited loader/hardware/reset routine remains in the Odessa audit image' not in build_script:
        errors.append('Odessa audit image must discard and reject unreferenced inherited hardware paths')
    if 'MKBOOTIMG="${MKBOOTIMG:-mkbootimg}"' not in build_script or '"$MKBOOTIMG" --header_version 2' not in build_script:
        errors.append('shim must allow an explicit Android mkbootimg executable')
    if 'validate-odessa-bootimg.py out/shim-boot.img out/Image out/ramdisk.bin "$ODESSA_DTB"' not in build_script:
        errors.append('shim must validate packaged boot-image components against their host inputs')
    if '-fno-jump-tables' not in build_script:
        errors.append('freestanding shim objects must avoid absolute string jump-table relocations')
    if 'end_hex=$($NM out/shim.elf' not in build_script or "int(sys.argv[1], 16)" not in build_script:
        errors.append('shim image sizing must use the portable ELF end-symbol conversion')
    if errors:
        print(red("[-] Odessa profile validation failed:"))
        for err in errors:
            print(f"    - {err}")
        return False
    if verbose:
        print(f"    [OK] {os.path.relpath(path, REPO_ROOT)}: target identity and implementation status")
    print(green("[✓] Validated Odessa evidence profile (inventory only; no boot/write claims)"))
    return True


def main():
    ap = argparse.ArgumentParser(description="Validate repository integrity, patches, and scripts.")
    ap.add_argument('-v', '--verbose', action='store_true', help='Show detailed per-file output')
    a = ap.parse_args()

    print(bold("=== Running ios-sweet Repository Validation ==="))
    ok_patches = validate_patches(a.verbose)
    ok_python = validate_python_scripts(a.verbose)
    ok_shell = validate_shell_scripts(a.verbose)
    ok_odessa = validate_odessa_profile(a.verbose)

    if ok_patches and ok_python and ok_shell and ok_odessa:
        print(bold(green("\nAll repository integrity checks PASSED successfully!")))
        return 0
    else:
        print(bold(red("\nRepository integrity check FAILED.")))
        return 1


if __name__ == '__main__':
    sys.exit(main())
