"""Live Mathcad X-Y plot for the cap worksheets, patched from a plot Mathcad wrote.

Mathcad stores a plot as a gzip-compressed binary object (an archive of the
plot's expression tree and formats), referenced from a `<plot item-idref>`
region. Writing that format from scratch is not safe without Mathcad, so this
module starts from a native object Mathcad itself saved: the "Summary of 30
Design Checks (Blue = OK, Red = No Good)" plot of the FDOT PSBeam run
(cap_mathcad/templates/psbeam_check_summary_plot.*). Its traces are kept as
written:

    red  trace: x = CheckNoGood^<0>, y = CheckNoGood^<1>
    blue trace: x = CheckGood^<0>,   y = CheckGood^<1>

so a worksheet that defines CheckGood and CheckNoGood (two-column matrices of
check number and value) gets a plot that recalculates in Mathcad. Each point is
drawn as a stem with a dot; a point whose check number lies outside the x range
is not drawn (PSBeam itself parks an empty trace at x = -1). Only these
fields are changed, each in place and each verified against the template
bytes before it is touched (the tree keeps its node count, so no node ids
shift):

- title and the two legend labels (length-prefixed UTF-16 strings);
- the y-axis maximum: the number 1.2 becomes the variable `ymax`
  (a number leaf turned into an identifier leaf, as used elsewhere in the tree);
- the y-axis minimum: -.2 becomes -0;
- the secondary y-axis maximum (the axis that carries the limit marker): 1.2
  becomes `ymax` too, so both scales run 0..ymax and the marker sits at 1.0;
- the x-axis maximum: 31 becomes the number of checks + 1, with one grid
  interval per check;
- the y-axis marker variable `NoGood` becomes `Limit`;
- the y-axis format: numbered with automatic grid, copied from the user's
  numbered "Shear Demand/Capacity Ratio" plot in the same run.
"""
import hashlib
import json
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / 'cap_mathcad' / 'templates' / 'psbeam_check_summary_plot.bin'
PROVENANCE = ROOT / 'cap_mathcad' / 'templates' / 'psbeam_check_summary_plot.json'
WIDTH_PT, HEIGHT_PT = 525.75, 142.5            # the template region's size in the PSBeam sheet
USES = ('CheckNoGood', 'CheckGood', 'ymax', 'Limit')   # worksheet variables the patched plot refers to


def _u16(text):
    return text.encode('utf-16-le')


def _counted(prefix, text):
    if not 0 < len(text) < 256:
        raise ValueError(f'string length {len(text)} outside 1..255: {text!r}')
    return bytes([prefix, len(text)]) + _u16(text)


def _number_leaf(node, flags, parent, text):
    """Tree leaf holding a number literal: [n+1][01][n] + UTF-16."""
    return bytes([node, 0x32, 0x02, 0x0f, 0, 0, flags, parent, 0, 0, len(text) + 1, 1, len(text)]) + _u16(text)


def _name_leaf(node, flags, parent, text):
    """Tree leaf holding an identifier: [n+1][n] + UTF-16."""
    return bytes([node, 0x32, 0x02, 0x0f, 0, 0, flags, parent, 0, 0, len(text) + 1, len(text)]) + _u16(text)


def template():
    data = TEMPLATE.read_bytes()
    record = json.loads(PROVENANCE.read_text(encoding='utf-8'))
    if hashlib.sha256(data).hexdigest() != record['template_sha256']:
        raise ValueError('cap_mathcad/templates/psbeam_check_summary_plot.bin does not match its recorded SHA-256')
    return data


def _replace_once(data, old, new, what):
    if data.count(old) != 1:
        raise ValueError(f'plot template: expected exactly one {what}, found {data.count(old)}')
    return data.replace(old, new)


def patched(n_checks, *, title, over_label, within_label):
    """Plot object bytes (uncompressed) for a worksheet with `n_checks` checks."""
    if not 1 <= n_checks <= 200:
        raise ValueError('number of checks out of range')
    data = template()
    data = _replace_once(data, _counted(0x01, 'Summary of 30 Design Checks (Blue = OK, Red = No Good)'),
                         _counted(0x01, title), 'plot title')
    data = _replace_once(data, _counted(0x03, 'Check# is No Good'), _counted(0x03, over_label), 'red legend label')
    data = _replace_once(data, _counted(0x03, 'Check# is Good'), _counted(0x03, within_label), 'blue legend label')
    # y-axis limits: node 0x0b (right child of 0x0a) is the maximum, node 0x0d under the negation 0x0c the minimum.
    data = _replace_once(data, _number_leaf(0x0b, 0x74, 0x0a, '1.2'), _name_leaf(0x0b, 0x64, 0x0a, 'ymax'), 'y maximum 1.2')
    data = _replace_once(data, _number_leaf(0x0d, 0xb4, 0x0c, '.2'), _number_leaf(0x0d, 0xb4, 0x0c, '0'), 'y minimum -.2')
    # The limit marker sits on the secondary y axis (group 0x18: limits under 0x1a, markers under 0x1d).
    # Give that axis the same 0..ymax range so the dashed line stays at D/C = 1.0 on the primary scale.
    data = _replace_once(data, _number_leaf(0x1b, 0x74, 0x1a, '1.2'), _name_leaf(0x1b, 0x64, 0x1a, 'ymax'), 'y2 maximum 1.2')
    # x-axis maximum (node 0x24 under 0x23).
    data = _replace_once(data, _number_leaf(0x24, 0x74, 0x23, '31'), _number_leaf(0x24, 0x74, 0x23, str(n_checks + 1)), 'x maximum 31')
    # y-axis marker variable.
    data = _replace_once(data, _name_leaf(0x1f, 0xa4, 0x1d, 'NoGood'), _name_leaf(0x1f, 0xa4, 0x1d, 'Limit'), 'marker NoGood')
    # Axis formats follow "axisFormat": x record then y record, each [flags] 01 00 00 00 01 00 00 00 [grids] ...
    head = b'axisFormat\x04\x00\x00\x00\x00\x00\x1c\x00\x00\x00'
    x_rec = bytes([0x0e, 1, 0, 0, 0, 1, 0, 0, 0, 0x1f, 0, 0, 0, 0, 0, 0xff, 0, 0xff, 0, 0, 1, 0x1c])
    y_rec = bytes([0x18, 1, 0, 0, 0, 1, 0, 0, 0, 0x02, 0, 0, 0, 0, 0, 0xff, 0, 0xff, 0, 0, 1, 0x1c])
    new_x = bytearray(x_rec); new_x[9] = n_checks + 1          # one grid interval per check
    new_y = bytearray(y_rec); new_y[0] = 0x5e; new_y[9] = 0x00  # numbered, automatic grid (as the user's D/C plot)
    data = _replace_once(data, head + x_rec + y_rec, head + bytes(new_x) + bytes(new_y), 'axis formats')
    return data


def compressed(data):
    """The stored form of a plot object (content-encoding="gzip"): a gzip member with the header Mathcad writes
    (no file name, time 0, XFL 0, OS 255), so the bytes do not depend on the clock or on the zlib build's OS code."""
    deflate = zlib.compressobj(6, zlib.DEFLATED, -15)
    body = deflate.compress(data) + deflate.flush()
    return b'\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\xff' + body + struct.pack('<II', zlib.crc32(data), len(data) & 0xffffffff)


def plot_block(n_checks, caption, **labels):
    """Worksheet block of the live plot (scripts/mathcad_sheet.PLOT) for `n_checks` checks."""
    from scripts.mathcad_sheet import PLOT
    return PLOT('D/C plot', compressed(patched(n_checks, **labels)), caption, WIDTH_PT, HEIGHT_PT, uses=USES)


def strings(data):
    """Readable UTF-16 strings in a plot object (for tests and review)."""
    import re
    return [m.group(1).decode('utf-16-le') for m in re.finditer(rb'((?:[\x20-\x7e]\x00){2,})', data)]


def tree_nodes(data):
    """Parse the plot's expression tree: (id, operator, flags, parent, leaf, closing zeros) per node.

    Node: [id] 0x32 [operator, 2 bytes] 00 00 [flags] [parent]; operator 0x0f02 is a
    leaf followed by 00 00 and either a number [n+1][01][n] or an identifier
    [n+1][n], then n UTF-16 characters. Zero bytes after a node close subtrees.
    Used to prove a patch keeps the node count, ids, parents and closings.
    """
    pos, end = data.index(b'tree') + 4, data.index(b'd2_graph_format')
    while not (data[pos] == 0x06 and data[pos + 1] == 0x32):
        pos += 1
    nodes = []
    while pos < end and data[pos + 1] == 0x32:
        node, op, flags, parent = data[pos], int.from_bytes(data[pos + 2:pos + 4], 'little'), data[pos + 6], data[pos + 7]
        if data[pos + 4:pos + 6] != b'\0\0':
            raise ValueError(f'unexpected node header at {pos:#x}')
        pos += 8
        leaf = None
        if op == 0x0f02:
            if data[pos:pos + 2] != b'\0\0':
                raise ValueError(f'unexpected leaf header at {pos:#x}')
            pos += 2
            if data[pos + 1] == 1 and data[pos] == data[pos + 2] + 1:
                n = data[pos + 2]; leaf = ('number', data[pos + 3:pos + 3 + 2 * n].decode('utf-16-le')); pos += 3 + 2 * n
            else:
                n = data[pos + 1]
                if data[pos] != n + 1:
                    raise ValueError(f'unexpected identifier length at {pos:#x}')
                leaf = ('name', data[pos + 2:pos + 2 + 2 * n].decode('utf-16-le')); pos += 2 + 2 * n
        zeros = 0
        while pos < end and data[pos] == 0:
            zeros += 1; pos += 1
        nodes.append((node, op, flags, parent, leaf, zeros))
    return nodes
