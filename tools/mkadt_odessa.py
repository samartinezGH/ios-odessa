#!/usr/bin/env python3
"""Build a conservative first-boot Apple Device Tree for Moto G9 Plus.

The input must be the active flattened device tree captured from the target,
not the unpopulated stock DTB embedded in boot.img. Only a single RAM bank
that is disjoint from fixed reservations and dynamic allocation ranges above
4 GiB is exposed to XNU. The result is a kernel bring-up ADT, not a claim that
the Odessa XNU kernel can boot or mount iOS.
"""
import argparse
import os
import secrets
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adt  # noqa: E402

FDT_MAGIC = 0xD00DFEED
FDT_BEGIN_NODE, FDT_END_NODE, FDT_PROP, FDT_NOP, FDT_END = 1, 2, 3, 4, 9
PAGE_SIZE = 0x4000
MIN_XNU_RAM = 0x10000000
HIGHMEM_CUTOFF = 0x100000000
SOC_BASE = 0x01000000


class FdtNode:
    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent
        self.props = {}
        self.children = []

    @property
    def path(self):
        return (self.parent.path.rstrip('/') + '/' + self.name) if self.parent else '/'


def parse_fdt(blob):
    if len(blob) < 40:
        raise ValueError('truncated FDT header')
    (magic, total, struct_off, strings_off, reserve_off, version, _last,
     _boot, strings_size, struct_size) = struct.unpack_from('>10I', blob)
    if magic != FDT_MAGIC or total > len(blob) or version < 16:
        raise ValueError('invalid or unsupported flattened device tree')
    if struct_off + struct_size > total or strings_off + strings_size > total:
        raise ValueError('FDT structure or string block exceeds total size')
    strings = blob[strings_off:strings_off + strings_size]
    data = blob[struct_off:struct_off + struct_size]
    root = None
    current = None
    pos = 0
    ended = False
    while pos + 4 <= len(data):
        token = struct.unpack_from('>I', data, pos)[0]
        pos += 4
        if token == FDT_BEGIN_NODE:
            end = data.find(b'\0', pos)
            if end < 0:
                raise ValueError('unterminated FDT node name')
            name = data[pos:end].decode('ascii', 'strict')
            pos = (end + 4) & ~3
            node = FdtNode(name, current)
            if current:
                current.children.append(node)
            elif root is None:
                root = node
            else:
                raise ValueError('multiple FDT roots')
            current = node
        elif token == FDT_END_NODE:
            if current is None:
                raise ValueError('unbalanced FDT_END_NODE')
            current = current.parent
        elif token == FDT_PROP:
            if current is None or pos + 8 > len(data):
                raise ValueError('invalid FDT property')
            length, nameoff = struct.unpack_from('>II', data, pos)
            pos += 8
            if pos + length > len(data) or nameoff >= len(strings):
                raise ValueError('FDT property exceeds its block')
            end = strings.find(b'\0', nameoff)
            if end < 0:
                raise ValueError('unterminated FDT property name')
            name = strings[nameoff:end].decode('ascii', 'strict')
            current.props[name] = data[pos:pos + length]
            pos = (pos + length + 3) & ~3
        elif token == FDT_NOP:
            continue
        elif token == FDT_END:
            ended = True
            break
        else:
            raise ValueError(f'unknown FDT token {token}')
    if root is None or not ended:
        raise ValueError('incomplete FDT structure')
    return root, blob[:total], reserve_off, total


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


def cell_count(node, key, default):
    raw = node.props.get(key)
    if raw is None:
        return default
    if len(raw) != 4:
        raise ValueError(f'{node.path}: malformed {key}')
    count, = struct.unpack('>I', raw)
    if count > 4:
        raise ValueError(f'{node.path}: unsupported {key}={count}')
    return count


def decode_cells(raw):
    if len(raw) % 4:
        raise ValueError('cell property has a partial cell')
    return struct.unpack('>' + 'I' * (len(raw) // 4), raw)


def decode_tuples(raw, address_cells, size_cells, path, key):
    stride = address_cells + size_cells
    cells = decode_cells(raw)
    if not stride or len(cells) % stride:
        raise ValueError(f'{path}: malformed {key} property')
    out = []
    for start in range(0, len(cells), stride):
        addr = size = 0
        for cell in cells[start:start + address_cells]:
            addr = (addr << 32) | cell
        for cell in cells[start + address_cells:start + stride]:
            size = (size << 32) | cell
        if size <= 0 or addr + size > 1 << (32 * max(address_cells, 1)):
            raise ValueError(f'{path}: invalid {key} range')
        out.append((addr, size))
    return out


def fdt_memory_and_reservations(root, blob, reserve_off, total):
    nodes = list(walk(root))
    memory = []
    for node in nodes:
        if node.parent is root and (node.name == 'memory' or node.name.startswith('memory@')):
            if node.props.get('device_type', b'').split(b'\0')[0] != b'memory':
                continue
            na = cell_count(root, '#address-cells', 2)
            ns = cell_count(root, '#size-cells', 1)
            memory.extend(decode_tuples(node.props.get('reg', b''), na, ns, node.path, 'reg'))
    if not memory:
        raise ValueError('active FDT has no populated /memory/reg ranges')

    reserved_node = next((n for n in nodes if n.path == '/reserved-memory'), None)
    fixed = []
    dynamic = []
    if reserved_node:
        na = cell_count(reserved_node, '#address-cells', cell_count(root, '#address-cells', 2))
        ns = cell_count(reserved_node, '#size-cells', cell_count(root, '#size-cells', 1))
        for node in reserved_node.children:
            if 'reg' in node.props:
                fixed.extend(decode_tuples(node.props['reg'], na, ns, node.path, 'reg'))
            elif 'size' in node.props:
                size_cells = decode_cells(node.props['size'])
                if len(size_cells) != ns:
                    raise ValueError(f'{node.path}: malformed dynamic reservation size')
                size = 0
                for cell in size_cells:
                    size = (size << 32) | cell
                if size <= 0:
                    raise ValueError(f'{node.path}: empty dynamic reservation')
                if 'alloc-ranges' not in node.props:
                    raise ValueError(f'{node.path}: dynamic reservation has no alloc-ranges')
                alloc = decode_tuples(node.props['alloc-ranges'], na, ns, node.path, 'alloc-ranges')
                dynamic.extend((a, s, node.path) for a, s in alloc)

    memreserve = []
    pos = reserve_off
    while pos + 16 <= total:
        addr, size = struct.unpack_from('>QQ', blob, pos)
        pos += 16
        if addr == 0 and size == 0:
            break
        memreserve.append((addr, size))
    return memory, fixed, dynamic, memreserve


def overlaps(a, b):
    return a[0] < b[0] + b[1] and b[0] < a[0] + a[1]


def select_kernel_ram(memory, fixed, dynamic, memreserve):
    candidates = []
    for bank in memory:
        if bank[0] < HIGHMEM_CUTOFF:
            continue
        if any(overlaps(bank, r) for r in fixed + memreserve):
            continue
        # Dynamic pools are not allocated in XNU's handoff. If their legal
        # range can intersect this bank, ownership cannot be proven here.
        if any(overlaps(bank, (a, size)) for a, size, _path in dynamic):
            continue
        if bank[1] >= MIN_XNU_RAM and bank[0] % PAGE_SIZE == 0 and bank[1] % PAGE_SIZE == 0:
            candidates.append(bank)
    if len(candidates) != 1:
        raise ValueError(f'expected exactly one unreserved high-memory bank; found {len(candidates)}')
    return candidates[0]


def get_node(root, path):
    cur = root
    for component in path.strip('/').split('/'):
        cur = next((c for c in cur.children if c.name == component), None)
        if cur is None:
            return None
    return cur


def string_list(raw):
    return [x.decode('ascii', 'strict') for x in raw.rstrip(b'\0').split(b'\0') if x]


def inspect_target(root):
    compatible = string_list(root.props.get('compatible', b''))
    if 'qcom,sdmmagpie' not in compatible:
        raise ValueError('input FDT is not the Moto G9 Plus qcom,sdmmagpie tree')
    cpus = get_node(root, '/cpus')
    if cpus is None:
        raise ValueError('active FDT has no /cpus node')
    ca = cell_count(cpus, '#address-cells', 1)
    cs = cell_count(cpus, '#size-cells', 0)
    cpu_nodes = []
    for node in cpus.children:
        if node.props.get('device_type', b'').split(b'\0')[0] != b'cpu':
            continue
        if node.props.get('enable-method', b'').split(b'\0')[0] != b'psci':
            raise ValueError(f'{node.path}: CPU enable-method is not PSCI')
        cells = decode_cells(node.props.get('reg', b''))
        if len(cells) != ca:
            raise ValueError(f'{node.path}: unsupported CPU reg width')
        mpidr = 0
        for cell in cells:
            mpidr = (mpidr << 32) | cell
        cpu_nodes.append((node.name, mpidr & 0xffffffff))
    if len(cpu_nodes) < 1 or cpu_nodes[0][1] != 0:
        raise ValueError('expected boot CPU affinity 0 as the first CPU node')

    gic = next((n for n in walk(root) if 'arm,gic-v3' in string_list(n.props.get('compatible', b''))), None)
    if gic is None:
        raise ValueError('active FDT has no GICv3 node')
    gp = gic.parent
    ga, gs = cell_count(gp, '#address-cells', 2), cell_count(gp, '#size-cells', 1)
    gic_regs = decode_tuples(gic.props.get('reg', b''), ga, gs, gic.path, 'reg')
    if len(gic_regs) < 2:
        raise ValueError('GICv3 DT node lacks distributor or redistributor ranges')

    timer = next((n for n in walk(root) if 'arm,armv8-timer' in string_list(n.props.get('compatible', b''))), None)
    if timer is None:
        raise ValueError('active FDT has no ARMv8 generic timer')
    ints = decode_cells(timer.props.get('interrupts', b''))
    if len(ints) < 12 or len(ints) % 3:
        raise ValueError('generic timer has an unexpected interrupt specifier')
    # ARMv8 timer binding: secure physical, non-secure physical, virtual,
    # hypervisor PPIs, each encoded as type, number, trigger flags.
    virtual_intid = 16 + ints[7]
    freq_raw = timer.props.get('clock-frequency')
    if not freq_raw or len(freq_raw) != 4:
        raise ValueError('generic timer frequency is missing from active FDT')
    timebase = struct.unpack('>I', freq_raw)[0]
    return cpu_nodes, gic_regs, virtual_intid, timebase


def u32(value):
    return struct.pack('<I', value)


def u64(value):
    return struct.pack('<Q', value)


def cstr(value):
    return value.encode('ascii') + b'\0'


def node(name, props=(), children=()):
    out = adt.Node()
    out.props = [('name', 0, cstr(name))] + [(k, 0, v) for k, v in props]
    out.children = list(children)
    return out


def build_adt(memory_range, cpu_nodes, gic_regs, virtual_intid, timebase, seed=None):
    if memory_range[0] < HIGHMEM_CUTOFF:
        raise ValueError('refusing to expose low memory as a single XNU range')
    seed = seed if seed is not None else secrets.token_bytes(64)
    phandles = iter(range(1, 100))
    ph = lambda: ('AAPL,phandle', u32(next(phandles)))
    chosen = node('chosen', [
        ph(), ('dram-base', u64(memory_range[0])), ('dram-size', u64(memory_range[1])),
        ('random-seed', seed),
        ('firmware-version', cstr('odessa-xnu-experimental')),
        ('system-firmware-version', cstr('odessa-xnu-experimental')),
    ], [node('memory-map', [ph()])])
    cpus = node('cpus', [ph(), ('#address-cells', u32(1)), ('#size-cells', u32(0))], [
        node(f'cpu{i}', [ph(), ('device_type', cstr('cpu')),
                         ('compatible', cstr('arm,armv8')),
                         ('reg', u32(mpidr)), ('cpu-id', u32(i)),
                         ('timebase-frequency', u32(timebase)),
                         ('state', cstr('running' if i == 0 else 'stopped')),
                         ('enable-method', cstr('psci'))])
        for i, (_name, mpidr) in enumerate(cpu_nodes)
    ])
    gic = node('gic', [ph(), ('compatible', cstr('arm,gic-v3')),
                       ('interrupt-controller', b''),
                       ('virtual-timer-intid', u32(virtual_intid)),
                       ('reg', struct.pack('<4Q',
                           gic_regs[0][0] - SOC_BASE, gic_regs[0][1],
                           gic_regs[1][0] - SOC_BASE, gic_regs[1][1]))])
    arm_io = node('arm-io', [ph(), ('device_type', cstr('odessa-io')),
                             ('compatible', cstr('odessa-io') + cstr('arm-io')),
                             ('#address-cells', u32(2)), ('#size-cells', u32(2)),
                             ('ranges', struct.pack('<3Q', 0, SOC_BASE, 0x100000000-SOC_BASE))],
                  [gic])
    return node('device-tree', [
        ph(), ('compatible', cstr('D22AP') + cstr('iPhone10,3') +
               cstr('motorola,odessa') + cstr('qcom,sdmmagpie') + cstr('AppleARM')),
        ('model', cstr('iPhone10,3')), ('target-type', cstr('D22')),
        ('target-sub-type', cstr('D22AP')), ('manufacturer', cstr('Apple Inc.')),
        ('#address-cells', u32(2)), ('#size-cells', u32(2)),
    ], [chosen, cpus, arm_io])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('live_fdt', help='read-only active /sys/firmware/fdt capture from Odessa')
    parser.add_argument('output', help='output Apple Device Tree path')
    args = parser.parse_args()
    try:
        root, blob, reserve_off, total = parse_fdt(open(args.live_fdt, 'rb').read())
        memory, fixed, dynamic, memreserve = fdt_memory_and_reservations(root, blob, reserve_off, total)
        ram = select_kernel_ram(memory, fixed, dynamic, memreserve)
        cpus, gic, timer_irq, timebase = inspect_target(root)
        result = adt.serialize(build_adt(ram, cpus, gic, timer_irq, timebase))
        # Verify the serialized ADT and key safety invariants before writing it.
        parsed, end = adt.parse(result)
        assert end == len(result)
        chosen = next(c for c in parsed.children if c.name == 'chosen')
        assert struct.unpack('<Q', chosen.prop('dram-base'))[0] == ram[0]
        assert struct.unpack('<Q', chosen.prop('dram-size'))[0] == ram[1]
        open(args.output, 'wb').write(result)
        print(f'ADT: {args.output} ({len(result)} bytes)')
        print(f'XNU RAM candidate: base={ram[0]:#x} size={ram[1]:#x} end={ram[0]+ram[1]:#x}')
        print(f'CPU nodes: {len(cpus)}; boot CPU affinity: {cpus[0][1]:#x}; secondary CPUs are described as stopped')
        print(f'GICv3: dist={gic[0][0]:#x} redist={gic[1][0]:#x}; virtual timer PPI={timer_irq}; timebase={timebase} Hz')
        print('This is a host-generated bring-up ADT, not a bootable or device-tested image.')
    except (OSError, ValueError, AssertionError, StopIteration, struct.error) as exc:
        print(f'error: refusing to generate Odessa ADT: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
