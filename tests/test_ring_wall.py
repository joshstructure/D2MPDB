"""Independent equilibrium, boundary and notebook execution checks."""
import base64
from contextlib import chdir
from copy import deepcopy
import hashlib
import io
import json
from math import pi
import os
from pathlib import Path
import random
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ring_wall.model import analyze, arch, default_case
from ring_wall.report import export_results, render_report
from ring_wall.study import spacing_study


class RingWallTests(unittest.TestCase):
    def test_gross_weight_and_global_equilibrium(self):
        p=default_case();r=analyze(p)
        expected=213*36*172.375/1728*.150
        self.assertAlmostEqual(r['totals']['service_weight'],expected)
        self.assertAlmostEqual(r['totals']['factored_weight'],1.25*expected)
        self.assertAlmostEqual(sum(x['R'] for x in r['rings']),1.25*expected)
        self.assertAlmostEqual(sum(x['R']*x['x']+x['M'] for x in r['rings']),1.25*expected*213/2)
        # Each row must also equilibrate independently; opposite end moments
        # must not hide incorrect individual overhang signs.
        for row in r['rows']:
            rings=[x for x in r['rings'] if x['row']==row['row']]
            self.assertAlmostEqual(sum(x['R'] for x in rings),row['weight'])
            self.assertAlmostEqual(rings[0]['M'],-row['w']*r['end']**2/2)
            self.assertAlmostEqual(rings[-1]['M'],row['w']*r['end']**2/2)
            self.assertGreater(row['lo']+row['height'],row['lo'])
        self.assertEqual(r['rows'][0]['lo'],0)
        self.assertEqual(r['rows'][-1]['hi'],p['height_in'])

    def test_funicular_forces_independently_from_beam_moment(self):
        # At each interior joint, T*y equals the simply supported bending moment
        # of the lumped loads. This catches an incorrect rise/thrust conversion.
        for panels in (2,4,6,10):
            w,L,h=.22,72.,13.
            a=arch(w,L,h,panels)
            self.assertLess(a['residual'],1e-12)
            for j,x in enumerate(a['x'][1:-1],1):
                M=a['reaction']*x-sum(P*(x-xp) for P,xp in zip(a['joint_loads'],a['x']) if xp<x)
                self.assertAlmostEqual(a['tie']*a['y'][j],M,places=10)
            self.assertAlmostEqual(sum(a['joint_loads']),w*L)

    def test_random_layout_equilibrium(self):
        rng=random.Random(8729)
        for _ in range(30):
            p=default_case()
            p.update(pile_count=rng.randint(2,6),pile_spacing_in=rng.uniform(42,80),
                     ring_count=rng.randint(1,5),arch_panels=rng.choice([2,4,6,8]))
            p['length_in']=(p['pile_count']-1)*p['pile_spacing_in']+rng.uniform(28,50)
            p['ring_spacing_in']=rng.uniform(24,40)
            p['height_in']=p['first_ring_in']+(p['ring_count']-1)*p['ring_spacing_in']+rng.uniform(25,50)
            r=analyze(p)
            self.assertLess(abs(r['totals']['force_error']),1e-9)
            self.assertLess(abs(r['totals']['moment_error']),1e-8)
            self.assertLess(r['totals']['joint_error'],1e-10)

    def test_minimum_grid_and_matching_u(self):
        r=analyze();g=r['grid']
        self.assertAlmostEqual(g['stm'],.648)
        self.assertAlmostEqual(g['st'],1.3*36*213/(2*(36+213)*60))
        self.assertEqual(g['bar'],5);self.assertEqual(g['spacing'],5.)
        self.assertAlmostEqual(g['provided'],.744)
        self.assertLessEqual(g['spacing'],g['spacing_limit'])
        self.assertAlmostEqual(g['development_h']['ld'],54.63374794909805)
        self.assertAlmostEqual(g['development_h']['lap_b'],71.02387233382747)
        p=default_case();p.update(grid_bar=6,auto_grid_spacing=False,grid_spacing_in=8.)
        q=analyze(p);check={x['id']:x for x in q['checks']}
        self.assertEqual(check['GRID-A']['status'],'PASS')
        self.assertEqual(check['GRID-S']['status'],'FAIL')

    def test_input_changes_recompute_demands(self):
        a=analyze();p=default_case();p['density_kcf']*=2;b=analyze(p)
        for ra,rb in zip(a['rings'],b['rings']):
            self.assertAlmostEqual(rb['R'],2*ra['R'])
            self.assertAlmostEqual(rb['qmax'],2*ra['qmax'])
            self.assertAlmostEqual(rb['t_req'],2**.5*ra['t_req'])
        p=default_case();p['bearing_fraction']=1.;c=analyze(p)
        self.assertAlmostEqual(c['rings'][0]['qmax'],a['rings'][0]['qmax']/2)
        self.assertEqual(c['totals'],a['totals'])

    def test_plate_root_moment_against_numerical_integration(self):
        r=analyze();p=r['case'];ring=r['rings'][0]
        ri,ro,rp=p['ring_id_in']/2,p['ring_od_in']/2,p['pile_od_in']/2
        count=10000;dr=(ro-ri)/count
        m=sum(ring['qmax']*(ri+(i+.5)*dr-rp)*(ri+(i+.5)*dr)/rp*dr for i in range(count))
        self.assertAlmostEqual(ring['m_per_in'],m,places=8)

    def test_conflicts_are_failures_and_no_overall_pass(self):
        r=analyze();checks={x['id']:x for x in r['checks']}
        self.assertEqual(checks['RING-END']['status'],'FAIL')
        self.assertEqual(checks['RING-GRID']['status'],'FAIL')
        self.assertEqual(r['geometry']['edge_clear'],2.)
        self.assertEqual(r['geometry']['grid_gap'],-.75)
        self.assertNotIn('PASS',r['overall'])
        # Even after trial fit changes, pending engineering cannot become PASS.
        p=default_case();p.update(thickness_in=44.,length_in=240.)
        r=analyze(p);self.assertTrue(r['pending']);self.assertNotIn('PASS',r['overall'])

    def test_invalid_inputs_fail_explicitly(self):
        changes=[dict(ring_id_in=19.),dict(ring_spacing_in=0.),dict(arch_panels=3),
                 dict(ring_count=100),dict(first_ring_in=0),dict(node_width_in=36),
                 dict(height_in=float('nan')),dict(pile_count=1),dict(coating='guess'),
                 dict(phi_tie=1.1),dict(fy_ksi=100),dict(thickness_in=12)]
        for change in changes:
            with self.subTest(change=change):
                p=default_case();p.update(change)
                with self.assertRaises(ValueError):analyze(p)

    def test_spacing_study_and_exports(self):
        r=analyze();study=spacing_study(r['case'])
        self.assertEqual(len(study),5)
        self.assertEqual(study[2]['ring_count'],5)
        self.assertEqual(study[2]['grid_spacing_in'],5.)
        with tempfile.TemporaryDirectory(dir=ROOT,prefix='.ring-wall-test-') as temp:
            paths=export_results(r,temp)
            self.assertEqual(len(paths),5)
            saved=json.loads((Path(temp)/'ring_wall_results.json').read_text())
            self.assertEqual(saved['totals'],r['totals'])
            report=(Path(temp)/'ring_wall_report.html').read_text(encoding='utf-8')
            self.assertIn('Equation &amp; values',report)
            self.assertIn('svg',report)
            self.assertIn('RING-GRID',report)
            self.assertNotIn('https://cdn',report)

    def test_portable_notebook_all_code_cells_execute(self):
        notebook=json.loads((ROOT/'Ring_Supported_Wall_STM.ipynb').read_text(encoding='utf-8'))
        namespace={}
        oldcwd=Path.cwd();oldpath=sys.path[:]
        try:
            with tempfile.TemporaryDirectory(dir=ROOT,prefix='.ring-wall-test-') as temp, chdir(temp):
                for index,c in enumerate(notebook['cells']):
                    if c['cell_type']=='code':
                        exec(compile(''.join(c['source']),f'notebook-cell-{index}','exec'),namespace)
                self.assertEqual(namespace['result']['grid']['spacing'],5.)
                self.assertTrue(namespace['bundle'].exists())
                with zipfile.ZipFile(namespace['bundle']) as z:
                    self.assertEqual(len(z.namelist()),7)
                embedded=base64.b64decode(namespace['PACKAGE'])
                self.assertEqual(hashlib.sha256(embedded).hexdigest(),namespace['PACKAGE_SHA256'])
                with zipfile.ZipFile(io.BytesIO(embedded)) as z:
                    for name in z.namelist():
                        self.assertEqual(z.read(name),(ROOT/name).read_bytes())
                # Stale results cannot be exported after an input change.
                namespace['case']['ring_t_in']=1.
                with self.assertRaises(RuntimeError):
                    exec(''.join(notebook['cells'][-2]['source']),namespace)
        finally:
            os.chdir(oldcwd);sys.path[:]=oldpath


if __name__=='__main__':unittest.main()
