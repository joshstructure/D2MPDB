"""3D paths must match the shared cage and preserve hollow pile topology."""
from copy import deepcopy
from pathlib import Path
import json
import math
import tempfile
import unittest
from lxml import etree as E
from pier_cap.cage_3d import layout_3d,circular_mesh
from pier_cap.model import evaluate,bar_positions,set_inputs
from pier_cap.detailing import hook_paths
from pier_cap.transverse import suggested_detail,scheduled_bars
from pier_cap.pile_visual import pile_appearance,validate_pile_visual
from pier_cap.fbmp import import_fbmp_xml
from pier_cap.io import write_case,load_case,export_bundle
from pier_cap.widgets import CapNotebook
from tests.case_fixtures import default_case


def case(shape='pipe'):
    c=set_inputs(default_case(),n_N2=3,n_P2=2,n_B2=2,n_skin=3)
    c['pile_visual']=dict(version=1,shape=shape,wall_in=.48 if shape=='pipe' else None,filled=False if shape=='pipe' else None,source='Test')
    c['transverse_detail']=suggested_detail(evaluate(c))
    return c


class Cage3DTests(unittest.TestCase):
    def test_every_longitudinal_bar_uses_the_section_coordinates(self):
        e=evaluate(case());f=layout_3d(e)
        steel=[t for t in f.data if t.meta.get('part') in ('top','bottom','side')]
        bars=bar_positions(e,'P');self.assertEqual(len(steel),len(bars))
        for trace,bar in zip(steel,bars):
            self.assertEqual(list(trace.x),[e.case['inputs']['C_s'],e.value('L_cap')-e.case['inputs']['C_s']])
            self.assertEqual(list(trace.y),[bar['x']]*2);self.assertEqual(list(trace.z),[bar['y']]*2)
            self.assertEqual(trace.meta['bar'],bar['bar'])
        transverse=[t for t in f.data if t.meta.get('part')=='transverse']
        self.assertEqual(len(transverse),len(scheduled_bars(e.case)))

    def test_added_bars_retain_both_bends_and_tails_in_every_span(self):
        e=evaluate(case());f=layout_3d(e)
        extra=[t for t in f.data if t.meta.get('part')=='added'];paths=hook_paths(e,bar_positions(e,'B'))
        self.assertEqual(len(extra),len(paths));self.assertGreater(len(extra),0)
        for trace,path in zip(extra,paths):
            self.assertEqual(list(zip(trace.x,trace.z)),path['points'])
            self.assertTrue(all(y==path['bar']['x'] for y in trace.y))

    def test_pipe_has_real_inner_wall_and_no_solid_disk_over_bore(self):
        mesh=circular_mesh(0,0,10,-12,12,inner_radius=9.52)
        radii=[math.hypot(x,y) for x,y in zip(mesh.x,mesh.y)]
        self.assertAlmostEqual(min(radii),9.52);self.assertAlmostEqual(max(radii),10)
        # Every top triangle stays in the annulus, allowing only chord error.
        for i,j,k in zip(mesh.i,mesh.j,mesh.k):
            if all(mesh.z[v]==12 for v in (i,j,k)):
                center=(sum(mesh.x[v] for v in (i,j,k))/3,sum(mesh.y[v] for v in (i,j,k))/3)
                self.assertGreater(math.hypot(*center),9.5)
        f=layout_3d(evaluate(case()))
        self.assertEqual(len([t for t in f.data if t.type=='mesh3d' and t.meta.get('part')=='piles']),4)

    def test_square_stays_square_and_concrete_pipe_fill_is_explicit(self):
        f=layout_3d(evaluate(case('square')))
        piles=[t for t in f.data if t.meta.get('part')=='piles']
        self.assertTrue(all(t.type=='mesh3d' and len(set(t.x))==2 and len(set(t.y))==2 for t in piles))
        c=case();c['pile_visual']['filled']=True
        self.assertEqual(len([t for t in layout_3d(evaluate(c)).data if t.name=='Concrete infill']),4)

    def test_unknown_shape_or_wall_is_not_invented(self):
        c=case();c.pop('pile_visual')
        self.assertEqual(pile_appearance(c)['shape'],'unknown')
        f=layout_3d(evaluate(c));piles=[t for t in f.data if t.meta.get('part')=='piles']
        self.assertTrue(all(t.type=='scatter3d' and t.line.dash=='dot' for t in piles))
        c=case();c['pile_visual']['wall_in']=None
        piles=[t for t in layout_3d(evaluate(c)).data if t.meta.get('part')=='piles']
        self.assertTrue(all(t.type=='scatter3d' for t in piles))
        c['pile_visual']['wall_in']=c['inputs']['D_pile']/2
        with self.assertRaises(ValueError):validate_pile_visual(c)

    def test_xml_and_json_retain_shape_wall_and_fill(self):
        source=Path(__file__).parent/'fixtures/fbmp_610_cap.xml'
        root=E.parse(str(source));segment=root.find('.//PILE_GEOMETRY/SEGMENT')
        material=E.SubElement(segment,'MATERIAL_PROPS');E.SubElement(material,'FPC',units='ksi').text='0'
        pipe=import_fbmp_xml(E.tostring(root))
        self.assertEqual(pipe['pile_visual']['shape'],'pipe');self.assertEqual(pipe['pile_visual']['wall_in'],.48)
        self.assertIs(pipe['pile_visual']['filled'],False)
        segment.find('DIMENSIONS').set('type','Rectangular')
        square=import_fbmp_xml(E.tostring(root),base=pipe)
        self.assertEqual(square['pile_visual']['shape'],'square');self.assertIsNone(square['pile_visual']['wall_in'])
        with tempfile.TemporaryDirectory() as d:
            path=write_case(pipe,Path(d)/'case.json')
            self.assertEqual(load_case(path)['pile_visual'],pipe['pile_visual'])

    def test_views_work_without_transverse_stations_and_buttons_select_groups(self):
        c=case();c['transverse_detail']['enabled']=False;fig=layout_3d(evaluate(c))
        self.assertFalse(any(t.meta.get('part')=='transverse' for t in fig.data))
        for button in fig.layout.updatemenus[0].buttons:
            visibility=button.args[0]['visible'];self.assertEqual(len(visibility),len(fig.data))
            if button.label=='Piles only':
                self.assertTrue(all(v==(t.meta['part']=='piles') for v,t in zip(visibility,fig.data)))
        with tempfile.TemporaryDirectory() as d:
            folder=export_bundle(c,d)
            self.assertIn('3D CAGE',(folder/'reinforcement_detail.html').read_text(encoding='utf-8'))

    def test_manual_pile_appearance_changes_view_and_roundtrips(self):
        app=CapNotebook(default_case())
        try:
            panel=app.pile_appearance;panel.shape.value='pipe';panel.wall.value='.5';panel.filled.value=False;panel.apply.click()
            self.assertEqual(app.case['pile_visual']['wall_in'],.5)
            self.assertIsNotNone(app.current)
            saved=deepcopy(app.case);app.load(default_case());self.assertEqual(panel.shape.value,'unknown')
            app.load(saved);self.assertEqual(panel.shape.value,'pipe');self.assertEqual(panel.wall.value,'0.5')
            panel.wall.value='20';panel.apply.click()
            self.assertEqual(app.case,saved);self.assertIn('less than half',panel.status.value)
        finally:app.close()


if __name__=='__main__':unittest.main()
