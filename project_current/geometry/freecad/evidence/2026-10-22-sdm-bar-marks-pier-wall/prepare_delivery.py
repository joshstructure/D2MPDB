"""D-083 delivery: apply only the mark values to the prior archive's Document.xml.

As the D-042 and D-060 jobs: the native step (native_update.py) proved the
change in FreeCAD and saved NativeSaved.FCStd.  A console save rewrites
unrelated presentation records, so the delivery edits, in the registered
archive text:

* the String value of ``Mark`` for each changed bar;
* the content of the column-A schedule cells of those bars;
* the "mark" values inside the cap-cage ScheduleJSON strings (none change
  here: no cap bar is re-marked);
* the String value of ``MarkStatus`` on PierWallSteelInputs.

Each edit is checked against the native save; every other object, view
record and archive member stays byte-identical.
"""
from pathlib import Path
import hashlib, html, json, re, zipfile, xml.etree.ElementTree as E

OUT = Path(__file__).resolve().parent
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
native_log = json.loads((OUT/'native-update.json').read_text())
assert native_log['status'] == 'PASS'
assert sha(OUT/'Before.FCStd') == native_log['before_sha256']
assert sha(OUT/'NativeSaved.FCStd') == native_log['native_saved_sha256']
assert not (OUT/'Delivery.FCStd').exists()
changes = json.loads((OUT/'mark-changes.json').read_text())
old_new = {c['object']: (c['old'], c['new']) for c in changes}
assert len(old_new) == len(changes) > 0
status = native_log['mark_status']
assert status and status['object'] == 'PierWallSteelInputs'
CAGES = ('CageEB1Quantities', 'CagePierQuantities', 'CageEB2Quantities')


def object_span(text, name):
    """(start, end) of the ObjectData record of ``name``."""
    data = text.index('<ObjectData')
    m = list(re.finditer(r'<Object name="%s"[ >]' % re.escape(name), text[data:]))
    assert len(m) == 1, (name, len(m))
    start = data + m[0].start()
    end = text.index('</Object>', start) + len('</Object>')
    return start, end


def property_span(text, start, end, prop):
    m = list(re.finditer(r'<Property name="%s"' % re.escape(prop), text[start:end]))
    assert len(m) == 1, (prop, len(m))
    s = start + m[0].start()
    return s, text.index('</Property>', s) + len('</Property>')


def replace_once(text, start, end, old, new):
    seg = text[start:end]
    assert seg.count(old) == 1, (old, seg.count(old))
    return text[:start] + seg.replace(old, new, 1) + text[end:]


def esc(s):
    return html.escape(s, quote=True).replace('&#x27;', '&apos;')


with zipfile.ZipFile(OUT/'Before.FCStd') as z:
    doc = z.read('Document.xml').decode('utf-8')
with zipfile.ZipFile(OUT/'NativeSaved.FCStd') as z:
    ndoc_root = E.fromstring(z.read('Document.xml'))
native = {o.get('name'): o for o in ndoc_root.find('ObjectData')}

# 1. Mark values
for name, (old, new) in old_new.items():
    s, e = object_span(doc, name)
    ps, pe = property_span(doc, s, e, 'Mark')
    doc = replace_once(doc, ps, pe, 'value="%s"' % esc(old), 'value="%s"' % esc(new))
    assert native[name].find("./Properties/Property[@name='Mark']/String").get('value') == new

# 2. Schedule cells (column A of each changed bar row), checked against the native save
cell_edits = 0
sheets = {}
for o in native.values():
    if o.get('name').endswith('Schedule'):
        cells = o.find("./Properties/Property[@name='cells']/Cells")
        if cells is not None:
            sheets[o.get('name')] = {c.get('address'): c.get('content') for c in cells}
with zipfile.ZipFile(OUT/'Before.FCStd') as z:
    broot = E.fromstring(z.read('Document.xml'))
before_sheets = {}
for o in broot.find('ObjectData'):
    if o.get('name').endswith('Schedule'):
        cells = o.find("./Properties/Property[@name='cells']/Cells")
        if cells is not None:
            before_sheets[o.get('name')] = {c.get('address'): c.get('content') for c in cells}
changed_sheets = []
for sheet, ncells in sheets.items():
    bcells = before_sheets[sheet]
    assert set(bcells) == set(ncells), sheet
    for addr, ncontent in ncells.items():
        if bcells[addr] == ncontent:
            continue
        assert addr.startswith('A'), (sheet, addr)
        old = bcells[addr].lstrip("'")
        new = ncontent.lstrip("'")
        assert any(o == old and n == new for o, n in old_new.values()), (sheet, addr, old, new)
        s, e = object_span(doc, sheet)
        ps, pe = property_span(doc, s, e, 'cells')
        doc = replace_once(doc, ps, pe, '<Cell address="%s" content="%s"' % (addr, esc(bcells[addr]).replace('&apos;', "'")),
                           '<Cell address="%s" content="%s"' % (addr, "'" + esc(new)))
        cell_edits += 1
        if sheet not in changed_sheets:
            changed_sheets.append(sheet)
assert cell_edits == len(old_new), (cell_edits, len(old_new))

# 3. Marks inside the cap-cage quantity ScheduleJSON strings (unchanged unless a cap bar is re-marked)
json_edits = 0
for q in CAGES:
    s, e = object_span(doc, q)
    ps, pe = property_span(doc, s, e, 'ScheduleJSON')
    nrows = json.loads(native[q].find("./Properties/Property[@name='ScheduleJSON']/String").get('value'))
    for row in nrows:
        if row['object'] not in old_new:
            continue
        old, new = old_new[row['object']]
        assert row['mark'] == new
        doc = replace_once(doc, ps, pe, '&quot;mark&quot;: &quot;%s&quot;' % old, '&quot;mark&quot;: &quot;%s&quot;' % new)
        ps, pe = property_span(doc, *object_span(doc, q), 'ScheduleJSON')
        json_edits += 1

# 4. MarkStatus on the pier wall inputs
s, e = object_span(doc, status['object'])
ps, pe = property_span(doc, s, e, 'MarkStatus')
doc = replace_once(doc, ps, pe, 'value="%s"' % esc(status['old']), 'value="%s"' % esc(status['new']))
assert native[status['object']].find("./Properties/Property[@name='MarkStatus']/String").get('value') == status['new']

with zipfile.ZipFile(OUT/'Before.FCStd') as old, zipfile.ZipFile(OUT/'Delivery.FCStd', 'w') as out:
    for info in old.infolist():
        out.writestr(info, doc.encode('utf-8') if info.filename == 'Document.xml' else old.read(info.filename))


def canon(el):
    return (el.tag, sorted(el.attrib.items()), (el.text or '').strip(), [canon(x) for x in el])


with zipfile.ZipFile(OUT/'Before.FCStd') as old, zipfile.ZipFile(OUT/'Delivery.FCStd') as new:
    assert old.namelist() == new.namelist()
    others = [n for n in old.namelist() if n != 'Document.xml']
    assert all(old.read(n) == new.read(n) for n in others)
    od, nd = [E.fromstring(z.read('Document.xml')) for z in (old, new)]
targets = {'Mark': set(old_new), 'cells': set(changed_sheets), 'ScheduleJSON': set(CAGES) if json_edits else set(),
           'MarkStatus': {status['object']}}
changed_props = {}
for o in od.find('ObjectData'):
    name = o.get('name')
    n = nd.find('./ObjectData/Object[@name="%s"]' % name)
    po = {p.get('name'): p for p in o.find('Properties')}
    pn = {p.get('name'): p for p in n.find('Properties')}
    assert set(po) == set(pn), name
    for k in po:
        if canon(po[k]) != canon(pn[k]):
            assert name in targets.get(k, ()), (name, k)
            changed_props.setdefault(k, []).append(name)
    assert canon(E.Element('x', o.attrib)) == canon(E.Element('x', n.attrib)), name
for tag in ('Objects', 'StringHasher', 'StringHasher2', 'Properties'):
    if od.find(tag) is not None:
        assert canon(od.find(tag)) == canon(nd.find(tag)), tag
# Every changed value equals the native save.
for k, names in changed_props.items():
    for name in names:
        a = nd.find('./ObjectData/Object[@name="%s"]/Properties/Property[@name="%s"]' % (name, k))
        b = native[name].find("./Properties/Property[@name='%s']" % k)
        if k in ('Mark', 'MarkStatus'):
            assert a.find('String').get('value') == b.find('String').get('value')
        elif k == 'cells':
            ca = {c.get('address'): c.get('content') for c in a.find('Cells')}
            cb = {c.get('address'): c.get('content') for c in b.find('Cells')}
            assert ca == cb, name
        else:
            ra = json.loads(a.find('String').get('value'))
            rb = json.loads(b.find('String').get('value'))
            assert [r['mark'] for r in ra] == [r['mark'] for r in rb], name
assert set(changed_props.get('Mark', [])) == set(old_new)
assert changed_props.get('MarkStatus') == [status['object']]
report = dict(status='PASS', before_sha256=sha(OUT/'Before.FCStd'), model_sha256=sha(OUT/'Delivery.FCStd'),
              native_saved_sha256=sha(OUT/'NativeSaved.FCStd'), objects=len(od.find('ObjectData')),
              changed_properties={k: len(v) for k, v in changed_props.items()},
              mark_values_changed=len(old_new), schedule_cells_changed=cell_edits, schedule_sheets_changed=changed_sheets,
              schedule_json_marks_changed=json_edits, mark_status=status,
              unchanged_archive_members=len(others), gui_document_unchanged=True,
              method='Native FreeCAD change on a disposable copy; delivery edits only the mark values, the schedule cell '
                     'text and the pier wall MarkStatus string in the registered archive (as the D-042 and D-060 jobs). '
                     'All other object, view and resource bytes kept.',
              not_transplanted='Console-save Visibility/_GroupTouched records, attribute escaping and last-digit volume '
                               'recalculations in NativeSaved are presentation or numerical-noise artifacts and were not adopted.')
(OUT/'preservation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
