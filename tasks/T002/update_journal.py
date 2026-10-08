"""Bounded T002 authoring; original XML bytes outside explicit edits are retained."""
from pathlib import Path
import sys, json, re, hashlib, shutil, html
import xml.etree.ElementTree as E
from bs4 import BeautifulSoup

REPO = Path(__file__).resolve().parents[2]
TASK = Path(__file__).parent
sys.path.insert(0, str(REPO))
from tools.bpad_workflow import Journal

SOURCE = Path('C:/Users/joshs/Downloads/End bent 1 Cap Design Report_10-8.html')
EXPECTED = '42120857965352febea29e4a672b2ba93f45199430360a89f8e1e529d2df50ef'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED
base = Journal.load(TASK/'base.bpad')
assert base.sha256 == '5611bee7a1b517f798521029bb9965f3c756941e564280fd8a37d09f81b7dfcd'
src = TASK/'sources'
src.mkdir(exist_ok=True)
shutil.copy2(SOURCE, src/SOURCE.name)
soup = BeautifulSoup(SOURCE.read_bytes(), 'html.parser')
case_text = soup.find('pre').get_text()
case = json.loads(case_text)
(src/'end_bent_1_report_case.json').write_text(case_text, encoding='utf8')
assert case['inputs']['b'] == 42 and case['pile_visual']['shape'] == 'square'
tables = []
for t in soup.find_all('table'):
    rows = [[c.get_text(' ',strip=True) for c in r.find_all(['th','td'],recursive=False)] for r in t.find_all('tr')]
    tables.append(rows)
(src/'provenance.json').write_text(json.dumps({
    'report_file': SOURCE.name, 'report_sha256': EXPECTED,
    'generated_utc':'2026-10-08T15:27:00+00:00',
    'case_sha256':hashlib.sha256((src/'end_bent_1_report_case.json').read_bytes()).hexdigest(),
    'analysis_xml_sha256':case['analysis']['xml_audit']['sha256'],
    'local_same_named_xml_sha256':hashlib.sha256(Path('C:/Users/joshs/Downloads/End Bent 1.XML').read_bytes()).hexdigest(),
    'geometry_and_cage_scope':'Both end bents, confirmed by user on 2026-10-08',
    'analysis_scope':'End Bent 1 only; exact raw XML not available',
}, indent=2),encoding='utf8')

def para(p,text='',**kw):
    a={'fontfamily':'Times New Roman','fontsize':'11','leftindent':'0','spacingafter':'7'}
    a.update({k:str(v) for k,v in kw.items()})
    e=E.SubElement(p,'paragraph',a); e.text=text; return e
def heading(p,text,level=1):
    e=E.SubElement(p,'heading',level=str(level),keepwithnext='True')
    if text in ('End-bent cap and pile layout — both end bents',
                'Current end-bent cap design record — 8 October 2026',
                '2. Current longitudinal reinforcement',
                '3. Actual transverse schedule',
                '4. Recorded fitted bar coordinates',
                '6. Quantities and unresolved coherence items'):
        e.set('pagebreakbefore','break')
    e.text=text
    return e
def section(name): return E.Element('section',name=name,capture='False',hide='false')
def eq(p,formula,caption='',input=False):
    q=para(p,spacingbefore='4',spacingafter='2',keepwithnext='True')
    e=E.SubElement(q,'dynexp',formula=formula,mathlayout='on',showsteps='False',seplines='False')
    if input:e.set('style','Required Input')
    E.SubElement(e,'expbody').text=formula
    if caption:para(p,caption,fontsize='10')
def link(p,label,address):
    E.SubElement(para(p,fontsize='10'),'link',address=address).text=label
def f(x):return (x,)
def table(p,name,headers,rows,widths,kind='discussion'):
    colors={'discussion':('#DCE7F3','#F1F5FA','#7189A6'),'input':('#F7E6B9','#FFF8E9','#A78638'),'output':('#DCECE0','#EFF7F1','#6A9075')}
    head,fill,border=colors[kind]
    t=E.SubElement(E.SubElement(p,'embed',spacingbefore='8',spacingafter='12',leftindent='0'),'table',name=name,capture='False',colwidths=', '.join(f'{i+1}:{v}' for i,v in enumerate(widths)))
    last=chr(64+len(headers)); end=len(rows)+1
    E.SubElement(t,'stylerule',range=f'A1:{last}{end}',fontfamily='Times New Roman',fontsize='10',valueformat='RoundedNumber(3, 3, {PriorityUnits: []})',border=f'Border("AllSides", "Solid", 0.7, "{border}"); Border("BetweenRows", "Solid", 0.35, "{border}"); Border("BetweenColumns", "Solid", 0.35, "{border}");',vertalign='Center')
    E.SubElement(t,'stylerule',range=f'A1:{last}1',background=head,fontweight='bold')
    E.SubElement(t,'stylerule',range=f'A2:{last}{end}',background=fill)
    for row in [headers]+rows:
        r=E.SubElement(t,'row')
        for v in row:
            if isinstance(v,tuple):
                E.SubElement(r,'c',capture='False',formula=v[0])
            elif len(str(v))>20:
                c=E.SubElement(r,'textcell',capture='False')
                para(c,str(v),fontsize='10',spacingafter='3')
            else:
                c=E.SubElement(r,'c',capture='False')
                E.SubElement(c,'textvalue').text=str(v)
    return t
def xml(e):return E.tostring(e,encoding='unicode',short_empty_elements=True)

mapping=json.loads((TASK/'components.json').read_text())
parts={k:base.part(k).decode('utf8') for k in mapping}
change_log=[]
def replace(key,old,new,count=1):
    assert parts[key].count(old)==count,(key,old,parts[key].count(old))
    parts[key]=parts[key].replace(old,new)
    change_log.append({'component':key,'old':old,'new':new})
def append(key,e):
    tag=key.split(':')[0]
    parts[key]=parts[key].replace(f'</{tag}>','\n'+xml(e)+f'\n</{tag}>')
def after_heading(key,e):
    pos=parts[key].index('</heading>')+len('</heading>')
    parts[key]=parts[key][:pos]+'\n'+xml(e)+parts[key][pos:]

G='report:BridgeGeometry_2Beam'; F='report:FBMPEndBent'; Q='spreadsheet:QauntitiesBridge'
replace(G,'EndBentCap_width = 36 in to in','EndBentCap_width = 42 in to in',2)
replace(G,'User input, 30 September 2026: 36-in by 36-in cap section; bearing spacing unchanged. The cap length and the absolute FBMP node coordinates are not established by these two section dimensions.',
 'Current geometry for both end bents: cap and pile dimensions follow the 8 October 2026 End Bent 1 cap report; applicability to both end bents is confirmed by the user. Bearing spacing and the backwall/beam-end placement chain remain the journal basis. End Bent 1 analysis results are recorded separately from this shared geometry.')
replace(G,'Bearing eccentricity toward the adjacent span relative to the centered pile/cap line. Current chain: 0 + 12 + 3 + 9 - 18 = 6 in.',
 'Bearing eccentricity toward the adjacent span relative to the centered pile/cap line. It follows the live rear-face, backwall, beam-end and half-cap-width chain. Verify this reference point against the exact analysis model.')
replace(G,'Checks the dimension chain only; the existing 4-ft pedestal footprint still requires reconciliation with the 3-ft cap.',
 'Checks the pad dimension chain only. The retained 48-in pedestal footprint exceeds the current cap width and remains unresolved; this check does not establish pedestal fit.')
replace(G,'* Pedestal outline is illustrative: the legacy 4-ft longitudinal footprint exceeds the new 3-ft cap width. The bearing-offset calculation uses the pad and backwall dimension chain, not that unresolved footprint. Rear backwall face is adopted flush with cap rear face.',
 '* Pedestal outline is illustrative. Its retained 48-in longitudinal footprint exceeds the current 42-in cap width. The bearing-offset calculation uses the pad and backwall chain, not that unresolved footprint. Rear backwall face remains adopted flush with cap rear face.')

g=section('EndBentCurrentGeometry')
heading(g,'End-bent cap and pile layout — both end bents',0)
table(g,'EBCurrentGeometryContext',['Basis','Scope'],[
 ['Source','End bent 1 Cap Design Report_10-8.html, generated 8 October 2026; current saved case.'],
 ['Application','Both end bents: geometry and entered reinforcement. Forces and analysis provenance: End Bent 1 only.'],
 ['Status','Data record with unresolved detailing and model checks; not construction approval.'],
],[100,420])
for formula,caption in [
 ('EndBent_pileCount = 4','Square piles per cap.'),
 ('EndBent_pileWidth = 18 in','Square pile width in both plan directions; not the pier pipe diameter.'),
 ('EndBent_pileSpacing = 54 in','Center-to-center spacing along the cap.'),
 ('EndBent_edgeClear = 9 in','Entered actual pile-face edge-clearance allowance.'),
 ('EndBent_pileTolerance = 3 in','Horizontal placement tolerance allowance, separate from bar clearance.'),
 ('EndBent_endDetail = 4 in','Additional nominal end allowance.'),
 ('EndBent_pileEmbed = 12 in','Physical pile penetration above cap underside; separate from analysis node elevation.'),
 ('EndBent_pileBarClear = 1 in','Entered pile-surface to bar-surface gap; project/code applicability remains a review item.'),
 ('EndBent_coverTop = 3 in','Clear cover to outside of transverse reinforcement.'),
 ('EndBent_coverBottom = 3 in','Clear cover to outside of transverse reinforcement.'),
 ('EndBent_coverSide = 3 in','Clear cover to outside of transverse reinforcement.'),
 ('EndBent_count = 2','Both end bents use this geometry by user confirmation.'),
 ]:eq(g,formula,caption,True)
for formula,caption in [
 ('EndBent_endFace = EndBent_edgeClear+EndBent_pileTolerance+EndBent_endDetail to in','Nominal end-to-outer-pile-face distance.'),
 ('EndBent_endCenter = EndBent_endFace+EndBent_pileWidth/2 to in','Left end to first pile center; equal right end distance.'),
 ('EndBentCap_length = (EndBent_pileCount-1)*EndBent_pileSpacing+2*EndBent_endCenter to ft in','Overall cap length along the pile row.'),
 ('EndBent_pileClearSpacing = EndBent_pileSpacing-EndBent_pileWidth to in','Clear spacing between nominal square pile faces.'),
 ('EndBentCap_area = EndBentCap_width*EndBentCap_depth to ft^2','Gross rectangular cap section; excludes backwall and pedestal.'),
 ('EndBentCap_volume = EndBentCap_area*EndBentCap_length to ft^3','Gross concrete per cap, before pile deductions.'),
 ('EndBentCaps_volume = EndBent_count*EndBentCap_volume to ft^3','Gross rectangular caps at both end bents.'),
 ('EndBentCap_DC = EndBentCap_volume*PedBridgeWeights_2Beams.I29 to kip','Cap-only self-weight using the existing project concrete unit weight. Do not add twice if the foundation model generates cap self-weight.'),
 ]:eq(g,formula,caption)
for i in range(1,5):
    eq(g,f'EndBent_P{i}_station = EndBent_endCenter+{i-1}*EndBent_pileSpacing to in',f'Pile P{i} center station from the left cap end.')
table(g,'EBCurrentPileStations',['Pile','Center (in)','Left face (in)','Right face (in)'],[[f'P{i}',f(f'EndBent_P{i}_station to in'),f(f'EndBent_P{i}_station-EndBent_pileWidth/2 to in'),f(f'EndBent_P{i}_station+EndBent_pileWidth/2 to in')] for i in range(1,5)],[70,150,150,150],'output')
para(g,'Geometry/cage stations start at the left cap end. The source XML audit starts at the first pile center; add EndBent_endCenter to convert audit stations. Bearing audit stations 29.50 and 132.49 in therefore correspond to 54.50 and 157.49 in from the cap end. Their separation is 102.99 in, consistent with the journal’s 103-in bearing spacing to the XML’s displayed precision.')
link(g,'Current reinforcement, source forces and coherence register','#FBMPEndBent.EBCurrentDesignRecord')
append(G,g)

# The existing live drawing follows cap width. Extend its pile envelope to use the
# new square pile width and physical embedment, while retaining its NTS convention.
replace(G,'[1.3+.07*BridgeGeometry_2Beam.EndBent_pileCL_fromRear/(1 in)-.28,1.3+.07*BridgeGeometry_2Beam.EndBent_pileCL_fromRear/(1 in)+.28,1.3+.07*BridgeGeometry_2Beam.EndBent_pileCL_fromRear/(1 in)+.28,1.3+.07*BridgeGeometry_2Beam.EndBent_pileCL_fromRear/(1 in)-.28,1.3+.07*BridgeGeometry_2Beam.EndBent_pileCL_fromRear/(1 in)-.28],[0.7,0.7,1.55,1.55,0.7]',
 '[1.3+.07*BridgeGeometry_2Beam.EndBent_pileCL_fromRear/(1 in)-.035*BridgeGeometry_2Beam.EndBent_pileWidth/(1 in),1.3+.07*BridgeGeometry_2Beam.EndBent_pileCL_fromRear/(1 in)+.035*BridgeGeometry_2Beam.EndBent_pileWidth/(1 in),1.3+.07*BridgeGeometry_2Beam.EndBent_pileCL_fromRear/(1 in)+.035*BridgeGeometry_2Beam.EndBent_pileWidth/(1 in),1.3+.07*BridgeGeometry_2Beam.EndBent_pileCL_fromRear/(1 in)-.035*BridgeGeometry_2Beam.EndBent_pileWidth/(1 in),1.3+.07*BridgeGeometry_2Beam.EndBent_pileCL_fromRear/(1 in)-.035*BridgeGeometry_2Beam.EndBent_pileWidth/(1 in)],[0.7,0.7,1.55+1.3*BridgeGeometry_2Beam.EndBent_pileEmbed/BridgeGeometry_2Beam.EndBentCap_depth,1.55+1.3*BridgeGeometry_2Beam.EndBent_pileEmbed/BridgeGeometry_2Beam.EndBentCap_depth,0.7]')

replace(F,'END BENT 1 | SPAN 1 | NODES 12 AND 19','END BENT 1 | SPAN 1 | LEGACY NODE MAP — VERIFY BEFORE ENTRY')
replace(F,'User: 36 in','Current shared geometry',2)
replace(F,'12 + 3 + 9 - 18 = 6 in; rear face flush','Live rear-face chain minus half the current cap width')
# Make existing application-node status explicitly reflect the unresolved source map.
old='EB_CheckSpan = If(EB_SpanNumber == 1,&quot;END BENT 1 - NODES 12 / 19&quot;,&quot;SPAN SELECTION CHANGED - REMAP NODES&quot;)'
new='EB_CheckSpan = &quot;REMAP REQUIRED - LEGACY 12 / 19; REPORT BEARING STATIONS AT 15 / 34&quot;'
replace(F,old,new)
replace(F,html.unescape(old),html.unescape(new))
warning=E.Element('paragraph',fontfamily='Times New Roman',fontsize='11',background='#FFF8E9',fontweight='bold',spacingafter='10')
warning.text='MODEL COHERENCE OPEN: the load-entry tables retain legacy nodes 12/19. The report audit places the bearing force stations at nodes 15/34. Confirm node mapping, axes, node elevation, longitudinal eccentricity and load inputs against the exact analyzed model before using these tables. The report XML fingerprint differs from the available same-named XML.'
after_heading(F,warning)

r=section('EBCurrentDesignRecord')
heading(r,'Current end-bent cap design record — 8 October 2026',0)
table(r,'EBDesignRecordContext',['Item','Recorded basis'],[
 ['Geometry / cage','Applies to both end bents by user confirmation. Shared dimensions are in Bridge Geometry.'],
 ['Analysis','End Bent 1 only. Independent envelopes; maximum moment, shear and torque are not a concurrent action vector.'],
 ['Design status','DETAILING SCREEN: 0 failed scalar checks; 48 pending/conditional checks; U-bar conflicts at R2, R4, R6 and R8.'],
 ['Source','End bent 1 Cap Design Report_10-8.html; generated 2026-10-08T15:27:00+00:00.'],
],[110,410])
para(r,'Source report SHA-256: '+EXPECTED,fontsize='8')
para(r,'Recorded analysis XML SHA-256: '+case['analysis']['xml_audit']['sha256'],fontsize='8')
link(r,'Shared cap and pile geometry','#BridgeGeometry_2Beam.EndBentCurrentGeometry')
heading(r,'1. Materials and detailing inputs')
for n,v,u,caption in [
 ('EBSteel_fc',5.5,'ksi','Cap concrete strength in the report; this is not a pile concrete material definition.'),
 ('EBSteel_fy',60,'ksi','Reinforcing yield strength.'),
 ('EBSteel_Es',29000,'ksi','Reinforcing modulus.'),
 ('EBSteel_barClear',2,'in','Minimum bar-to-bar construction clearance in the source screening; distinct from pile-to-bar gap.'),
 ('EBSteel_aggregate',0.75,'in','Source case nominal maximum aggregate, recorded as confirmed in the source case.'),
 ]:eq(r,f'{n} = {v} {u}',caption,True)
table(r,'EBDesignFactors',['Source factor','Value','Review basis'],[
 ['Flexure / shear-torsion','0.90 / 0.90','Adopted source factors; code edition and applicability not closed.'],
 ['Crack exposure / fatigue','1.00 / 1.75','Fatigue remains pending.'],
 ['Shear beta / theta / alpha','2.00 / 45 deg / 90 deg','Simplified source model.'],
 ['Prestress credit / torsion area factor','0 ksi / 0.85','No favorable axial/prestress credit.'],
],[175,140,205],'input')
heading(r,'2. Current longitudinal reinforcement')
for formula,caption in [
 ('EBSteel_topCount = 4','Continuous #6 top bars; one row.'),
 ('EBSteel_topAreaEach = 0.44 in^2','Source area for one #6 bar.'),
 ('EBSteel_bottomCount = 2','Continuous #8 bottom bars at piles and between piles.'),
 ('EBSteel_bottomAreaEach = 0.79 in^2','Source area for one #8 bar.'),
 ('EBSteel_addedCount = 2','Additional #5 bottom bars between piles, beyond the two continuous #8 bars; 90-degree hooked ends.'),
 ('EBSteel_addedAreaEach = 0.31 in^2','Source area for one #5 bar.'),
 ('EBSteel_skinEachSide = 7','Continuous #4 skin bars on each side, excluding top and bottom main bars.'),
 ('EBSteel_skinAreaEach = 0.20 in^2','Source area for one #4 bar.'),
 ('EBSteel_AsTop = EBSteel_topCount*EBSteel_topAreaEach to in^2','Top flexural area.'),
 ('EBSteel_AsPile = EBSteel_bottomCount*EBSteel_bottomAreaEach to in^2','Continuous bottom flexural area at piles.'),
 ('EBSteel_AsSpan = EBSteel_AsPile+EBSteel_addedCount*EBSteel_addedAreaEach to in^2','Combined between-pile bottom flexural area; additions are not the total.'),
 ('EBSteel_AsSkinSide = EBSteel_skinEachSide*EBSteel_skinAreaEach to in^2','Skin area per side; excluded from the report flexural areas.'),
 ]:eq(r,formula,caption,'=' in formula and not formula.startswith(('EBSteel_As')))
table(r,'EBLongitudinalSummary',['Family','Entered bars','Area'],[
 ['Top','4 #6 continuous',f('EBSteel_AsTop to in^2')],
 ['Bottom at piles','2 #8 continuous',f('EBSteel_AsPile to in^2')],
 ['Bottom between piles','2 #8 continuous + 2 #5 additional',f('EBSteel_AsSpan to in^2')],
 ['Skin, each side','7 #4 continuous',f('EBSteel_AsSkinSide to in^2')],
],[150,250,120],'output')
para(r,'Additional top rows, second bottom rows and longitudinal U tension-leg counts are zero. The dormant longitudinal U input is #8 with zero credited legs; actual transverse open-bottom U-bars below are #4. Manual spacing overrides are inactive. The actual station schedule controls; a uniform closed-hoop reference does not represent this cage.')
heading(r,'3. Actual transverse schedule')
para(r,'All stations below are inches from the left cap end. Each run uses #4 bars at 6-in pitch, global shear basis G. Nineteen closed hoops plus sixteen open-bottom U-bars give 35 transverse bars. Development is unconfirmed for every run. U ends use 90-degree bends, 6-in straight tails and 3-in inside bend diameter; these ends conflict with pile/clearance envelopes in the source.')
runs=case['transverse_detail']['runs']
table(r,'EBActualTransverseSchedule',['Run / shape','First (in)','Last (in)','Count','Status'],[
 [x['id']+' / '+('hoop' if x['kind']=='hoop' else 'open U'),f"{x['first_in']:g}",f"{x['end_in']:g}",str(round((x['end_in']-x['first_in'])/x['pitch_in'])+1),'Development pending' if x['kind']=='hoop' else 'PILE CLASH / development pending'] for x in runs
],[115,75,75,50,205],'input')
heading(r,'4. Recorded fitted bar coordinates')
para(r,'Source snapshot only: x is across the 42-in cap from the left section face; y is above the underside. Refit and regenerate these coordinates if geometry or steel changes. Family translations are 0.00374794 in; top bars lie at y = 32.1213 in. Fit does not close transverse U-bar clashes, anchorage or cutoff checks.')
table(r,'EBRecordedFitCoordinates',['Family','x coordinates (in)','y coordinates (in)'],[
 ['4 #6 top','5.01029, 15.6701, 26.3299, 36.9897','32.1213'],
 ['2 #8 bottom','5.01233, 36.9877','4.00375'],
 ['2 #5 additions','16.6062, 25.3938','3.81625'],
 ['7 #4 skin each side','3.75375 and 38.2463','7.51844, 11.0331, 14.5478, 18.0625, 21.5772, 25.0919, 28.6066'],
],[125,220,175])
heading(r,'5. End Bent 1 analysis snapshot')
table(r,'EBRecordedForces',['Action','Source value','Governing case'],[
 ['Negative strength moment magnitude','67.13 kip-ft','Strength III / C2 / member 38 J'],
 ['Positive at-pile moment','75.96 kip-ft','Strength I / C1 / member 29 interior'],
 ['Positive span/bearing moment','190.92 kip-ft','Strength I / C1 / member 32 J'],
 ['Global and low-zone shear magnitude','91.79 kip','Strength I / C1 / member 28 I; no low-shear zone established'],
 ['Torque magnitude','2.93 kip-ft','Strength III / C3 / member 17 I'],
 ['Service I N / P / B','45.82 / 57.50 / 146.82 kip-ft','Service I / C4'],
 ['Service III / fatigue','PENDING','Stored zero placeholders are not verified actions'],
],[180,145,195])
para(r,'Source check summary: largest available D/C = 0.966155 for B actual row spacing / shrinkage. This passing scalar ratio does not close the 48 pending/conditional checks. Axial force, weak-axis bending and lateral shear are outside the sectional calculation. End Bent 2 demands and model currency require separate verification.')
heading(r,'6. Quantities and unresolved coherence items')
table(r,'EBCurrentQuantities',['Item','Value','Scope'],[
 ['Gross cap concrete, one',f('BridgeGeometry_2Beam.EndBentCap_volume to ft^3'),'Rectangular cap only; no pile deduction'],
 ['Gross cap concrete, both',f('BridgeGeometry_2Beam.EndBentCaps_volume to ft^3'),'Backwalls, pedestals and cheek walls separate'],
 ['Estimated reinforcing, one','616.259 lb','Source drawn cage only; excludes laps, hoop closures, undrawn end anchorage and waste'],
 ['Estimated reinforcing, both','1232.518 lb','Twice the same current cage; planning estimate, not a fabrication schedule'],
],[160,120,240],'output')
table(r,'EBCoherenceRegister',['Item','Disposition'],[
 ['Cap and square pile layout','Shared dimensions and cap-only quantities aligned with the supplied report. Existing pier pipe-pile calculations remain pier-only.'],
 ['Bearing line and load moments','Live journal chain updates with 42-in width. Verify actual XML offsets and node mapping before model entry.'],
 ['Pedestal footprint','48-in retained longitudinal footprint exceeds the 42-in cap; revised footprint not supplied. Related pedestal dead weight remains provisional.'],
 ['Backwall quantity','Legacy combined cap/backwall allowance is superseded. Cap volume is separated; backwall volume is unresolved by this cap-only report.'],
 ['Actual cage','R2/R4/R6/R8 pile conflicts; development, cutoff, anchorage and closure checks remain open.'],
 ['Design completion','Service III, fatigue, code/exposure basis, force zones, D-regions and omitted force components remain open.'],
 ['Analysis provenance','Report snapshot has its own XML identity. Available same-named XML differs; no verified current model/input pair. End Bent 2 forces are not provided.'],
 ['Inherited journal issues','110 stored errors in FBMPMinTip and FeetintoDecimalFeet; three broken LoadCombinations reference links. Unchanged and outside this data update.'],
],[135,385])
append(F,r)

# Quantity rows retain their positions and interfaces. Obsolete combined quantity
# is replaced with the known cap-only scope, with explicit unresolved backwalls.
replace(Q,'End Bent Cap and Back Wall','End Bent Caps ONLY')
replace(Q,'<c formula="14.3592 ft^2"><num>14.3592 ft^2</num></c>', '<c formula="BridgeGeometry_2Beam.EndBentCap_area to ft^2" />')
replace(Q,'<c formula="C104*19\'3&quot;"><num>276.41459999999995 ft^3</num></c>', '<c formula="BridgeGeometry_2Beam.EndBentCap_volume to ft^3" valueformat="RoundedNumber(1, 3, {PriorityUnits: []})" />')
replace(Q,'<c formula="2*D104" background="#ABDB92"><num>552.8291999999999 ft^3</num></c>', '<c formula="BridgeGeometry_2Beam.EndBent_count*D104 to ft^3" background="#EFF7F1" />')
# Add a note in the existing empty row 108 without moving any cells.
row_pattern=re.compile(r'<row(?:\s[^>]*)?\s*/>|<row(?:\s[^>]*)?>.*?</row>',re.S)
matches=list(row_pattern.finditer(parts[Q]))
assert len(matches)==160
m=matches[107]
note='<row><textcell capture="False"><paragraph fontfamily="Times New Roman" fontsize="9">Backwalls excluded: final geometry pending. Old 14.3592-ft² × 19-ft-3-in combined allowance is superseded. Adjacent embedded sketches are historical reference.</paragraph></textcell></row>'
parts[Q]=parts[Q][:m.start()]+note+parts[Q][m.end():]
# The cap-only source also does not revise the legacy cheek-wall takeoff.
matches=list(row_pattern.finditer(parts[Q]))
m=matches[124]
assert re.fullmatch(r'<row\s*/>',m.group())
note='<row><textcell capture="False"><paragraph fontfamily="Times New Roman" fontsize="9">PROVISIONAL: legacy cheek-wall geometry; update with the end-bent detail.</paragraph></textcell></row>'
parts[Q]=parts[Q][:m.start()]+note+parts[Q][m.end():]
replace(Q,'6-in height; retained 4-ft length — verify final end-bent footprint.','PROVISIONAL: 48-in pedestal length exceeds 42-in cap. Revise footprint before final quantities.')

for key,title,text in [
 ('report:PileProperties','Pile section applicability','The pipe section formulas below apply to the pier’s 20-in pipe piles. Both end bents use the current 18-in square pile envelope recorded in Bridge Geometry. Do not apply these pipe thickness, steel area, stiffness or corrosion allowances to the end-bent piles; their material, reinforcement, section properties and foundation checks require the applicable pile design/model.'),
 ('report:FoundationModeling','End-bent model reconciliation','Both end bents use the shared square-pile geometry in Bridge Geometry. The p-multiplier discussion below remains for pier pipe piles. The End Bent 1 report confirms its recorded cap geometry but does not establish a current journal-to-analysis input pair. Verify the exact XML identity, bearing nodes, axes, eccentricities, pedestal/backwall dead loads and convergence before relying on transferred results.'),
 ]:
    e=section('EBApplicability20261008'); heading(e,title); para(e,text)
    link(e,'Current end-bent design and coherence record','#FBMPEndBent.EBCurrentDesignRecord')
    after_heading(key,e)

d=section('EndBentUpdate20261008'); heading(d,'2026-10-08 — current end-bent geometry and steel',0)
para(d,'User confirmed this configuration applies to both end bents. The 8 October End Bent 1 report supersedes the earlier 36-in-wide end-bent cap: 42-in width, 36-in depth and 17-ft-8-in length; four 18-in square piles at 54-in centers, with 25-in end-to-center distances. Pier geometry and historical decisions remain distinct.')
para(d,'Current entered cage: 4 #6 top, 2 #8 continuous bottom, 2 additional #5 hooked span bars, 7 #4 skin bars per side, and 19 closed #4 hoops plus 16 open-bottom #4 U-bars in the nine-run schedule. R2/R4/R6/R8 pile conflicts and source pending checks remain unresolved. This records the current arrangement; it is not an approved final cage.')
para(d,'Shared live cap quantities replace the obsolete combined end-bent cap/backwall allowance. Backwalls remain unresolved; the retained 48-in pedestal footprint also requires a revised detail. The live bearing offset changes with cap width. Source analysis is End Bent 1 only; the exact XML fingerprint, legacy node mapping and End Bent 2 demands require reconciliation.')
link(d,'Current design record and open items','#FBMPEndBent.EBCurrentDesignRecord'); append('report:DecisionLog',d)
replace('report:PedBridge','FBMP Entry - End Bent (12 / 19)','FBMP Entry - End Bent (legacy node map; review required)')
p=section('CurrentEndBentRecord'); heading(p,'Current end-bent data — 8 October 2026')
link(p,'Both end bents — cap and square pile geometry','#BridgeGeometry_2Beam.EndBentCurrentGeometry')
link(p,'Current steel configuration, End Bent 1 forces and coherence register','#FBMPEndBent.EBCurrentDesignRecord')
para(p,'Geometry and current cage are recorded for both end bents. Open design, pedestal/backwall and analysis-provenance items remain listed in the design record.',fontsize='10')
after_heading('report:PedBridge',p)

# Invalidate only displays downstream of the changed width or changed formulas.
# Native Blockpad will evaluate these; Python does not create native result caches.
changed={'EndBentCap_width','EB_CheckSpan'}
all_forms=[]
for key in (G,F):
    for e in E.fromstring(parts[key]).iter():
        if 'formula' in e.attrib:all_forms.append(e.get('formula'))
for _ in range(100):
    more=set(changed)
    for s in all_forms:
        m=re.match(r'^\s*(\w+)\s*=(?!=)',s)
        if m and any(re.search(r'(?<!\w)'+re.escape(n)+r'(?!\w)',s.split('=',1)[1]) for n in changed):more.add(m.group(1))
    if more==changed:break
    changed=more
cleared=[]
pattern=re.compile(r'<(?P<tag>dynexp|c|planecontainer)\b[^>]*\bformula="(?P<formula>[^"]*)"[^>]*(?<!/)>.*?</(?P=tag)>',re.S)
for key in (G,F):
    def clear(m):
        s=html.unescape(m.group('formula'))
        if not any(re.search(r'(?<!\w)'+re.escape(n)+r'(?!\w)',s) for n in changed):return m.group()
        cleaned=re.sub(r'<(expresult|expstep|num|textvalue|bool)\b[^>]*>.*?</\1>','',m.group(),flags=re.S)
        if cleaned!=m.group():cleared.append({'component':key,'formula':s})
        return cleaned
    parts[key]=pattern.sub(clear,parts[key])
for key,data in parts.items():
    E.fromstring(data)
    (TASK/'components'/mapping[key]).write_bytes(data.encode('utf8'))
(TASK/'working.bpad').write_bytes(base.replace({k:v.encode('utf8') for k,v in parts.items()}))
(TASK/'changes.json').write_text(json.dumps({'replacements':change_log,'invalidated_cached_expressions':cleared,'changed_width_dependency_names':sorted(changed)},indent=2,ensure_ascii=False),encoding='utf8')
print(json.dumps({'components':list(parts),'cached_expressions_invalidated':len(cleared),'source_report_sha256':EXPECTED},indent=2))
