"""Every report equation dropdown highlights at least one element of its mechanics sketch."""
import unittest
from lxml import etree
from ring_wall.model import analyze, default_case
from ring_wall.calculation_report import families, sketch_kind, check_type
from ring_wall.schematics import schematic


def dropdowns(r):
    """(group, node name, kind, example, check type) for every equation the report renders."""
    nodes = {n['name'] for n in r['nodes']}
    for g in families(r):
        for name in g['names']:
            if name in nodes:
                yield g['key'], name, sketch_kind(name, g['key']), g['example'], ''
        for typ in g['types']:
            matches = [c for c in g['checks'] if check_type(c) == typ]
            if not matches: continue
            ex = g['example']
            c = next((c for c in matches if c['id'].startswith(f"R{ex['row']}-P{ex['pile']}-")), matches[0])
            yield g['key'], c['demand_node'], sketch_kind(c['demand_node'], g['key']), ex, typ


class RingWallSchematicTests(unittest.TestCase):
    def test_every_equation_dropdown_highlights_its_sketch(self):
        for p in (default_case(), default_case() | dict(pile_count=1, ring_count=1),
                  default_case() | dict(length_in=240., thickness_in=44., placement_tolerance_in=0.)):
            r = analyze(p); seen = 0
            for group, name, kind, example, typ in dropdowns(r):
                with self.subTest(group=group, name=name, check=typ):
                    svg = schematic(kind, name, r, example)
                    self.assertIn('font-weight="700"', svg)
                    self.assertIn('viewBox="0 0 720 250"', svg)
                    self.assertNotIn('<script', svg); self.assertNotIn('href=', svg)
                    root = etree.fromstring(svg.encode())  # well-formed XML, offline inline SVG
                    self.assertEqual(len(root.xpath('.//*[local-name()="svg"]')), 1)
                seen += 1
            self.assertGreaterEqual(seen, 80 if p['pile_count'] > 1 else 70)
        self.assertEqual(sum(1 for _ in dropdowns(analyze())), 96)

    def test_unknown_kind_and_inactive_sketch(self):
        r = analyze(); ex = r['rings'][0]
        with self.assertRaises(ValueError): schematic('nothing', 'outer_radius', r, ex)
        self.assertNotIn('font-weight="700"', schematic('annulus', 'density_kcf', r, ex))
        with_limit = schematic('pressure', 'bearing_limit', r, ex); without = schematic('pressure', 'ring_1_1_qavg', r, ex)
        self.assertIn('q_R', with_limit); self.assertNotIn('>q_R', without)


if __name__ == '__main__': unittest.main()
