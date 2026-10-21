"""Independent mechanics, boundary, portability and export checks."""
import base64
from contextlib import chdir
from copy import deepcopy
import hashlib
import io
import json
from math import pi,sqrt
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from ring_wall.model import analyze,default_case,upgrade_case
from ring_wall.output import export_results,render_report
from ring_wall.study import spacing_study

ROOT=Path(__file__).resolve().parents[1]


class RingWallTests(unittest.TestCase):
    def test_default_weight_grid_and_no_stm(self):
        r=analyze();p=r['case']
        self.assertAlmostEqual(r['totals']['service_weight'],213*36*172.375*.150/1728)
        self.assertEqual(r['grid']['spacing'],11.)
        self.assertAlmostEqual(r['grid']['required'],1.3*36*213/(2*(36+213)*60))
        self.assertNotIn('arch',r['rows'][0]);self.assertNotIn('stm',r['grid'])
        self.assertFalse(any('strut' in c['title'].lower() or 'tie' in c['title'].lower() for c in r['checks']))
        self.assertEqual(p['schema_version'],3)

    def test_midplanes_edges_and_each_cell_centroid_equilibrium(self):
        r=analyze();p=r['case']
        self.assertEqual(r['geometry']['x_bounds'],[0,46.5,106.5,166.5,213.])
        self.assertEqual(r['geometry']['z_bounds'],[0,24,60,96,132,172.375])
        for a in r['rings']:
            W=(a['xhi']-a['xlo'])*(a['hi']-a['lo'])*p['thickness_in']*.150*1.25/1728
            self.assertAlmostEqual(a['R'],W)
            self.assertAlmostEqual(a['R']*a['x']+a['M_nominal'],W*(a['xlo']+a['xhi'])/2)
        self.assertAlmostEqual(r['totals']['force_error'],0)
        self.assertAlmostEqual(r['totals']['moment_error'],0)

    def test_random_tributary_conservation_including_single_pile_row(self):
        rng=random.Random(482)
        for _ in range(30):
            p=default_case();p.update(pile_count=rng.randint(1,6),ring_count=rng.randint(1,6),pile_spacing_in=rng.uniform(45,80),ring_spacing_in=rng.uniform(24,40))
            p['length_in']=(p['pile_count']-1)*p['pile_spacing_in']+rng.uniform(40,90)
            p['height_in']=p['first_ring_in']+(p['ring_count']-1)*p['ring_spacing_in']+rng.uniform(30,60)
            r=analyze(p)
            self.assertLess(abs(r['totals']['force_error']),1e-9);self.assertLess(abs(r['totals']['moment_error']),1e-8)
            self.assertAlmostEqual(sum(a['volume_ft3'] for a in r['rings']),p['length_in']*p['height_in']*p['thickness_in']/1728)

    def test_grid_independent_of_ring_pitch_and_number(self):
        baseline=analyze()['grid']
        for count,pitch in [(1,36.),(4,40.),(6,28.)]:
            p=default_case();p.update(ring_count=count,ring_spacing_in=pitch)
            self.assertEqual(analyze(p)['grid'],baseline)
        study=spacing_study(default_case());self.assertEqual(len(study),5)
        self.assertTrue(all(a['grid_spacing_in']==11 for a in study))

    def test_load_scaling_and_phi_sensitivity(self):
        a=analyze();p=default_case();p['density_kcf']*=2;b=analyze(p)
        for x,y in zip(a['rings'],b['rings']):
            for key in ('R','qmax','m_per_in','weld_demand'):self.assertAlmostEqual(y[key],2*x[key])
            self.assertAlmostEqual(y['t_bending_req'],sqrt(2)*x['t_bending_req'])
            self.assertGreaterEqual(y['t_req'],y['t_bending_req'])
        p=default_case();p['phi_weld']=.4;c=analyze(p)
        self.assertAlmostEqual(c['rings'][0]['weld_ratio'],2*a['rings'][0]['weld_ratio'])

    def test_plate_integrals_and_two_weld_force_components(self):
        r=analyze();p=r['case'];a=r['rings'][2];rp=p['pile_od_in']/2;rb=max(p['ring_id_in']/2,rp+p['weld_leg_in']);ro=p['ring_od_in']/2
        dr=(ro-rb)/10000
        m=sum(a['qmax']*(rb+(i+.5)*dr-rp)*(rb+(i+.5)*dr)/rp*dr for i in range(10000))
        v=sum(a['qmax']*(rb+(i+.5)*dr)/rp*dr for i in range(10000))
        self.assertAlmostEqual(a['m_per_in'],m,places=8);self.assertAlmostEqual(a['v_per_in'],v,places=8)
        self.assertAlmostEqual(a['weld_demand'],sqrt((v/2)**2+(m/p['ring_t_in'])**2),places=8)
        throat=(p['weld_leg_in']-(p['ring_id_in']-p['pile_od_in'])/2)/sqrt(2)
        self.assertAlmostEqual(a['weld_capacity'],.8*.6*70*throat)
        self.assertGreater(a['weld_demand'],v/2)  # Do not omit radial plate-root moment.

    def test_bearing_annulus_excludes_top_weld_and_compatibility_moment(self):
        r=analyze();p=r['case'];a=r['rings'][0];rp=p['pile_od_in']/2;rb=rp+p['weld_leg_in'];ro=p['ring_od_in']/2
        A=pi*(ro**2-rb**2);I=pi/4*(ro**4-rb**4)
        self.assertAlmostEqual(a['e_nominal'],6.75)
        self.assertAlmostEqual(a['M_superseded'],a['R']*9.75)  # former D-070 basis, kept for comparison only
        # Independent solution: rigid wall on axial/rotational pile springs, pile group displaced by the tolerance.
        ri=rp-p['pile_t_effective_in'];Ap=pi*(rp**2-ri**2);Ip=pi/4*(rp**4-ri**4)
        kv=Ap*p['pile_e_ksi']/p['pile_axial_length_in'];kt=4*p['pile_e_ksi']*Ip/p['pile_free_length_in']
        xs=[16.5+60*i for i in range(4)];xbar=sum(xs)/4;Sx=sum((x-xbar)**2 for x in xs)
        W=r['totals']['factored_weight'];theta=W*3/(kv*Sx+4*kt)
        self.assertAlmostEqual(r['totals']['wall_rotation'],theta);self.assertAlmostEqual(a['M'],kt*theta/5)
        self.assertAlmostEqual(a['dR'],(24/172.375)*kv*theta*90);self.assertAlmostEqual(a['R_design'],a['R']+a['dR'])
        self.assertAlmostEqual(a['qmax'],a['R_design']/A+a['M']*ro/I);self.assertAlmostEqual(a['e_equivalent'],a['M']/a['R_design'])
        self.assertAlmostEqual(r['totals']['kern_limit'],I/(A*ro));self.assertLess(a['e_equivalent'],r['totals']['kern_limit'])
        self.assertTrue(all(x['contact_ok'] for x in r['rings']));self.assertLess(a['M'],a['M_superseded']/10)
        p['placement_tolerance_in']=0;b=analyze(p);keys=('service_weight','factored_weight','force_error','moment_error')
        self.assertEqual({k:r['totals'][k] for k in keys},{k:b['totals'][k] for k in keys})
        self.assertEqual(b['rings'][0]['M'],0);self.assertEqual(b['rings'][0]['dR'],0);self.assertGreater(a['qmax'],b['rings'][0]['qmax'])

    def test_single_pile_and_imposed_rotation_moments(self):
        p=default_case();p.update(pile_count=1);r=analyze(p);W=r['totals']['factored_weight']
        self.assertAlmostEqual(r['totals']['pile_head_moment'],W*3)  # no axial couple: one pile carries W·Δp in bending
        for a in r['rings']:self.assertAlmostEqual(a['M'],W*3/5);self.assertEqual(a['dR'],0)
        p.update(ring_count=1);a=analyze(p)['rings'][0]
        self.assertAlmostEqual(a['M'],a['M_superseded']);self.assertAlmostEqual(a['e_equivalent'],3.)
        p=default_case();p.update(imposed_rotation_rad=.001);r=analyze(p);kt=next(n['value'] for n in r['nodes'] if n['name']=='pile_rotational_stiffness')
        self.assertGreater(r['totals']['wall_rotation'],.001);self.assertAlmostEqual(r['totals']['pile_head_moment'],kt*r['totals']['wall_rotation'])

    def test_contact_failure_blocks_local_strength_pass(self):
        base=analyze();self.assertTrue(all(c['status']=='PASS' for c in base['checks'] if c['id'] not in ('RING-END','RING-GRID')))
        p=default_case();p.update(imposed_rotation_rad=.002);r=analyze(p);checks={c['id']:c for c in r['checks']}
        self.assertEqual(checks['R1-P1-CONTACT']['status'],'FAIL')
        for key in ('BEAR','PLATE','SHEAR','WELD','RING-BASE','PIPE-BASE','PIPE-YIELD'):
            self.assertEqual(checks['R1-P1-'+key]['status'],'PENDING')
        p=default_case();p.update(length_in=240.,thickness_in=44.)
        r=analyze(p)
        self.assertTrue(all(a['contact_ok'] for a in r['rings']))
        self.assertTrue(all(c['status']=='PASS' for c in r['checks']))
        self.assertTrue(r['pending']);self.assertIn('LIMITED SCOPE',r['overall'])

    def test_detailing_gates_and_minimum_weld_table_boundaries(self):
        r=analyze();c={x['id']:x for x in r['checks']}
        self.assertEqual(c['RING-END']['status'],'FAIL');self.assertEqual(c['RING-GRID']['status'],'FAIL')
        p=default_case();p.update(auto_grid_spacing=False,grid_spacing_in=12.,u_leg_in=50.,vertical_lap_in=40.,cover_in=2.5)
        c={x['id']:x for x in analyze(p)['checks']}
        for key in ('GRID-A','U-LAP','V-LAP','COVER'):self.assertEqual(c[key]['status'],'FAIL')
        for thickness,expected in [(0.25,.125),(.5,.1875),(.75,.25),(.751,.3125)]:
            p=default_case();p.update(ring_t_in=thickness,pile_t_effective_in=.20)
            vals={x['name']:x['value'] for x in analyze(p)['nodes']}
            self.assertAlmostEqual(vals['minimum_table_weld'],expected)
            self.assertAlmostEqual(vals['weld_minimum'],min(expected,.20))

    def test_invalid_inputs_and_case_migration(self):
        for changes in [dict(ring_count=100),dict(pile_count=True),dict(ring_id_in=19.),dict(height_in=float('nan')),dict(weld_leg_in=.02),dict(weld_leg_in=2.),dict(coating='guess'),dict(phi_weld=1.1),dict(ring_fu_ksi=30.),dict(grid_bar=3),dict(cover_in=20.),
                        dict(imposed_rotation_rad=.1),dict(imposed_rotation_rad=-.001),dict(pile_free_length_in=0.),dict(schema_version=2)]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):analyze(default_case()|changes)
        legacy=default_case();legacy.pop('schema_version');legacy.update(support_model='face_transfer',arch_rise_in=10.,bearing_fraction=.5,additional_service_ksf=0)
        for key in ('pile_e_ksi','pile_free_length_in','pile_axial_length_in','imposed_rotation_rad'):legacy.pop(key)
        p,notice=upgrade_case(legacy);self.assertEqual(len(notice),2);self.assertNotIn('support_model',p);self.assertEqual(p['schema_version'],3)
        legacy['additional_service_ksf']=.02
        with self.assertRaises(ValueError):upgrade_case(legacy)
        two=default_case()|dict(schema_version=2,placement_tolerance_in=2.)
        for key in ('pile_e_ksi','pile_free_length_in','pile_axial_length_in','imposed_rotation_rad'):two.pop(key)
        p,notice=upgrade_case(two);self.assertEqual(len(notice),1);self.assertIn('D-070',notice[0])
        self.assertEqual(p,default_case()|dict(placement_tolerance_in=2.));self.assertEqual(analyze(p)['case'],p)

    def test_export_manifest_and_offline_report(self):
        with tempfile.TemporaryDirectory(dir=ROOT,prefix='.ring-wall-test-') as folder:
            r=analyze();paths=export_results(r,folder);self.assertEqual(len(paths),12)
            with zipfile.ZipFile(Path(folder)/'Ring_Wall_Design_Exports.zip') as z:
                self.assertEqual(json.loads(z.read('ring_wall_case.json')),r['case'])
                manifest=json.loads(z.read('ring_wall_export_manifest.json'))
                for name,sha in manifest['files'].items():self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(),sha)
                report=z.read('ring_wall_report.html').decode()
                self.assertIn('Numeric substitution and schematic',report);self.assertIn('Plotly.newPlot',report)
                self.assertNotIn('<script src=',report);self.assertIn('full compression',report);self.assertIn('D-070',report)
                self.assertIn('FULL CONTACT FAILS',render_report(analyze(default_case()|dict(imposed_rotation_rad=.002))))
                with zipfile.ZipFile(io.BytesIO(z.read('ring_wall_source.zip'))) as src:
                    self.assertIn('ring_wall/_native/bpad_sheet.py',src.namelist())

    def test_portable_notebook_executes_and_embeds_exact_source(self):
        nb=json.loads((ROOT/'Pier_Wall_Design.ipynb').read_text(encoding='utf-8'));ns={};oldpath=sys.path[:]
        oldmods={k:v for k,v in sys.modules.items() if k=='ring_wall' or k.startswith('ring_wall.')}
        try:
            with tempfile.TemporaryDirectory(dir=ROOT,prefix='.ring-wall-test-') as folder,chdir(folder),patch('IPython.display.display'):
                for i,c in enumerate(nb['cells']):
                    if c['cell_type']=='code':exec(compile(''.join(c['source']),f'cell-{i}','exec'),ns)
                app=ns['app'];self.assertFalse(app.export_root.exists())
                payload=base64.b64decode(ns['PACKAGE']);self.assertEqual(hashlib.sha256(payload).hexdigest(),ns['PACKAGE_SHA256'])
                with zipfile.ZipFile(io.BytesIO(payload)) as z:
                    for name in z.namelist():self.assertEqual(z.read(name),(ROOT/name).read_bytes())
                saved=app.export();self.assertTrue((saved/'ring_wall_design.xmcd').is_file())
                app.controls['ring_t_in'].value=1.
                with self.assertRaises(RuntimeError):app.export()
                exec(''.join(nb['cells'][2]['source']),ns)
                self.assertEqual(ns['app'].case['ring_t_in'],1.);self.assertEqual(ns['app'].last_export,saved)
                ns['app'].close()
        finally:
            sys.path[:]=oldpath
            for key in list(sys.modules):
                if key=='ring_wall' or key.startswith('ring_wall.'):del sys.modules[key]
            sys.modules.update(oldmods)


if __name__=='__main__':unittest.main()
