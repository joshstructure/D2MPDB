"""Physical station cuts checked against saved FreeCAD solids and the HTML engine."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import unittest

import numpy as np
from bridge_report import clean, report_data

ROOT=Path(__file__).resolve().parents[1]


def load_model():
    notebook=json.loads((ROOT/'Bridge_Geometry_2 Beam_V2.ipynb').read_text(encoding='utf-8'))
    cells={c['id']:c for c in notebook['cells']}
    env=dict(Path=Path,np=np)
    for ident in ('bridge-03','bridge-05'):exec(''.join(cells[ident]['source']),env)
    env['CONFIG']['roadway']['xml_path']=str(ROOT/'Geometry Report.xml')
    tree=ast.parse(''.join(cells['bridge-06']['source']))
    functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('fib_polygon','section_geometry')]
    exec(compile(ast.Module(body=functions,type_ignores=[]),'section-functions','exec'),env)
    return env,env['BridgeModel'](env['CONFIG'])


def native_measures(components,support):
    result={}
    for component in components:
        kind=component['kind']
        if kind=='Cap':name='BridgeCap'+support
        elif kind=='Pile':name=f"BridgePile{support}P{component['pile']}"
        elif kind=='Pedestal':name=f"BridgePedestal{support}B{component['beam']}"
        elif kind=='Bearing':name=f"BridgePad{support}S{component['span']}B{component['beam']}"
        elif kind=='Cheek':name=f"BridgeCheek{support}{1 if component['side']=='L' else 2}"
        else:continue  # Backwalls: the CAD seat follows the MSE landing underside.
        xy=np.asarray(component['xy']);x,y=xy.T
        area=abs(np.dot(x,np.roll(y,1))-np.dot(y,np.roll(x,1)))/2
        bounds=np.array([x.min(),x.max(),y.min(),y.max()])
        if name in result:
            old=result[name]
            bounds=np.array([min(bounds[0],old['bounds_ft'][0]),max(bounds[1],old['bounds_ft'][1]),
                             min(bounds[2],old['bounds_ft'][2]),max(bounds[3],old['bounds_ft'][3])])
            area+=old['area_ft2']
        result[name]=dict(area_ft2=area,bounds_ft=bounds)
    return result


class PhysicalGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env,cls.model=load_model()
        cls.reference=json.loads((ROOT/'tests/data/bridge_native_sections.json').read_text())

    def test_sections_match_native_saved_solids(self):
        self.assertEqual(self.model.cfg['physical_geometry']['source_sha256'],self.reference.get('dimensional_baseline_sha256',self.reference['source_sha256']))
        if 'notebook_model_id' in self.reference:
            # Native measurements track the updated geometry, while the imported
            # dimensional baseline remains historical provenance (not CAD input).
            config=copy.deepcopy(self.model.cfg)
            config['roadway']['xml_path']='Geometry Report.xml'
            # D-053 lowers only the two backwall tops by 1/4 in. This native
            # fixture excludes backwalls; retain its original configuration ID
            # check for every other input instead of relabeling old CAD evidence.
            config['end_bents']['start']['backwall_drop_in']=4.0
            config['end_bents']['end']['backwall_drop_in']=4.0
            self.assertEqual(self.env['configuration_id'](config),self.reference['notebook_model_id'])
            current=json.loads((ROOT/'bridge_geometry/project_source.json').read_text())['current_geometry_source']
            self.assertEqual(current['sha256'],self.reference['source_sha256'])
            self.assertEqual(hashlib.sha256((ROOT/current['source_file']).read_bytes()).hexdigest(),self.reference['source_sha256'])
        for sample in self.reference['samples']:
            with self.subTest(station=sample['station'],support=sample['support']):
                measured=native_measures(self.model.support_section(sample['station']),sample['support'])
                expected={c['name']:c for c in sample['components']}
                self.assertEqual(set(measured),set(expected))
                for name,actual in measured.items():
                    self.assertAlmostEqual(actual['area_ft2'],expected[name]['area_ft2'],places=7,msg=name)
                    np.testing.assert_allclose(actual['bounds_ft'],expected[name]['bounds_ft'],rtol=0,atol=1e-8,err_msg=name)

    def test_joint_and_bearing_cuts_are_distinct(self):
        model=self.model;s=model.pier['station']
        center=self.env['section_geometry'](model,s)[0]['components']
        self.assertEqual({c['kind'] for c in center},{'Deck','Cap','Pile','Pedestal'})
        self.assertEqual(sum(c['kind']=='Pile' for c in center),8)
        offset=self.env['section_geometry'](model,s+.5)[0]['components']
        self.assertEqual(sum(c['kind']=='Bearing' for c in offset),2)
        self.assertEqual({c['span'] for c in offset if c['kind']=='Bearing'},{2})
        self.assertEqual(sum(c['kind']=='Beam' for c in offset),2)
        outer=self.env['section_geometry'](model,s+1)[0]['components']
        self.assertFalse(any(c['kind']=='Pile' for c in outer))
        self.assertTrue(any(c['kind']=='Cap' for c in outer))
        self.assertFalse(model.support_section(s+2.00001))
        self.assertTrue(model.support_section(model.inspection_start))
        self.assertFalse(model.inspect(model.inspection_start)['beam_present'][0])

    def test_caps_remain_at_user_reported_stations_after_one_hundredth_foot_move(self):
        for station,name in ((1593.22,'End Bent 1'),(1700.57,'Pier'),(1805.47,'End Bent 2')):
            for delta in (-.01,0,.01):
                with self.subTest(station=station,delta=delta):
                    section=self.env['section_geometry'](self.model,station+delta)[0]
                    self.assertEqual(section['support']['name'],name)
                    self.assertEqual(sum(c['kind']=='Cap' for c in section['components']),1)

    def test_public_model_cannot_silently_use_the_old_station_only_mode(self):
        for mode in ('missing','disabled'):
            config=copy.deepcopy(self.env['CONFIG'])
            if mode=='missing':config.pop('physical_geometry')
            else:config['physical_geometry']['enabled']=False
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'Physical support geometry is required'):
                self.env['BridgeModel'](config)

    def test_camber_is_zero_at_bearings_and_pipe_wall_is_nominal(self):
        np.testing.assert_allclose(self.model.evaluate(np.array(self.model.bearing_limits).ravel())['camber'],0,atol=1e-10)
        pipes=[c for c in self.model.support_section(1700.57) if c['kind']=='Pile']
        np.testing.assert_allclose([np.ptp(c['xy'][:,0])*12 for c in pipes],.625,atol=1e-10)
        self.assertTrue(self.model.selected_table(1700.57)['Beam bottom (ft)'].isna().all())

    def test_invalid_physical_footprints_are_rejected(self):
        for edits in ({'pad_length_in':100},{'pedestal_length_in':60},{'pile_wall_in':11}):
            config=copy.deepcopy(self.env['CONFIG']);config['pier'].update(edits)
            with self.subTest(edits=edits),self.assertRaises(ValueError):self.env['BridgeModel'](config)

    def test_extrema_exclude_open_joints_and_end_clearances(self):
        for profile,deck in [('brokeback','crowned'),('parabolic','uniform'),('parabolic','transition')]:
            config=copy.deepcopy(self.env['CONFIG'])
            config['profile']['mode']=profile;config['deck']['mode']=deck
            model=self.env['BridgeModel'](config)
            for i,(a,b) in enumerate(model.beam_limits):
                self.assertTrue(np.all((model.haunch_candidates[i]>=a)&(model.haunch_candidates[i]<=b)))
            dense=np.concatenate([np.linspace(a,b,10001) for a,b in model.beam_limits])
            minimum=float(np.min(model.evaluate(dense)['haunch']))
            self.assertAlmostEqual(minimum,model.haunch_min,places=6)

    @unittest.skipUnless(shutil.which('node'),'Node required for offline engine parity')
    def test_browser_engine_matches_notebook_at_physical_boundaries(self):
        model=self.model
        stations=[sample['station'] for sample in self.reference['samples']]
        stations += [s+delta for s in (1593.22,1700.57,1805.47) for delta in (-.01,0,.01)]
        stations += [a+delta for pair in model.beam_limits+model.bearing_limits+model.deck_limits
                     for a in pair for delta in (-1e-6,0,1e-6)]
        for support in model.supports:
            for pad in support['solid_geometry']['bearings']:
                stations += [a+delta for a in pad['bounds'] for delta in (-1e-6,0,1e-6)]
            radius=support['solid_geometry']['piles'][0]['diameter']/2
            stations += [support['station']+sign*radius+delta for sign in (-1,1) for delta in (-1e-6,0,1e-6)]
            for wall in support['solid_geometry'].get('walls',[]):
                stations += [a+delta for a in wall['bounds'] for delta in (-1e-6,0,1e-6)]
        stations=sorted(s for s in set(stations) if model.inspection_start<=s<=model.inspection_end)
        data=report_data(model,self.env['section_geometry'])
        script=(ROOT/'bridge_report/report-engine.js').read_text()+"\nconst p=JSON.parse(require('fs').readFileSync(0,'utf8'));const e=makeBridgeReportEngine(p.data);process.stdout.write(JSON.stringify(p.stations.map(s=>e.evaluate(s))));"
        process=subprocess.run(['node','-e',script],cwd=ROOT,input=json.dumps(dict(data=data,stations=stations)),text=True,capture_output=True)
        self.assertEqual(process.returncode,0,process.stderr)
        results=json.loads(process.stdout)
        for station,actual in zip(stations,results):
            with self.subTest(station=station):
                expected=self.env['section_geometry'](model,station)[0]['components']
                for kind in ('Cap','Pile','Pedestal','Bearing','Beam','Deck','Haunch','Backwall','Cheek'):
                    a=[c for c in actual['components'] if c['kind']==kind]
                    b=[c for c in expected if c['kind']==kind]
                    self.assertEqual(len(a),len(b),kind)
                    # Templates remove collinear points; compare physical areas and bounds.
                    for x,y in zip(a,b):
                        p,q=np.array(x['xy']),np.array(y['xy'])
                        np.testing.assert_allclose([p.min(0),p.max(0)],[q.min(0),q.max(0)],rtol=0,atol=1e-8,err_msg=kind)
                        area=lambda v:abs(np.dot(v[:,0],np.roll(v[:,1],1))-np.dot(v[:,1],np.roll(v[:,0],1)))/2
                        self.assertAlmostEqual(area(p),area(q),places=7,msg=kind)
                value=model.inspect(station)
                self.assertEqual(actual['beamPresent'],bool(value['beam_present'][0]))
                self.assertEqual(actual['deckPresent'],bool(value['deck_present'][0]))
                np.testing.assert_allclose([np.nan if x is None else x for x in actual['clearance']],value['clearance'][0],rtol=0,atol=1e-8,equal_nan=True)


if __name__=='__main__':unittest.main()
