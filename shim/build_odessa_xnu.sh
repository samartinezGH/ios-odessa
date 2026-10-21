#!/bin/bash
# Build an experimental Odessa XNU handoff image for host inspection only.
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
CALLER_DIR=$(pwd)
cd "$SCRIPT_DIR"

if [ "$#" -ne 3 ]; then
	echo "usage: $0 XNU_KERNEL ACTIVE_FDT STOCK_BOOT_DTB" >&2
	exit 2
fi
resolve_input() {
	case "$1" in
		/*) printf '%s\n' "$1" ;;
		*) (cd "$CALLER_DIR/$(dirname "$1")" && printf '%s/%s\n' "$(pwd)" "$(basename "$1")") ;;
	esac
}
XNU_KERNEL=$(resolve_input "$1")
ACTIVE_FDT=$(resolve_input "$2")
BOOT_DTB=$(resolve_input "$3")
[ -f "$XNU_KERNEL" ] && [ -f "$ACTIVE_FDT" ] && [ -f "$BOOT_DTB" ] || {
	echo "error: XNU kernel, active FDT, or stock boot DTB is missing" >&2
	exit 1
}

TOOL_PREFIX="${ODESSA_TOOL_PREFIX:-$REPO_ROOT/../toolchains/arm-14.2/arm-gnu-toolchain-14.2.rel1-darwin-x86_64-aarch64-none-elf/bin/aarch64-none-elf-}"
CC="${CC:-clang}"
TARGET_FLAGS="${TARGET_FLAGS:--target aarch64-none-elf}"
MKBOOTIMG="${MKBOOTIMG:-$REPO_ROOT/../toolchains/mkbootimg/mkbootimg.py}"
OUT_DIR="${OUT_DIR:-$SCRIPT_DIR/out/odessa-xnu-candidate}"
OS_VERSION="${OS_VERSION:-16.0.0}"
OS_PATCH_LEVEL="${OS_PATCH_LEVEL:-2025-08}"
CFLAGS="-O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector -fno-jump-tables -ffunction-sections -fdata-sections -Wall -Wextra -DODESSA"

for tool in "$CC" "${TOOL_PREFIX}ld" "${TOOL_PREFIX}objcopy" \
	"${TOOL_PREFIX}readelf" "${TOOL_PREFIX}nm" "${TOOL_PREFIX}objdump" \
	python3 "$MKBOOTIMG" truncate awk; do
	command -v "$tool" >/dev/null 2>&1 || {
		echo "error: required build tool not found: $tool" >&2
		exit 1
	}
done

mkdir -p "$OUT_DIR"
python3 ../tools/mkadt_odessa.py "$ACTIVE_FDT" "$OUT_DIR/odessa.adt"
python3 ../tools/mkpayload.py "$XNU_KERNEL" "$OUT_DIR/odessa.adt" \
	"$OUT_DIR/odessa-xnu-payload.bin" --target ODESSA \
	--cmdline='debug=0x14e cpus=1 keepsyms=1'

for source in start.S loader.c fdt.c odessa_xnu_entry.c odessa_xnu_console.c; do
	"$CC" $TARGET_FLAGS $CFLAGS -I. -c "$source" -o "$OUT_DIR/${source%.*}.o"
done
if "${TOOL_PREFIX}nm" "$OUT_DIR"/*.o | grep -Eq '[[:space:]](test_ufs|test_gic|reset|test_smp)$'; then
	echo "error: unexpected hardware probe in Odessa XNU loader" >&2
	exit 1
fi
"${TOOL_PREFIX}ld" -static -T shim.ld --build-id=none --gc-sections \
	--no-warn-rwx-segments -N "$OUT_DIR/start.o" "$OUT_DIR/loader.o" \
	"$OUT_DIR/fdt.o" "$OUT_DIR/odessa_xnu_entry.o" \
	"$OUT_DIR/odessa_xnu_console.o" -o "$OUT_DIR/odessa-xnu-loader.elf"
"${TOOL_PREFIX}objcopy" -O binary "$OUT_DIR/odessa-xnu-loader.elf" "$OUT_DIR/Image"
end_hex=$("${TOOL_PREFIX}nm" "$OUT_DIR/odessa-xnu-loader.elf" | awk '$3=="_end"{print $1}')
[ -n "$end_hex" ] || { echo "error: _end symbol missing" >&2; exit 1; }
image_size=$(python3 -c 'import sys; print(int(sys.argv[1], 16))' "$end_hex")
truncate -s "$image_size" "$OUT_DIR/Image"

"$MKBOOTIMG" --header_version 2 --kernel "$OUT_DIR/Image" \
	--ramdisk "$OUT_DIR/odessa-xnu-payload.bin" --dtb "$BOOT_DTB" \
	--base 0 --kernel_offset 0x8000 --ramdisk_offset 0x1000000 \
	--tags_offset 0x100 --dtb_offset 0x1f00000 --pagesize 4096 \
	--os_version "$OS_VERSION" --os_patch_level "$OS_PATCH_LEVEL" \
	--cmdline 'console=null' -o "$OUT_DIR/odessa-xnu-candidate.img"

python3 ../tools/validate-odessa-bootimg.py \
	"$OUT_DIR/odessa-xnu-candidate.img" "$OUT_DIR/Image" \
	"$OUT_DIR/odessa-xnu-payload.bin" "$BOOT_DTB"
shasum -a 256 "$OUT_DIR/odessa.adt" "$OUT_DIR/odessa-xnu-payload.bin" \
	"$OUT_DIR/Image" "$OUT_DIR/odessa-xnu-candidate.img"
echo "Candidate created for host review only; no device boot or partition write was performed."
