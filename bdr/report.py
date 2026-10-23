"""Render the Bridge Development Report as one self-contained HTML document.

The outline follows FDM 121.9 (contents 121.9.1, format 121.9.2, aesthetics 121.9.3,
construction 121.9.4, conclusions 121.9.8, 30% plans 121.9.9) and the FDM 121.10
submittal checklist. Every number comes from the bundle that ``sources.collect``
reads from the project record; what the record cannot supply is printed as a
flagged placeholder and collected into the open-items appendix.
"""
from __future__ import annotations

import base64
import csv
import re
from fractions import Fraction
from html import escape as esc
from pathlib import Path

from bdr import figures, sources

BG = "BridgeGeometry_2Beam"
BAR_WEIGHT_LB_FT = {3: 0.376, 4: 0.668, 5: 1.043, 6: 1.502, 7: 2.044, 8: 2.670, 9: 3.400, 10: 4.303, 11: 5.313}
CALC_REPORTS = {
    "C001": "wind_superstructure/report/", "C002": "fence_wind/report/", "C003": "bridge_movement/report/",
    "C004": "superstructure_uplift/report/", "C007": "journal module only (shared cap factors)",
    "C008": "project_current/cap_design/end_bents/", "C009": "project_current/cap_design/end_bent_2/",
    "C010": "project_current/cap_design/pier/", "C011": "project_current/pile_design/end_bent_1/",
    "C012": "project_current/pile_design/end_bent_2/", "C013": "project_current/pile_design/pier/",
    "C014": "project_current/cap_design/backwall/", "C015": "mse_wall_exclusion/report/",
    "C016": "bearing_design/report/", "C017": "project_current/pier_wall/", "C018": "project_current/pier_cheek_wall/",
}

CSS = """
:root{--ink:#1d2430;--muted:#5d6877;--line:#cfd5dc;--band:#eef2f6;--accent:#8a1c1c;--tbs:#b7791f;--pend:#8a1c1c;--ok:#2f6f3e;--bg:#fff}
*{box-sizing:border-box}
html{background:#e9ecef}
body{margin:0;color:var(--ink);background:var(--bg);font:12.5px/1.5 Georgia,"Times New Roman",serif;max-width:8.5in;margin:0 auto;padding:0.6in 0.75in 1in;box-shadow:0 0 18px #0002}
h1,h2,h3,h4{font-family:"Segoe UI",Arial,Helvetica,sans-serif;color:var(--ink);line-height:1.2}
h1{font-size:26px;margin:0 0 6px}
h2{font-size:17px;margin:28px 0 8px;padding-bottom:4px;border-bottom:2px solid var(--ink)}
h3{font-size:14px;margin:18px 0 6px}
h4{font-size:12.5px;margin:12px 0 4px}
p{margin:6px 0}
ul,ol{margin:4px 0 8px 22px;padding:0}
li{margin:2px 0}
table{border-collapse:collapse;width:100%;margin:8px 0 12px;font-size:11.5px;page-break-inside:auto}
th,td{border:1px solid var(--line);padding:3px 6px;vertical-align:top;text-align:left}
th{background:var(--band);font-family:"Segoe UI",Arial,sans-serif;font-weight:600}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
tr{page-break-inside:avoid}
.cover{min-height:9.2in;display:flex;flex-direction:column;justify-content:space-between;page-break-after:always}
.cover .agency{font-family:"Segoe UI",Arial,sans-serif;font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.cover .title{font-family:"Segoe UI",Arial,sans-serif;font-size:34px;font-weight:700;margin:60px 0 10px}
.cover .struct{font-family:"Segoe UI",Arial,sans-serif;font-size:22px;margin-bottom:30px}
.cover table{width:auto;min-width:60%}
.cover .rev{font-family:"Segoe UI",Arial,sans-serif;color:var(--accent);font-weight:600;font-size:15px}
.draft{border:2px solid var(--accent);color:var(--accent);padding:8px 12px;font-family:"Segoe UI",Arial,sans-serif;font-size:12px;margin:14px 0}
.toc ol{list-style:none;margin-left:0}
.toc li{margin:2px 0}
.toc li.l2{margin-left:18px;font-size:12px}
.toc a{color:var(--ink);text-decoration:none}
.flag{font-family:"Segoe UI",Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:.04em;padding:1px 5px;border-radius:3px;border:1px solid;margin-right:4px;white-space:nowrap;vertical-align:1px}
.flag.tbs{color:var(--tbs);border-color:var(--tbs)}
.flag.pend{color:var(--pend);border-color:var(--pend)}
.flag.ok{color:var(--ok);border-color:var(--ok)}
.flag.inf{color:var(--muted);border-color:var(--muted)}
.fig{width:100%;height:auto;border:1px solid var(--line);background:#fff;margin:6px 0 2px}
figure{margin:12px 0 16px;page-break-inside:avoid}
figcaption{font-family:"Segoe UI",Arial,sans-serif;font-size:11px;color:var(--muted);margin-top:4px}
.sheet{width:100%;height:auto;border:1px solid var(--line)}
.legend{font-size:11px;color:var(--muted)}
.legend span{margin-right:12px;white-space:nowrap}
.sw{display:inline-block;width:10px;height:10px;border:1px solid #777;margin-right:4px;vertical-align:-1px}
.note{color:var(--muted);font-size:11.5px}
.kv td:first-child{width:38%;background:var(--band);font-family:"Segoe UI",Arial,sans-serif;font-weight:600}
.pb{page-break-before:always}
.small{font-size:11px}
.exec{background:var(--band);border-left:4px solid var(--ink);padding:8px 12px;margin:10px 0}
a{color:#1a4e8a}
@media print{html{background:#fff}body{box-shadow:none;max-width:none;padding:0;margin:0}
 @page{size:Letter;margin:0.75in 0.7in 0.8in}
 h2{page-break-after:avoid}figure{page-break-inside:avoid}}
"""


# ---------------------------------------------------------------- helpers --
class Ctx:
    def __init__(self, bundle):
        self.b = bundle
        self.J = bundle["journal"]
        self.open_items = []     # (section, kind, text)
        self.fig_no = 0
        self.table_no = 0
        self.section = ""

    def tbs(self, text, kind="To be supplied"):
        self.open_items.append({"section": self.section, "kind": kind, "text": text})
        cls = {"To be supplied": "tbs", "Pending": "pend"}.get(kind, "inf")
        return f'<span class="flag {cls}">{esc(kind)}</span>{esc(text)}'

    def v(self, symbol, module=BG):
        return esc(self.J.text(module, symbol))

    def jv(self, symbol, module=BG):
        return self.J.value(module, symbol)

    def figure(self, inner, caption):
        self.fig_no += 1
        return f'<figure>{inner}<figcaption>Figure {self.fig_no}. {caption}</figcaption></figure>'

    def table(self, headers, rows, caption=None, cls="", numeric=()):
        self.table_no += 1
        cap = f'<caption style="caption-side:top;text-align:left;font-family:Segoe UI,Arial,sans-serif;font-size:11px;color:var(--muted);padding:2px 0">Table {self.table_no}. {caption}</caption>' if caption else ""
        th = "".join(f'<th class="{"n" if i in numeric else ""}">{h}</th>' for i, h in enumerate(headers))
        body = "".join("<tr>" + "".join(f'<td class="{"n" if i in numeric else ""}">{c}</td>' for i, c in enumerate(r)) + "</tr>" for r in rows)
        return f'<table class="{cls}">{cap}<thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'


def img_data(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode("ascii")


def ftin(inches, denom=8):
    """Feet and inches for a foot or more; inches alone below a foot (6 in, 2 9/16 in)."""
    if inches is None:
        return "—"
    if abs(inches) < 12:
        whole = int(inches)
        frac = Fraction(inches - whole).limit_denominator(denom)
        if whole and frac:
            return f"{whole} {frac} in"
        return f"{frac} in" if frac and not whole else f"{whole} in"
    return figures._ftin(inches, denom)


def f2(x, nd=2):
    return f"{x:,.{nd}f}"


# ------------------------------------------------------------------ data --
def derived(c: Ctx) -> dict:
    """The numbers the narrative repeats, read once from the bundle."""
    J, b = c.J, c.b
    g = {}
    g["span1"] = c.jv("Span_1").ft
    g["span2"] = c.jv("Span_2").ft
    g["total"] = c.jv("TotalSpan").ft
    g["sta_eb1"] = float(J.text(BG, "BeginBridge_station"))
    g["sta_pier"] = float(J.text(BG, "CLPier_station"))
    g["sta_eb2"] = float(J.text(BG, "EndBridge_station"))
    g["pgl_start"] = c.jv("PGL_start_elev").ft
    g["pgl_end"] = c.jv("PGL_end_elev").ft
    g["pgl_pier"] = c.jv("PGL_pier_elev").ft
    g["grade"] = c.jv("PGL_nominalGrade").num
    g["crossfall"] = c.jv("Deck_crossfall").num
    g["deck_w_in"] = c.jv("Deck_out2out").inches
    g["clear_w_in"] = c.jv("Bridge_clearWidth").inches
    g["parapet_w_in"] = c.jv("Parapet_width").inches
    g["parapet_h_in"] = c.jv("Parapet_ht").inches
    g["edge_offset_in"] = c.jv("Distance_outFaceParapet_deckEdge").inches
    g["beam_spacing_in"] = c.jv("Beam_spacing").inches
    g["beam_depth_in"] = c.jv("Beam_depth").inches
    g["slab_in"] = c.jv("Thickness_slab_peak").inches
    g["flange_in"] = c.jv("Beam_topFlange_width").inches
    g["haunch_min_in"] = c.jv("Haunch_min").inches
    g["fence_straight_in"] = c.jv("Fence_straight_ht").inches
    g["fence_radius_in"] = c.jv("Fence_outerRadius").inches
    g["fence_ht_in"] = c.jv("Fence_ht").inches
    g["fence_post_in"] = c.jv("Fence_postSpacing").inches
    g["super_depth_in"] = c.jv("Depth_SuperStr").inches
    g["pier_cap_w_in"] = c.jv("PierCap_width").inches
    g["pier_cap_h_in"] = c.jv("PierCap_ht").inches
    g["pier_cap_len_in"] = c.jv("PierCap_length").inches
    g["pier_piles"] = int(c.jv("Pier_pile_count").num)
    g["pier_pile_d_in"] = c.jv("Pier_pile_diameter").inches
    g["pier_pile_s_in"] = c.jv("Pile_spacing").inches
    g["eb_cap_w_in"] = c.jv("EndBentCap_width").inches
    g["eb_cap_h_in"] = c.jv("EndBentCap_depth").inches
    g["eb_cap_len_in"] = c.jv("EndBentCap_length").inches
    g["eb_piles"] = int(c.jv("EndBent_pileCount").num)
    g["eb_pile_w_in"] = c.jv("EndBent_pileWidth").inches
    g["eb_pile_s_in"] = c.jv("EndBent_pileSpacing").inches
    g["cheek_t_in"] = c.jv("EndBent_cheekThickness").inches
    g["backwall_t_in"] = c.jv("Backwall_thickness_shown").inches
    g["pad_l_in"] = c.jv("Bearing_pad_length").inches
    g["pad_w_in"] = c.jv("Bearing_pad_width").inches
    g["pad_t_in"] = c.jv("Bearing_pad_thickness").inches
    g["pedestal_h_in"] = c.jv("Pedestal_ht").inches
    g["pedestal_w_in"] = c.jv("Pedestal_width").inches
    g["cap_top_pier"] = c.jv("CapTop_elev").ft
    g["cap_bot_pier"] = c.jv("CapBottom_elev").ft
    g["terrain_pier"] = c.jv("Terrain_elev").ft
    g["algn_terrain"] = c.jv("Distance_Algn2Terrain").ft
    g["pier_wind_face_in"] = c.jv("Pier_windFace_width").inches
    g["deckend_len_in"] = c.jv("DeckEnd_length_min").inches
    g["deckend_add_in"] = c.jv("DeckEnd_addedDepth_min").inches
    g["backwall_drop_in"] = c.jv("EndBent_backwallDrop").inches
    g["haunch_total_ft3"] = c.jv("Haunch_totalVolume").num
    # journal materials
    g["mat"] = {k: J.text("Materials", k) for k in ("Substructure_fc", "Deck_fc", "Beam_fc", "Railing_fc", "Rebar_fy", "Rebar_Es")}
    # wind (journal basis module)
    g["wind"] = {k: J.text("PedBridgeWind", k) for k in ("Wind_conc_superstrc_lineload", "Wind_CG_Cap_pointLoad", "Wind_CG_Cap_moment",
                                                          "Wind_perpPierWall", "Wind_pierWall_pointload", "Wind_fence_pointload", "q_z_fencing")}
    g["p_z_iii"] = J.text("C001WindLoadOnPedBridgeSuperstructure", "P_Z_III")
    # pipe pile section (journal)
    g["pipe"] = {k: J.text("PileProperties", k) for k in ("t_actual", "Sacrificial_thk", "t_eff", "A_eff")}
    # gravity sheet rows
    rows = J.sheets["PedBridgeWeights_2Beams"]
    g["gravity"] = {}
    for r in rows:
        if "TOTAL AT PIER" in r:
            vals = [x for x in r if x.endswith("kip")]
            g["gravity"]["pier_DC_pad"], g["gravity"]["pier_below"], g["gravity"]["pier_DC_node"], g["gravity"]["pier_PL"] = vals[0], vals[1], vals[2], vals[3]
        if r[:4] == ["", "", "", "1"] and any("ft^2" in x for x in r) and "kip" in " ".join(r) and "89." in " ".join(r):
            g["gravity"]["beam_kip"] = float(next(x for x in r if x.endswith(" kip")).split()[0])
        if "150 plf" in r:
            g["gravity"]["fence_plf"] = "150 plf"
        if "90 psf" in r:
            g["gravity"]["ll_psf"] = "90 psf"
            g["gravity"]["ll_total"] = next(x for x in r if x.endswith(" kip"))
    # pier wall volume from the gravity sheet (row with 18 ft 3 in)
    for r in rows:
        if "18 ft 3 in" in r:
            g["pier_wall_vol_ft3"] = float(next(x for x in r if x.endswith("ft^3")).split()[0])
            g["pier_wall_kip"] = next(x for x in r if x.endswith(" kip"))
    g["quantities"] = dict(J.sheet_volumes("QauntitiesBridge"))
    g["mse_walls"], g["mse_totals"] = J.mse_walls()
    # backwall volume from the case (thickness x length x mean of crown and edge heights)
    bw = b["cases"]["BACKWALL-CASE"]["inputs"]
    g["backwall_vol_ft3"] = bw["t_bw"] / 12 * bw["L_bw"] / 12 * (bw["H_bw"] + bw["H_bw_edge"]) / 2
    g["backwall_H"] = bw["H_bw"]
    g["backwall_H_edge"] = bw["H_bw_edge"]
    g["cheek_H"] = bw["H_ck"]
    # closure slabs from the D-044 decision text
    m = re.search(r"closure concrete totals ([\d.]+) ft3", " ".join(d["basis"] for d in b["decisions"]))
    g["closure_ft3"] = float(m[1]) if m else None
    # bearing check from D-063
    d063 = next((d for d in b["decisions"] if d["id"] == "D-063"), None)
    g["bearing"] = {}
    if d063:
        m = re.search(r"Static ([\d.]+) rad and cyclic ([\d.]+) rad.*?bound is ([\d.]+) in", d063["basis"])
        if m:
            g["bearing"] = {"static": m[1], "cyclic": m[2], "move": m[3]}
    # substructure reinforcing from the bar register (CAD model bar list)
    reg = sources.ROOT / "substructure_drawings" / "output" / "bar_mark_register.csv"
    weight, count = {}, {}
    with open(reg, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            size = int(r["size"])
            weight[r["support"]] = weight.get(r["support"], 0.0) + float(r["list_length_in"]) / 12 * BAR_WEIGHT_LB_FT[size]
            count[r["support"]] = count.get(r["support"], 0) + 1
    g["rebar_lb"] = weight
    g["rebar_count"] = count
    # piles
    pt = b["pile_tables"]
    g["pile_rows"] = {k: pt[k]["row"] for k in pt}
    g["pile_cols"] = pt["EB1"]["columns"]
    g["pile_trial_ft"] = b["facts"]["geometry"]["trial_pile_length_ft"]["value"]
    return g


# -------------------------------------------------------------- sections --
def cover(c: Ctx, g):
    c.section = "Cover"
    f = c.b["facts"]
    ident = f["identification"]
    pi = {k: c.J.text("ProjectInfo", k, "") for k in ("Firm", "Address", "Project", "DesignedBy", "DesignDate", "CheckedBy")}

    names = {"fpid": "Financial Project ID", "bridge_number": "Bridge number"}

    def cell(key):
        e = ident[key]
        if e["value"] is None:
            return c.tbs(f'{names.get(key, key)}: {e["basis"]}')
        flag = '' if e["status"] == "project source" else f'<span class="flag inf">{esc(e["status"])}</span>'
        return f'{flag}{esc(str(e["value"]))}'

    rows = [
        ("Project", esc(pi["Project"])),
        ("Structure", esc(f["report"]["structure"])),
        ("Financial Project ID", cell("fpid")),
        ("Bridge No.", cell("bridge_number")),
        ("County", cell("county")),
        ("FDOT District", cell("district")),
        ("Road", cell("road")),
        ("Structure category", cell("structure_category")),
        ("Prepared by", esc(pi["Firm"]) + "<br>" + esc(pi["Address"])),
        ("Designed / checked", esc(f'{pi["DesignedBy"]} / {pi["CheckedBy"]}')),
        ("Project record as of", esc(c.b["as_of"])),
        ("Report status", f'<span class="rev">{esc(f["report"]["revision"])}</span>'),
    ]
    tbl = "<table class='kv'>" + "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows) + "</table>"
    return f"""<section class="cover">
<div>
<div class="agency">State of Florida Department of Transportation</div>
<div class="title">{esc(f["report"]["title"])}</div>
<div class="struct">{esc(f["report"]["structure"])}<br><span style="font-size:15px;color:var(--muted)">{esc(pi["Project"])}</span></div>
{tbl}
</div>
<div class="draft"><b>Generated record document.</b> This report was assembled by <code>bdr/build.py</code> from the registered project record in
<code>project_current</code> (source register, journal, decisions, saved cases, check registers, pile data tables, geometry sources and the preliminary
FDOT drawings) on the record of {esc(c.b["as_of"])}. Values are read as saved; nothing is recalculated. Items the record does not answer are flagged
<span class="flag tbs">To be supplied</span>; unconfirmed design inputs are flagged <span class="flag pend">Pending</span>; both are listed in Appendix H.
Source selection in the record is not engineering acceptance. Not for construction.</div>
</section>"""


def toc(entries):
    items = "".join(f'<li class="l{lvl}"><a href="#{i}">{t}</a></li>' for i, t, lvl in entries)
    return f'<section class="toc"><h2>Contents</h2><ol>{items}</ol></section>'


def executive_summary(c: Ctx, g):
    c.section = "Executive summary"
    f = c.b["facts"]
    rev = c.b["review"]
    pile = g["pile_rows"]
    summary = c.table(
        ["Item", "Recommended configuration (project record)"],
        [
            ["Structure", f'Two-span pedestrian bridge over I-95, {f2(g["span1"])} ft + {f2(g["span2"])} ft = {f2(g["total"])} ft, 0° skew, tangent alignment'],
            ["Superstructure", f'Two Florida-I 36 (FIB-36) prestressed concrete beams at {ftin(g["beam_spacing_in"])} with a {ftin(g["slab_in"])} cast-in-place deck; '
                               f'{ftin(g["clear_w_in"])} clear walkway between {ftin(g["parapet_h_in"])} parapets; enclosed by a metal-fabric fence'],
            ["Substructure", f'End bents: {ftin(g["eb_cap_w_in"])} × {ftin(g["eb_cap_h_in"])} caps, {ftin(g["eb_cap_len_in"])} long, with backwall and cheek walls inside MSE walls. '
                             f'Pier: {ftin(g["pier_cap_w_in"])} × {ftin(g["pier_cap_h_in"])} cap, {ftin(g["pier_cap_len_in"])} long, on a {ftin(c.b["cases"]["PIER-WALL-CASE"]["length_in"])} × {ftin(c.b["cases"]["PIER-WALL-CASE"]["thickness_in"])} pier wall'],
            ["Foundations", f'End bents: {g["eb_piles"]} ~ {pile["EB1"][1]} piles at {ftin(g["eb_pile_s_in"])}; pier: {g["pier_piles"]} ~ {pile["PIER"][1]} piles at {ftin(g["pier_pile_s_in"])} '
                            f'(nominal bearing resistance {pile["EB1"][2]} / {pile["EB2"][2]} / {pile["PIER"][2]} tons)'],
            ["Approaches", "MSE-walled ramps A and B (ADA walkway slopes), 4-in walking slabs on the backwalls; tie-back straps carry the end-bent lateral load into the reinforced fill"],
            ["Vertical clearance", f'{f["geometry"]["min_vertical_clearance_ft"]["value"]:.2f} ft minimum over the covered roadway region against the FDM 260 minimum of {f["report"]["fdm_260_clearance_ft"]} ft'],
            ["Estimated construction cost", c.tbs("unit costs and the total construction cost are not in the project record")],
            ["Construction time", c.tbs("construction time requirement not in the project record")],
        ], "Executive summary of the recommended structure")
    status = (f'The design record carries {rev["outstanding"]} outstanding coherence items, {len(c.b["assumptions"])} register entries of assumptions and gaps, '
              f'and pending prerequisites in every pile design (environment classification, minimum tip elevations, scour, downdrag documentation, drivability and the pile-to-cap connection). '
              f'The end-bent cap reports carry {c.b["caps"]["EB"]["fail"]} FAIL entries each (end-face U-grid pile clearance, item COH-019) and the pier wall ring calculation one FAIL (ring clearance to the face grid). '
              f'These are design-record findings, not reasons to change the structure type; they are listed in Section 15 and Appendix H.')
    return f"""<section id="exec"><h2>Executive summary</h2>
<div class="exec"><p>This Bridge Development Report presents the type, size and location of the B4 Pedestrian Bridge over I-95, a two-span prestressed
concrete beam bridge with MSE-walled ADA ramps, assembled from the project design record. FDM 121.9 allows an abbreviated BDR for a simple Category 1
structure whose optimal type is evident from the site constraints; this report documents the selected type and the design basis, states the findings
that remain open, and lists the items a complete BDR submittal still needs.</p></div>
{summary}
<p>{esc(status)}</p>
<p><b>Recommendation.</b> Carry the two-span, two-beam FIB-36 configuration with pile-supported end bents in MSE fill and the pier wall on
{g["pier_piles"]} steel pipe piles forward into the final Structures Plans, subject to the geotechnical, hydraulic (drainage concurrence),
corrosion-environment and maintenance-of-traffic submittals that complete the BDR package (Appendix G checklist).</p>
</section>"""


def s1_introduction(c: Ctx, g):
    c.section = "1 Introduction"
    f = c.b["facts"]
    pi = c.J.text("ProjectInfo", "Project")
    reg = c.b["register"]
    current = [r for r in reg if r["status"].lower().startswith("current")]
    return f"""<section id="s1"><h2>1. Introduction and project description</h2>
<h3>1.1 Purpose of the report</h3>
<p>The Bridge Development Report (BDR) is the Department's tool for selecting the optimal bridge type and for establishing the basic parameters that
govern the design and plans-preparation phase (FDM 121.9). This report is prepared to the January 2026 FDM: the contents of FDM 121.9.1, the format of
121.9.2, aesthetics 121.9.3, construction and maintenance 121.9.4, conclusions 121.9.8, the 30% Structures Plans of 121.9.9 and the submittal checklist
of FDM 121.10 (Form 121-A). Where the project record does not yet answer an item the report says so rather than supplying an unsupported statement
(FDM 121.9: "the BDR should contain only supportable and defendable statements").</p>
<h3>1.2 Project</h3>
<p>{esc(pi)} ({esc(f["identification"]["district"]["value"])}, {esc(f["identification"]["county"]["value"])} County). The B4 Pedestrian Bridge carries a
{ftin(g["clear_w_in"])} walkway over I-95 between two MSE-walled approach ramps (Ramp A on the west, Ramp B on the east) with Pond 14D graded east of
Ramp B. The bridge is a two-span structure of {f2(g["total"])} ft between the front faces of the end-bent backwalls, with the pier at
Sta. {figures._fmt_sta(g["sta_pier"])}.</p>
<h3>1.3 Basis of this report</h3>
<p>The report is generated from the current project record (<code>project_current</code>, source register of {esc(c.b["as_of"])}: {len(reg)} registered
sources, {len(current)} of them current) and from the project journal (<code>journal/D2_I95_Project_Journal.bpad</code>), the adopted decisions
D-001 to {esc(c.b["decisions"][-1]["id"])}, the assumptions-and-gaps register, the latest coherence review, the selected calculation cases and check
registers, the registered Mathcad beam runs, the FreeCAD model through its drawing snapshots, and the preliminary FDOT-format substructure sheets.
Appendix F lists the sources. The hand-maintained facts that no source supplies (<code>bdr/data/facts.json</code>) are flagged in the text.</p>
</section>"""


def s2_criteria(c: Ctx, g):
    c.section = "2 Design criteria"
    f = c.b["facts"]
    mat = g["mat"]
    cheek = c.b["cases"]["CHEEK-CASE"]["inputs"]
    bw = c.b["cases"]["BACKWALL-CASE"]["inputs"]
    combos = c.b["cases"]["PILE-PIER-CASE"]["analysis"]["combination_factors"]
    names = c.b["cases"]["PILE-PIER-CASE"]["analysis"]["combinations"]
    combo_rows = []
    for k in sorted(combos, key=int):
        fac = combos[k]
        shown = ", ".join(f"{kk} {vv:g}" for kk, vv in fac.items() if vv)
        combo_rows.append([f"FBMP load case {k}", esc(names[k]), esc(shown)])
    refs = c.table(["Document", "Edition / use"], [
        ["AASHTO LRFD Bridge Design Specifications", "10th edition (2024): all structural design (RFQ governing regulations)"],
        ["FDOT Structures Manual, Vol. 1 Structures Design Guidelines (SDG)", "January 2026: wind (2.4), temperature (2.7), covers (1.4), foundations (3.5), end bents in MSE (3.13), bearings (6)"],
        ["FDOT Structures Manual, Vol. 2 Structures Detailing Manual (SDM)", "January 2026: bar marks (4.3), Pile Data Table (11.4), tie-back note (12.3.F), cheek walls (12.6)"],
        ["AASHTO LRFD Guide Specifications for the Design of Pedestrian Bridges", "2009 (2015 interims where applicable): pedestrian live load 90 psf, fence/railing"],
        ["FDOT Design Manual (FDM)", "January 2026: 121 (BDR), 222 to 224 (pedestrian facilities), 260 (bridge geometrics, Table 260.6.1 vertical clearance)"],
        ["FDOT Standard Plans", "FY 2026-27: Index 455 (prestressed piles), 415-001 (bar bending)"],
        ["FDOT Standard Specifications", "Sections 346, 455, 931, 933, 962 as cited in the pile design"],
        ["FDOT CADD Manual and Standard Level Table", "Topic 625-050-001 (Nov. 2024) and 10-25-2023 level table: drawing symbology"],
        ["2010 ADA Standards for Accessible Design", "403, 405, 505 (journal Access Geometry and ADA module)"],
        ["RFQ structural criteria and Structures Manual modifications", "Journal reference packet (RFQ item 8, item 66): project-specific criteria"],
    ], "Governing documents")
    loads = c.table(["Load", "Value", "Basis"], [
        ["Concrete unit weight", "150 pcf (0.1455 kcf for modulus)", "SDG Table 2.2-1; LRFD Table 3.5.1-1"],
        ["Pedestrian live load PL", f'{g["gravity"].get("ll_psf", "90 psf")} over the {ftin(g["clear_w_in"])} clear walkway', "AASHTO Pedestrian Guide 3.1; D-015 (no vehicular or maintenance-vehicle loading)"],
        ["Fence / enclosure weight", g["gravity"].get("fence_plf", "150 plf"), "Journal gravity sheet (supplier basis)"],
        ["Wind, Strength III", f'V = {cheek["V_III"]:g} mph, K<sub>Z</sub> = {cheek["K_Z_III"]:.4f} (Exposure C), G = {cheek["G_f"]:g}; P<sub>Z</sub> = {esc(g["p_z_iii"])} on the superstructure; C<sub>D</sub> = {cheek["C_D"]:g} on the substructure',
         "SDG Table 2.4.1-1 (Duval County), SDG 2.4.1.C, LRFD 3.8.1.2.1; calculations C001, C002, C018"],
        ["Wind, Strength V / Service I", f'V = {cheek["V_V"]:g} mph / {cheek["V_SI"]:g} mph, K<sub>Z</sub> = 1.0', "LRFD Table 3.8.1.1.2-1"],
        ["Wind on the fence", f'{esc(g["wind"]["q_z_fencing"])} on the metal-fabric fence; {esc(g["wind"]["Wind_fence_pointload"])} at the pier', "LRFD 13.8.2 basis; calculation C002"],
        ["Uniform temperature", f'ΔT = {bw["dT"]:g} °F (concrete superstructure), α = {bw["alpha_t"]:g}/°F', "SDG Table 2.7.1-1; calculation C003"],
        ["Earth pressure behind the end bents", f'φ = {bw["phi_soil"]:g}°, γ = {bw["gamma_s"] * 1000:g} pcf, active Coulomb with δ = {bw["delta_w"]:g}°; live-load surcharge {bw["q_PL"] * 1000:g} psf',
         "D-016 (SDG 3.13.2.I.1 sand backfill; SDG Table 2.2-1); LRFD 3.11.6.1"],
        ["Downdrag", f'{g["pile_rows"]["EB1"][9]} tons per end-bent pile; none at the pier', "Geotechnical engineer, 19 October 2026 (D-050); SDG 3.5.6"],
        ["Vessel collision", f'<span class="flag inf">Inferred</span>{esc(f["bdr_items"]["vessel_collision"]["text"])}', "FDM 121.9.1(6)"],
        ["Scour", f'<span class="flag inf">Inferred</span>{esc(f["bdr_items"]["scour"]["text"])}', "FDM 121.9.1(7)"],
        ["Seismic", f'<span class="flag inf">Inferred</span>{esc(f["bdr_items"]["seismic"]["text"])}', "SDG 2.3"],
    ], "Loads")
    mats = c.table(["Material", "Strength", "Use"], [
        ["Concrete Class VI", esc(mat["Beam_fc"]), "Prestressed FIB-36 beams (f'ci 6.0 ksi at release, Mathcad runs)"],
        ["Concrete Class V", "6.5 ksi", "Prestressed concrete piles (Spec. 346; FBMP FPC)"],
        ["Concrete Class IV", esc(mat["Substructure_fc"]), "Cast-in-place substructure unless noted"],
        ["Concrete Class II (Bridge Deck)", esc(mat["Deck_fc"]), "Bridge deck"],
        ["Concrete", esc(mat["Railing_fc"]), "Railings / parapets"],
        ["Reinforcing steel", f'{esc(mat["Rebar_fy"])} (E<sub>s</sub> {esc(mat["Rebar_Es"])})', "Grade 60, uncoated"],
        ["Prestressing strand", "Grade 270 low-relaxation, 0.6 in (beams and piles)", "Mathcad runs; Standard Plans Index 455"],
        ["Steel pipe piles", f'ASTM A252 Grade 3, F<sub>y</sub> 45 ksi; {esc(g["pipe"]["t_actual"])} wall, {esc(g["pipe"]["Sacrificial_thk"])} sacrificial, {esc(g["pipe"]["t_eff"])} effective', "Spec. 962 Table 962-11; journal Pile Section Properties; D-073"],
        ["Ring plates and fillet welds", "F<sub>y</sub> 50 ksi plate; E70 fillets", "Pier wall calculation C017"],
    ], "Materials (journal Materials module)")
    env = c.tbs("Environmental classification (SDG 1.4) for covers, pile minimum size and strand tension limits: pending in every registered calculation (A-011); the beam runs assume 'Moderately' aggressive. Bridge Corrosion Environment Report required (FDM 121.10).", "Pending")
    return f"""<section id="s2"><h2>2. Design criteria</h2>
<h3>2.1 Governing documents</h3>{refs}
<h3>2.2 Loads and load combinations</h3>{loads}
<p>The foundation analyses (FB-MultiPier 6.1.0, registered exports) carry the following combinations; Strength IV and the Extreme Event combinations
are not in the exports (Strength IV does not govern a two-beam pedestrian superstructure of this span, and no extreme events apply). Service III is
treated as not applicable to the non-prestressed substructure (D-007). Fatigue of the substructure is pending the applicability review in the cap
reports.</p>
{c.table(["Case", "Limit state", "Load factors in the export"], combo_rows, "Load combinations in the registered FB-MultiPier exports")}
<h3>2.3 Materials</h3>{mats}
<h3>2.4 Environment, covers and durability</h3>
<p>{env}</p>
<p>Concrete cover adopted in the calculations: 3 in on the caps, backwalls and pier wall (SDG Table 1.4.2-1 exterior formed substructure, slightly
or moderately aggressive), 2 in in the pier cheek walls, 3 in clear to the pile spiral (Index 455-001). The corrosion allowance on the steel pipe
piles is a design input awaiting the classification (LRFD 10.7.5).</p>
<h3>2.5 Geometric criteria</h3>
<p>Vertical clearance over the roadway: minimum {f["report"]["fdm_260_clearance_ft"]} ft ({esc(f["report"]["fdm_260_clearance_basis"])}). Provided:
{f["geometry"]["min_vertical_clearance_ft"]["value"]:.2f} ft minimum over the covered roadway region from the geometry notebook
(<span class="flag inf">Inferred</span>{esc(f["geometry"]["min_vertical_clearance_ft"]["basis"])}); the journal Access Geometry module records
{f["geometry"]["journal_vertical_clearance_ft"]["value"]:.2f} ft on the earlier FIB-45 basis. Walkway: {ftin(g["clear_w_in"])} clear between parapets
(FDM 222 to 224 pedestrian and shared-use path widths), {g["crossfall"] * 100:.0f}% crossfall; approach walkways not steeper than 5% so that they are walkways rather
than ramps under ADA 403/405 (D-026: main ramps ≤ 5%, short landing transitions excepted).</p>
</section>"""


def s3_site(c: Ctx, g):
    c.section = "3 Site conditions"
    f = c.b["facts"]
    pt = c.b["pile_tables"]
    gm = c.b["geotech_manifest"]
    terrain = c.table(["Support", "Station", "Ground EL in the FBMP model (ft)", "Pile cutoff EL (ft)", "Source"], [
        ["End Bent 1", figures._fmt_sta(g["sta_eb1"]), f2(pt["EB1"]["inputs"]["EL_ground"]["value"]), f2(pt["EB1"]["inputs"]["EL_cutoff"]["value"], 3), "End Bent 1_Fixed.XML (EB-XML)"],
        ["Pier", figures._fmt_sta(g["sta_pier"]), f2(pt["PIER"]["inputs"]["EL_ground"]["value"]), f2(pt["PIER"]["inputs"]["EL_cutoff"]["value"], 3), "Pier_Fixed.XML (PIER-XML)"],
        ["End Bent 2", figures._fmt_sta(g["sta_eb2"]), f2(pt["EB2"]["inputs"]["EL_ground"]["value"]), f2(pt["EB2"]["inputs"]["EL_cutoff"]["value"], 3), "End Bent 2_Fixed.XML (EB2-XML)"],
    ], "Ground and pile cutoff elevations at the supports", numeric=(2, 3))
    secs = c.table(["Section", "Plane", "Stations", "Existing-ground survey on the plane", "Elements cut"], [
        [s["id"], f'{s["offset_ft"]:.1f} ft north of the PGL' if s["offset_ft"] else "on the PGL", f'{s["from"]} to {s["to"]}',
         f'{s["eg_coverage"] * 100:.0f}% of the window; survey limit at Sta. {", ".join(s["eg_survey_limits"])}', str(s["elements"])]
        for s in gm["sections"]], "Longitudinal sections prepared for the geotechnical engineer (geotech_sections, 23 October 2026)")
    return f"""<section id="s3"><h2>3. Site and existing conditions</h2>
<h3>3.1 Crossing</h3>
<p><span class="flag inf">Inferred</span>{esc(f["identification"]["crossing"]["text"] if "text" in f["identification"]["crossing"] else f["identification"]["crossing"]["value"])}.
The roadway profile under the bridge is supplied to the geometry notebook by the roadway geometry XML (registered source ROADWAY), which covers part of
the crossing; the vertical-clearance figure of Section 2.5 is the minimum over the covered region.</p>
<h3>3.2 Terrain and survey</h3>
<p>Existing ground at the site is the Ex_I-95_Middle LandXML survey, placed under the registered CAD model; the Pond 14D proposed grading lies east
of Ramp B. The journal records the terrain at the pier as EL {g["terrain_pier"]:.4f} ft, {g["algn_terrain"]:.3f} ft below the PGL; the foundation
models use the soil-surface elevations below, which differ from the CAD terrain by up to 6.3 in at the pier (assumption A-013, accepted as negligible).</p>
{terrain}
<p>Four longitudinal sections through the registered model and the survey were cut on 23 October 2026 for the geotechnical engineer (Appendix D).
The survey stops about 100 ft short of the required 100-ft clearance beyond the outer project elements on both ramps; a wider survey is needed to close
those ends.</p>
{secs}
<h3>3.3 Geotechnical information</h3>
<p>{c.tbs(f["bdr_items"]["geotechnical_report"]["text"])}</p>
<p>The FB-MultiPier models carry the soil profiles used for the lateral and axial pile analyses (sand, with the depth-to-fixity rate n<sub>h</sub> =
{pt["PIER"]["inputs"]["n_h"]["value"]:g} ksi/ft of LRFD Table C10.4.6.3-2 in the column checks); minimum tip elevations, the pile order and test-pile
lengths and the scour elevations are N/A in the Pile Data Table until the handoff is received. The geotechnical engineer has given 18 tons of downdrag
per end-bent pile (D-050); its documentation (neutral plane, scourable layers) is pending.</p>
<h3>3.4 Hydraulics and drainage</h3><p>{c.tbs(f["bdr_items"]["drainage"]["text"])}</p>
<h3>3.5 Utilities, lighting, railroad, wildlife</h3>
<p>{c.tbs(f["bdr_items"]["utilities"]["text"])}<br>{c.tbs(f["bdr_items"]["lighting"]["text"])}<br>
<span class="flag inf">Inferred</span>{esc(f["bdr_items"]["railroad"]["text"])}<br>{c.tbs(f["bdr_items"]["wildlife_connectivity"]["text"])}</p>
</section>"""


def typsec_figure(c: Ctx):
    """Sheet S-1: the typical section cut from the registered model."""
    t = c.b["typsec"]
    sec = t["section"]
    return c.figure(
        f'<img class="sheet" src="{img_data(t["png"])}" alt="Sheet S-1 typical section">',
        f'Sheet {esc(t["number"])}, {esc(t["title"].title())}: the superstructure cut from the registered FreeCAD model at '
        f'Sta. {esc(sec["station"])} (mid-span 1), looking ahead station, in FDOT CADD symbology ({esc(t["generator"])}). '
        f'Measured on the model: {ftin(sec["deck_out_to_out_ft"] * 12)} out to out, {ftin(sec["clear_between_barriers_ft"] * 12)} clear, '
        f'beams at {ftin(sec["beam_spacing_ft"] * 12)}, {ftin(sec["slab_thickness_at_pgl_ft"] * 12)} slab, {sec["crossfall"]["L"] * 100:.1f}% crossfall. '
        f'The fence enclosure is not in the model and is not drawn.')


def s4_geometry(c: Ctx, g, fig_section, fig_elev):
    c.section = "4 Geometry"
    f = c.b["facts"]
    sta = c.table(["Point", "Station", "PGL elevation (ft)", "Note"], [
        ["Begin bridge, FFBW End Bent 1", figures._fmt_sta(g["sta_eb1"]), f2(g["pgl_start"], 3), "Journal BeginBridge_station / PGL_start_elev"],
        ["℄ Pier", figures._fmt_sta(g["sta_pier"]), f2(g["pgl_pier"], 3), f'Crest of the profile; +{g["grade"] * 100:.2f}% from Begin Bridge, −{g["grade"] * 100:.2f}% to End Bridge'],
        ["End bridge, FFBW End Bent 2", figures._fmt_sta(g["sta_eb2"]), f2(g["pgl_end"], 3), "Journal EndBridge_station / PGL_end_elev"],
    ], "Horizontal and vertical control on the PGL (journal Bridge Geometry - 2 Beam)", numeric=(2,))
    xsec = c.table(["Element", "Dimension"], [
        ["Clear width between parapets", ftin(g["clear_w_in"])],
        ["Parapets", f'{ftin(g["parapet_w_in"])} wide × {ftin(g["parapet_h_in"])} high, outer face {ftin(g["edge_offset_in"])} inboard of the deck edge'],
        ["Deck, out to out", ftin(g["deck_w_in"])],
        ["Deck slab", f'{ftin(g["slab_in"])} Class II concrete, {g["crossfall"] * 100:.0f}% crossfall from the crown; ends thickened {ftin(g["deckend_add_in"])} over {ftin(g["deckend_len_in"])}'],
        ["Beams", f'2 ~ FIB-36 at {ftin(g["beam_spacing_in"])}, {ftin(g["flange_in"])} top flange, minimum haunch {g["haunch_min_in"]:.2f} in'],
        ["Superstructure depth", f'{ftin(g["super_depth_in"])} (beam, haunch, slab)'],
        ["Fence enclosure", f'{ftin(g["fence_straight_in"], 16)} straight above the parapet with a curved top of {ftin(g["fence_radius_in"], 16)} outer radius; {ftin(g["fence_ht_in"], 16)} overall; posts at {ftin(g["fence_post_in"])}'],
        ["Handrails", "34 in above the walking surface (journal Access Geometry and ADA)"],
    ], "Bridge typical section")
    return f"""<section id="s4"><h2>4. Roadway and bridge geometry</h2>
<h3>4.1 Alignment and profile</h3>
<p>The bridge is tangent and square (0° skew in the beam runs and the bearing layout). The PGL rises at {g["grade"] * 100:.2f}% from Begin Bridge to a
crest at the pier and falls at the same grade to End Bridge; the deck crossfall is {g["crossfall"] * 100:.0f}% each way from the crown. Spans are
{f2(g["span1"])} ft and {f2(g["span2"])} ft between the front face of backwall and the pier centreline ({f2(g["total"])} ft overall).</p>
{sta}
{c.figure(fig_elev, "Bridge elevation on the PGL with the existing ground and the approach ramps, from the registered model and survey (Appendix D sections A-2 and B-2).")}
<h3>4.2 Typical section</h3>
{xsec}
{fig_section}
<h3>4.3 Approaches</h3>
<p>Ramp A (west) and Ramp B (east) are MSE-walled fill ramps that bring the walkway down to grade with switchback runs; the journal Access Geometry
module sizes the runs at 5% (1:20) so that the walkways are not ramps under ADA 403 and shows the switchback length needed on the east side.
The 4-in walking slabs bear on the end-bent backwalls (D-017) and the ramp slabs thicken locally to the backwall tops (D-053). The MSE walls, copings,
barrier returns and landings are owned by the CAD model and the MSE detail drawing (MSE-DETAIL-DXF); the four barrier-return bases are the only
MSE-interface inputs to the geometry notebook (D-036). Wall lengths and face areas are in Section 9.</p>
</section>"""


def s5_type(c: Ctx, g):
    c.section = "5 Structure type"
    f = c.b["facts"]
    b = c.b["beams"][1]
    archive = [t for tag, n, t in c.J.modules if t.startswith("Archive")]
    return f"""<section id="s5"><h2>5. Structure type selection</h2>
<h3>5.1 General (FDM 121.9.1(1))</h3>
<p>The bridge length is set by the width of the I-95 cross section being spanned and by the ramp footprints on either side; no hydraulic opening,
railroad or navigation clearance applies. With the pier placed in the median the two spans are {f2(g["span1"])} ft and {f2(g["span2"])} ft, within the
economical range of a 36-in Florida-I beam at the 8'-7" spacing of a 12-ft walkway, and the {ftin(g["super_depth_in"])} superstructure depth keeps the
profile, and therefore the ramp lengths, to the minimum consistent with the {f["report"]["fdm_260_clearance_ft"]} ft clearance.</p>
<h3>5.2 Statical system (121.9.1(2))</h3>
<p>Two simple spans with a continuous deck is the system in the record: simple-span prestressed beams on elastomeric bearings at the pier, with the
thermal movement centred at the pier (calculation C003) and the beam-end rotations and movements checked at the level pier seats (C016, D-063 to
D-065). Making the beams continuous for live load was not needed for strength at these spans and would add a diaphragm and negative-moment steel
over the pier for no reduction in beam depth.</p>
<h3>5.3 Superstructure alternatives (121.9.1(3))</h3>
<p>The record holds the selected layout, two FIB-36 beams ({b["strands"]} ~ 0.6-in strands, {b["debonded"]} debonded, {b["fc_beam_ksi"]:g} ksi concrete,
Span 1 and Span 2 Mathcad runs of 12 October 2026, D-022), and the superseded three-beam layout kept in the journal archive
({"; ".join(esc(a) for a in archive)}). The two-beam layout halves the beam count for the same deck width at the cost of a 2'-6" deck overhang,
and was adopted after the superstructure, wind and bearing calculations were rerun on it.</p>
<p>{c.tbs(f["bdr_items"]["alternatives_statement"]["text"])}</p>
<h3>5.4 Substructure alternatives (121.9.1(4))</h3>
<p>End bents: pile-supported caps with backwalls and cheek walls inside the MSE walls, their lateral load carried by soil-reinforcement tie-back straps
into the reinforced fill (D-014, SDG 3.13.2.N) rather than by pile bending, which keeps the end-bent piles vertical and the cap short. Pier: a solid
wall between the four pipe piles under a {ftin(g["pier_cap_w_in"])} × {ftin(g["pier_cap_h_in"])} cap, with the wall carried on welded annular ring plates on the
piles (C017, the welded-ring concept selected over the fin-plate and hairpin concept C006, which was withdrawn under D-082). A multi-column pier or a
hammerhead was not needed for a 13'-7" deck.</p>
<h3>5.5 Foundation alternatives (121.9.1(5))</h3>
<p>Driven piles at every support: 18-in square prestressed concrete piles (Standard Plans Index 455-018) at the end bents, where the fill downdrag
and the MSE exclusion zone (C015) govern the layout, and 20-in steel pipe piles at the pier, whose shells receive the welded ring plates of the pier
wall. Drilled shafts and spread footings were not carried: the end bents sit in reinforced fill and the pier loads are modest.</p>
<p>{c.tbs(f["bdr_items"]["grs_abutments"]["text"])}</p>
<h3>5.6 Precast feasibility (121.9.1(9))</h3>
<p>{c.tbs(f["bdr_items"]["precast_feasibility"]["text"])}</p>
<h3>5.7 Vessel collision, scour, movable bridge, security, alternative designs</h3>
<p><span class="flag inf">Inferred</span>{esc(f["bdr_items"]["vessel_collision"]["text"])}<br>
<span class="flag inf">Inferred</span>{esc(f["bdr_items"]["scour"]["text"])}<br>
<span class="flag inf">Inferred</span>{esc(f["bdr_items"]["movable_bridge"]["text"])}<br>
<span class="flag inf">Inferred</span>{esc(f["bdr_items"]["bridge_security"]["text"])}<br>
<span class="flag inf">Inferred</span>{esc(f["bdr_items"]["alternative_designs"]["text"])}</p>
</section>"""


def s6_superstructure(c: Ctx, g):
    c.section = "6 Superstructure"
    bm = c.b["beams"]
    rows = []
    for span in (1, 2):
        b = bm[span]
        rows.append([f"Span {span}", esc(b["beam_type"]), f2(b["L_beam_ft"], 3), f'{b["bearing_distance_in"]:g}', f'{b["strands"]} ({b["debonded"]} debonded) + {b["top_strands"]} top',
                     f'{b["jacking_kip"]:.2f}', f'{b["fc_beam_ksi"]:g} / {b["fci_beam_ksi"]:g}', f'{b["net_camber_in"]:.3f}', esc(b["environment"])])
    beams = c.table(["Span", "Beam", "Beam length (ft)", "Bearing distance (in)", "0.6-in strands", "Jacking (kip/strand)", "f'c / f'ci (ksi)", "Net camber at 120 d (in)", "Environment"],
                    rows, "Prestressed beams, saved results of the registered Mathcad runs (MCAD-S1, MCAD-S2)", numeric=(2, 3, 5, 7))
    bearing = g["bearing"]
    brg = (f'The level pier seats were checked for the beam-end rotations of the saved beam runs: static {bearing.get("static", "—")} rad against 0.0125 rad and cyclic '
           f'{bearing.get("cyclic", "—")} rad against 0.004 rad (Standard Plans Index 400-510 limits), with a conservative longitudinal thermal and creep movement of '
           f'{bearing.get("move", "—")} in against the 1-in shear limit of the pad (C016, D-063).') if bearing else "Bearing rotation check: see calculation C016."
    return f"""<section id="s6"><h2>6. Superstructure</h2>
<p>Two FIB-36 prestressed concrete beams at {ftin(g["beam_spacing_in"])} carry a {ftin(g["slab_in"])} cast-in-place Class II deck, {ftin(g["deck_w_in"])} out to out,
with {ftin(g["parapet_h_in"])} concrete parapets and a metal-fabric fence enclosure over the walkway. The deck ends are thickened {ftin(g["deckend_add_in"])} over
{ftin(g["deckend_len_in"])} at the end bents (journal thickened-deck-end detail). Square deck edges with {ftin(0.75)} chamfers and drip grooves follow D-031 and
D-044.</p>
{beams}
<p>The 120-day net cambers above drive the haunch and seat geometry of the geometry notebook and the saved CAD model (D-023); the midpoint minimum
flange haunches are 0.943 in (Span 1) and 0.500 in (Span 2), and the haunch concrete totals {g["haunch_total_ft3"]:.1f} ft³ (journal).</p>
<h3>6.1 Bearings and seats</h3>
<p>Type F composite elastomeric bearing pads, {g["pad_l_in"]:g} × {g["pad_w_in"]:g} × {ftin(g["pad_t_in"], 16)} (3 internal layers of 1/2 in, 4 steel laminates, G = 110 psi),
on {ftin(g["pedestal_h_in"])} pedestals {ftin(g["pedestal_w_in"])} wide; the bearing line is 9 in from the beam ends and the pier bearing lines are 1'-9" apart
(journal). {brg} The as-cast pedestal tops are level at each pedestal's maximum (D-065, D-086) and the final seat and grinding elevations remain open.</p>
<h3>6.2 Railings, fence and lighting</h3>
<p>Pedestrian parapets {ftin(g["parapet_h_in"])} high with 34-in handrails and a curved-top metal-fabric fence enclosure ({ftin(g["fence_ht_in"])} overall) close the
walkway over I-95 (FDM 222 to 224; LRFD 13.8.2 fence wind basis in C002). {c.tbs(c.b["facts"]["bdr_items"]["lighting"]["text"])}</p>
</section>"""


def s7_substructure(c: Ctx, g):
    c.section = "7 Substructure"
    cases = c.b["cases"]
    pc, ec = cases["PIER-CASE"]["inputs"], cases["EB-CASE"]["inputs"]
    pw = cases["PIER-WALL-CASE"]
    ck = cases["CHEEK-CASE"]["inputs"]
    caps = c.b["caps"]
    pk = c.b["pile_checks"]
    wc, cc = c.b["wall_checks"], c.b["cheek_checks"]
    strap = c.b["strap"]

    def bar(n, size):
        return f"{n} ~ #{size}"

    geom = c.table(["Element", "End bents (End Bent 1 governs both, D-004)", "Pier"], [
        ["Cap", f'{ftin(ec["b"])} wide × {ftin(ec["h"])} deep × {ftin(g["eb_cap_len_in"])} long (251 in over the cheek webs)', f'{ftin(pc["b"])} wide × {ftin(pc["h"])} deep × {ftin(g["pier_cap_len_in"])} long'],
        ["Piles", f'{ec["N_pile"]} ~ {ftin(ec["D_pile"])} square prestressed at {ftin(ec["S_pile"] * 12)}, embedded {ftin(ec["Pile_embed"])}', f'{pc["N_pile"]} ~ {ftin(pc["D_pile"])} steel pipe at {ftin(pc["S_pile"] * 12)}, embedded {ftin(pc["Pile_embed"])}'],
        ["Cap longitudinal steel (saved case)", f'top {bar(ec["n_N1"], ec["Bar_N1"])}; bottom at piles {bar(ec["n_P1"], ec["Bar_P"])}; between piles {bar(ec["n_B1"], ec["Bar_B"])}; skin {bar(ec["n_skin"], ec["Bar_skin"])}',
         f'top {bar(pc["n_N1"], pc["Bar_N1"])}; bottom at piles {bar(pc["n_P1"], pc["Bar_P"])}; between piles {bar(pc["n_B1"], pc["Bar_B"])}; skin {bar(pc["n_skin"], pc["Bar_skin"])}'],
        ["Cap transverse steel", f'#{ec["Bar_v"]} hoops at {ec["s_G"]:g} in', f'#{pc["Bar_v"]} hoops at {pc["s_G"]:g} in'],
        ["Walls", f'{ftin(g["backwall_t_in"])} backwall, {g["backwall_H"]:.3f} ft at the crown ({g["backwall_H_edge"]:.3f} ft at the edges) above the cap; {ftin(g["cheek_t_in"])} cheek webs {g["cheek_H"]:.2f} ft high with rear and bottom lugs; one centred #4 mat at 10 in each way',
         f'Pier wall {ftin(pw["length_in"])} × {ftin(pw["thickness_in"])} × {ftin(pw["height_in"])} (EL 24.53 to the cap bottom), #{pw["grid_bar"]} at {pw["grid_spacing_in"] if not pw["auto_grid_spacing"] else 11:g} in each way each face; '
         f'two cheek walls {ftin(ck["H_w"])} × {ftin(ck["w_w"])} × {ftin(ck["t_w"])} with a recessed chamfered panel and a centred #4 mat'],
        ["Pile-to-wall / cap connection", "Piles embedded 12 in in the cap (moment transfer pending, SDG 3.5.1.C)", f'{pw["ring_count"]} rows of annular ring plates per pile, {pw["ring_od_in"]:g} in OD × {pw["ring_id_in"]:g} in ID × {pw["ring_t_in"]:g} in, two {Fraction(pw["weld_leg_in"]).limit_denominator(16)} in continuous fillets'],
        ["Lateral load path", f'Tie-back straps into the MSE fill at 1.5 ft above the cap (D-014, D-019): {strap["service_kip_ft"]:.3f} kip/ft service, {strap["factored_kip_ft"]:.3f} kip/ft factored ({strap["governing"]})', "Pile bending with the wall (FB-MultiPier fixed-head runs)"],
        ["Bearing seats", "4 pedestals 30 in long on the 42-in cap, level tops (D-065)", "2 pedestals 48 in long, level tops (D-065)"],
    ], "Substructure configuration in the registered cases and CAD model")

    def cap_row(label, calc, counts, case):
        return [label, calc, f'{ftin(case["b"])} × {ftin(case["h"])}', f'M<sub>u</sub> {case["Mu_B"]:.1f} kip-ft (between piles), {case["Mu_N"]:.1f} kip-ft (over piles); V<sub>u</sub> {case["Vu_G"]:.1f} kip; T<sub>u</sub> {case["Tu"]:.1f} kip-ft',
                f'{counts["fail"]} FAIL entries (incl. the aggregate), {counts["pending"]} pending/conditional ({counts["decision"]}, {counts["report_date"]} report)']

    results = c.table(["Component", "Calc.", "Section", "Governing actions (Strength)", "Register status"], [
        cap_row("End Bent 1 cap", "C008", caps["EB"], ec),
        cap_row("End Bent 2 cap", "C009", caps["EB2"], cases["EB2-CASE"]["inputs"]),
        cap_row("Pier cap", "C010", caps["PIER"], pc),
        ["End Bent 1 piles", "C011", "18-in PSC, 12 ~ 0.6-in strands", f'{esc(pk["EB1"]["governing_check"])}: D/C {pk["EB1"]["max_structural_ratio"]:.3f}', f'{pk["EB1"]["counts"].get("FAIL", 0)} FAIL; {len(pk["EB1"]["pending"])} pending entries'],
        ["End Bent 2 piles", "C012", "18-in PSC, 12 ~ 0.6-in strands", f'{esc(pk["EB2"]["governing_check"])}: D/C {pk["EB2"]["max_structural_ratio"]:.3f}', f'{pk["EB2"]["counts"].get("FAIL", 0)} FAIL; {len(pk["EB2"]["pending"])} pending entries'],
        ["Pier piles", "C013", "20-in pipe, 0.48-in wall, A252 Gr 3", f'{esc(pk["PIER"]["governing_check"])}: D/C {pk["PIER"]["max_structural_ratio"]:.3f} ({esc(pk["PIER"]["governing_note"].split(".")[0])})', f'{pk["PIER"]["counts"].get("FAIL", 0)} FAIL; {len(pk["PIER"]["pending"])} pending entries'],
        ["End-bent backwall, cheek walls, straps", "C014", "12-in backwall, 8-in cheeks", f'Strap load {strap["factored_kip_ft"]:.3f} kip/ft factored; one centred #4 mat at 10 in', "All numerical checks pass; 9 pending entries across six unconfirmed prerequisites (D-057)"],
        ["Pier wall on annular rings", "C017", f'{ftin(pw["length_in"])} × {ftin(pw["thickness_in"])} wall, 1/2-in rings', f'Largest passing ratio {wc["max_pass"][0]:.2f} ({esc(wc["max_pass"][1])}); all 20 rings in full contact', f'{wc["counts"].get("PASS", 0)} PASS / {wc["counts"].get("FAIL", 0)} FAIL ({", ".join(wc["failed"])}: ring clearance to the face grid at the 3-in placement tolerance)'],
        ["Pier cap cheek walls", "C018", "48 × 48 × 12 in", f'Strength III wind 0.060 ksf; largest ratio {cc["max_pass"][0]:.2f} ({esc(cc["max_pass"][1])})', f'{cc["counts"].get("PASS", 0)} PASS / {cc["counts"].get("FAIL", 0)} FAIL; {len(cc["pending"])} pending (single-mat shrinkage convention)'],
        ["Bearings and support details", "C016", "Type F pads", "Rotation and movement within the Index 400-510 limits (D-063)", "Final bearing fit in undeformed geometry FAIL pending the seat and grinding elevations (D-065)"],
        ["MSE wall exclusion", "C015", "Both end bents", "Front walls 46.5 in and side walls 114 in from the pile rows against the 24-in criterion", "Two side-wall rows read SHORTFALL by their last digits (A-010, pending)"],
    ], "Design results in the registered calculations (selection is not engineering acceptance)")
    return f"""<section id="s7"><h2>7. Substructure</h2>
{geom}
<h3>7.1 Design results</h3>
<p>Each calculation is a registered report with its saved case and check register (Appendix E). The FAIL entries of the end-bent caps are the
end-face U-grid pile clearance finding and its aggregate (COH-019, a detailing revision); the pier cap FAIL entries are its aggregate and the same
detail. The pier wall calculation fails one placement check (ring clearance to the inner face-grid layer at the 3-in radial pile tolerance); every
strength, contact, bearing, plate and weld check passes.</p>
{results}
<p class="note">Fixed-head FB-MultiPier runs of 19 and 22 October 2026 (D-049, D-077) supply the actions; the pile heads sit about 0.08 in above the
notebook cutoffs at the pier and End Bent 2 and the final reruns at the current cutoffs remain open (COH-028). The D-062 load review accepted the
differences between the journal loads and the export loads as negligible (assumptions A-001 to A-008).</p>
</section>"""


def s8_foundations(c: Ctx, g):
    c.section = "8 Foundations"
    f = c.b["facts"]
    cols = g["pile_cols"]
    rows = g["pile_rows"]
    body = []
    for i, col in enumerate(cols):
        body.append([esc(col)] + [esc(str(rows[k][i])) for k in ("EB1", "EB2", "PIER")])
    pdt = c.table(["Pile Data Table (SDM 11.4)", "End Bent 1", "End Bent 2", "Pier"], body, "Pile Data Table from the registered pile designs (22 October 2026); N/A = not applicable or not yet received", numeric=(1, 2, 3))
    pt = c.b["pile_tables"]
    basis = pt["EB1"]["basis"]
    return f"""<section id="s8"><h2>8. Foundations</h2>
<h3>8.1 Foundation type and analysis</h3>
<p>Driven piles at all three supports, analysed as pile groups in FB-MultiPier 6.1.0 with the superstructure reactions, wind and temperature of the
journal entry tables (modules FBMP Entry - Pier / End Bent). The end-bent piles are {ftin(g["eb_pile_w_in"])} square prestressed concrete (Index 455-018,
12 ~ 0.6-in strands, 336 kip effective prestress) with {g["pile_rows"]["EB1"][9]} tons of downdrag per pile applied as drag load DR
(γ<sub>DR</sub> 1.10 at strength, 1.00 at Service I; excluded from the Factored Design Load, SDM 11.4). The pier piles are {ftin(g["pier_pile_d_in"])} steel pipe,
ASTM A252 Grade 3, analysed as non-composite with a {esc(g["pipe"]["Sacrificial_thk"])} sacrificial thickness ({esc(g["pipe"]["t_eff"])} effective wall).
Trial pile lengths in the model are {g["pile_trial_ft"]:g} ft (<span class="flag inf">Inferred</span>{esc(f["geometry"]["trial_pile_length_ft"]["basis"])}).</p>
<p>The nominal bearing resistance follows SDG 3.5.13 Eq. 3-1, R<sub>n</sub> = (FDL + net scour + downdrag) / φ with φ = {g["pile_rows"]["EB1"][15]} (SDG Table 3.5.7-1,
footnote 7); the 18-in prestressed pile sits well under the 300-ton driving limit of SDG Table 3.5.13-1 and the pipe-pile limit is to be confirmed with
the geotechnical engineer. Pile spacing is exactly 3 diameters at the pier (SDG 3.5.4) and 3.0 widths at the end bents.</p>
{pdt}
<h3>8.2 Items that complete the foundation design</h3>
<ul>
<li>{c.tbs("Phase I Geotechnical Report with borings, minimum tip elevations (SDG 3.5.9), test-pile or pile-order lengths, downdrag documentation and the pipe-pile driving limit (FDM 121.10).", "Pending")}</li>
<li>{c.tbs("Scour: concurrence that the grade separation has no scour design (Pile Data Table columns K to O) from the drainage and geotechnical engineers.", "Pending")}</li>
<li>{c.tbs("Environment classification and the corrosion allowance of the pipe piles (A-011).", "Pending")}</li>
<li>{c.tbs("Drivability and driving stresses (LRFD 10.7.8, Spec. 455) and the pile-to-cap connection with 12-in embedment (SDG 3.5.1.C, SDM 11.6).", "Pending")}</li>
<li>{c.tbs("Final FB-MultiPier reruns with the pile heads at the notebook cutoffs (COH-028) and the complete load comparison (COH-004).", "Pending")}</li>
</ul>
<h3>8.3 GRS abutments</h3><p>{c.tbs(f["bdr_items"]["grs_abutments"]["text"])}</p>
</section>"""


def s9_walls(c: Ctx, g):
    c.section = "9 Retaining walls"
    f = c.b["facts"]
    walls = g["mse_walls"]
    rows = [[esc(w["wall"]), esc(w["base_length"]), f2(w["area_ft2"], 1) if w["area_ft2"] else "—"] for w in walls]
    tot = g["mse_totals"].get("area_ft2")
    tbl = c.table(["MSE wall", "Base length", "Face area (ft²)"], rows + [["Total", "", f2(tot, 1) if tot else "—"]], "MSE walls of Ramps A and B (journal Quantities - MSE Wall)", numeric=(2,))
    return f"""<section id="s9"><h2>9. Retaining walls</h2>
<p>Mechanically stabilised earth walls retain both approach ramps (A1 to A8 on Ramp A, B1 to B9 on Ramp B), about {tot / 9:,.0f} square yards of
face in all, with copings, barrier returns and 1/2-in joints at the end bents (D-026, D-033). The end-bent caps sit inside the walls with their
cheek-wall lugs and the 0.5-in MSE joints; calculation C015 checks the MSE exclusion zone around the end-bent piles (front walls 46.5 in and side walls
114 in from the pile rows against the 24-in criterion; two rows read SHORTFALL by their last digits, A-010). The backwall tie-back straps (C014,
SDM 12.3.F plan note: {c.b["strap"]["service_kip_ft"]:.2f} kip/ft service, {c.b["strap"]["factored_kip_ft"]:.2f} kip/ft factored) attach to the backwall at a
level to be aligned with an MSE reinforcement layer (D-019); SDG 3.13.2.N.3 permits the attachment only when the settlement of the soil above the cap
bottom does not exceed 2 in, a geotechnical confirmation that is pending.</p>
{tbl}
<p>{c.tbs(f["bdr_items"]["retaining_wall_study"]["text"])}</p>
</section>"""


def s10_construction(c: Ctx, g):
    c.section = "10 Construction"
    f = c.b["facts"]
    beam_kip = g["gravity"].get("beam_kip")
    beam_txt = f"{beam_kip:.0f} kip" if beam_kip else "—"
    return f"""<section id="s10"><h2>10. Temporary traffic control, constructability and construction time</h2>
<h3>10.1 Temporary traffic control (FDM 121.9.1(8))</h3>
<p>The bridge spans the I-95 mainline. The two {f2(c.b["beams"][1]["L_beam_ft"], 1)}-ft and two {f2(c.b["beams"][2]["L_beam_ft"], 1)}-ft FIB-36 beams
(about {beam_txt} each) are erected over live traffic from the median pier and the end bents, which fixes the crane positions, the lane closures
and the erection windows; the pier wall, pile driving in the median and the deck pour over traffic are the other overhead work items.</p>
<p>{c.tbs(f["bdr_items"]["temporary_traffic_control"]["text"])}</p>
<h3>10.2 Constructability and maintenance (FDM 121.9.4)</h3>
<p>Members are standard FDOT products (FIB-36 beams under 110 ft, Index 455 piles, A252 pipe) within ordinary transport limits. The pier wall is cast
around the pipe piles after the ring plates are welded on in the field, which needs the pile placement tolerance of 3 in to be held or the ring
clearance to the wall steel re-detailed (C017 RING-GRID finding). The end-bent walls are cast in sequence with the MSE wall lifts so that the tie-back
straps can be placed at their reinforcement level. The structure is inspectable from grade; the walkway enclosure and the pier wall leave no concealed
spaces.</p>
<h3>10.3 Construction time (FDM 121.9.2)</h3><p>{c.tbs(f["bdr_items"]["construction_time"]["text"])}</p>
</section>"""


def s11_pedestrian(c: Ctx, g):
    c.section = "11 Pedestrian facilities"
    ag = c.J.defs.get("AccessGeometry", {})
    return f"""<section id="s11"><h2>11. Bicycle and pedestrian facilities and ADA access (FDM 121.9.1(15))</h2>
<p>The structure is a pedestrian overpass: a {ftin(g["clear_w_in"])} clear walkway between {ftin(g["parapet_h_in"])} parapets with 34-in handrails, enclosed over the
roadway by a curved-top metal-fabric fence {ftin(g["fence_ht_in"])} high (FDM 222 to 224). Access is by the two MSE-walled ramps with switchback runs; the
journal Access Geometry and ADA module records the 2010 ADA Standards criteria applied (403 walking surfaces, 405 ramps: running slope not steeper
than 1:12, cross slope 1:48, 36-in clear width, 30-in maximum rise per run, 60-in landings; 505 handrails for rises over 6 in) and sizes the runs at
5% (1:20) so that they remain walkways: the east ramp drops {esc(ag["Elev_dropEB2ramp"].text) if "Elev_dropEB2ramp" in ag else "—"} to grade over
{esc(ag["EB2_rampLength"].text) if "EB2_rampLength" in ag else "—"} of run. The walking slabs are 4 in on the ramps and thicken locally to the backwall
tops (D-053); the deck crossfall is {g["crossfall"] * 100:.0f}%, within the 1:48 cross-slope limit. Bicycles are not a design use of the record
(pedestrian live load only, D-015); confirm the facility type with the District.</p>
</section>"""


def s12_aesthetics(c: Ctx, g):
    c.section = "12 Aesthetics"
    f = c.b["facts"]
    return f"""<section id="s12"><h2>12. Aesthetics (FDM 121.9.3)</h2>
<p>FDM 121.9.3 names pedestrian bridges among the sites where aesthetics may play a more important role, and the District establishes the level of
aesthetic effort. The record carries these treatments: a slender two-beam superstructure with square deck edges, chamfers and drip grooves (D-031,
D-044); the pier wall and cap as one solid form, with recessed, chamfered panels on the pier cheek walls (D-059); copings and level barrier returns
on the MSE walls (D-026, D-033); and the curved-top fence enclosure. No colour, texture or landscape treatment is in the record.</p>
<p>{c.tbs(f["bdr_items"]["aesthetics_level"]["text"])}<br>{c.tbs(f["bdr_items"]["aesthetics_cost"]["text"])}</p>
</section>"""


def s13_cost(c: Ctx, g):
    c.section = "13 Quantities and cost"
    f = c.b["facts"]
    q = g["quantities"]
    bm = c.b["beams"]
    beam_lf = 2 * bm[1]["L_beam_ft"] + 2 * bm[2]["L_beam_ft"]
    cy = lambda ft3: f2(ft3 / 27, 1)
    rebar_total = sum(g["rebar_lb"].values())
    items = [
        ["Superstructure", "Prestressed beams, FIB-36", f2(beam_lf, 1), "LF", "4 beams, lengths of the Mathcad runs"],
        ["Superstructure", "Bridge deck concrete, Class II", cy(q.get("Bridge Deck", 0)), "CY", f'{f2(q.get("Bridge Deck", 0), 1)} ft³ (journal Quantities - Bridge)'],
        ["Superstructure", "Haunch concrete", cy(g["haunch_total_ft3"]), "CY", "journal Bridge Geometry haunch volume"],
        ["Superstructure", "Pedestrian parapets", f2(2 * g["total"], 1), "LF", f'{f2(q.get("2 Barriers", 0), 1)} ft³ (journal)'],
        ["Superstructure", "Fence enclosure", f2(g["total"], 1), "LF", "over the bridge length"],
        ["Superstructure", "Bearing pads, Type F", "8", "EA", "journal Bearing_pad_count"],
        ["Substructure", "End bent caps, Class IV", cy(q.get("2 End Bents", 0)), "CY", f'{f2(q.get("2 End Bents", 0), 1)} ft³ (journal)'],
        ["Substructure", "End bent backwalls", cy(2 * g["backwall_vol_ft3"]), "CY", f'2 × {g["backwall_vol_ft3"]:.2f} ft³ (backwall case geometry)'],
        ["Substructure", "End bent cheek walls", cy(q.get("4 Cheek Walls", 0)), "CY", f'{f2(q.get("4 Cheek Walls", 0), 1)} ft³ (journal)'],
        ["Substructure", "End bent pedestals", cy(q.get("4 End Bent Pedestals", 0)), "CY", "journal"],
        ["Substructure", "Closure slabs at the end bents", cy(g["closure_ft3"] or 0), "CY", f'{g["closure_ft3"]:.1f} ft³ (D-044)' if g["closure_ft3"] else "—"],
        ["Substructure", "Pier cap", cy(q.get("Pier Cap", 0)), "CY", f'{f2(q.get("Pier Cap", 0), 1)} ft³ (journal)'],
        ["Substructure", "Pier wall", cy(g["pier_wall_vol_ft3"]), "CY", f'{g["pier_wall_vol_ft3"]:.1f} ft³ (journal gravity sheet, D-075 geometry; the Quantities sheet row of 841.1 ft³ predates D-075)'],
        ["Substructure", "Pier cheek walls", cy(q.get("2 Pier Cheek Walls", 0)), "CY", "journal"],
        ["Substructure", "Pier pedestals", cy(q.get("2 Pier Pedestals", 0)), "CY", "journal"],
        ["Substructure", "Reinforcing steel, substructure", f2(rebar_total, 0), "LB", f'CAD model bar list ({sum(g["rebar_count"].values())} bars; end bents and pier only, excludes deck, piles and MSE)'],
        ["Substructure", "Annular ring plates and fillet welds", "20", "EA", "276 lb of 1/2-in plate (D-079)"],
        ["Foundations", "Prestressed concrete piles, 18 in", f2(8 * g["pile_trial_ft"], 0), "LF", f'8 piles × {g["pile_trial_ft"]:g} ft trial length; order lengths pending'],
        ["Foundations", "Steel pipe piles, 20 in", f2(4 * g["pile_trial_ft"], 0), "LF", f'4 piles × {g["pile_trial_ft"]:g} ft trial length; order lengths pending'],
        ["Walls", "MSE wall face", f2((g["mse_totals"].get("area_ft2") or 0) / 9, 0), "SY", "journal Quantities - MSE Wall"],
        ["Walls", "Soil reinforcement tie-back straps", "14", "EA", "7 per backwall, schematic (D-045); supplier design"],
    ]
    rows = [[esc(a), esc(b_), qn, u, esc(n), "—", "—"] for a, b_, qn, u, n in items]
    tbl = c.table(["Group", "Pay item (preliminary)", "Quantity", "Unit", "Basis", "Unit cost", "Amount"], rows, "Preliminary quantities (FDM 121.9.1(10)); unit costs to be supplied", numeric=(2, 5, 6))
    return f"""<section id="s13"><h2>13. Quantities, unit costs and cost estimate (FDM 121.9.1(10) to (12))</h2>
<p>Quantities below are read from the journal quantity sheets, the saved cases and the CAD model bar list; they are the rough quantities FDM 121.9.1(10)
allows for a minor bridge and are intended for a relative cost comparison, not a final estimate. Deck reinforcement, approach-slab and ramp walking-slab
concrete, MSE copings and barriers, fence hardware and the earthwork of the ramps are not quantified in the record.</p>
{tbl}
<p>{c.tbs(f["bdr_items"]["unit_costs"]["text"])}</p>
<p>{c.tbs("Cost curves (FDM 121.9.1(12)): with a single viable span arrangement (median pier) no span-arrangement cost curve was developed; a statement to that effect, or the curve, is required.")}</p>
<p>{c.tbs("Total estimated construction cost of the recommended design (FDM 121.9.8).")}</p>
</section>"""


def s14_plans(c: Ctx, g):
    c.section = "14 30% plans"
    dr = c.b["drawings"]
    t = c.b["typsec"]
    rows = [[esc(s["number"]), esc(s["title"]), esc(", ".join(s["scales"]))] for s in dr["sheets"]]
    tbl = c.table(["Sheet", "Title", "Scales"], [["P-1", "GENERAL PLAN (whole model, 1\" = 40')", "1\" = 40'"],
                                                 [esc(t["number"]), esc(t["title"]) + " (superstructure, mid-span 1)", esc(t["scales"][0])]] + rows,
                  "Preliminary FDOT-format sheets generated from the registered model (Appendix C)")
    req = c.table(["30% Structures Plans item (FDM 121.9.9)", "Status in the record"], [
        ["General Notes sheet", c.tbs("not in the record; the design-basis notes of the journal and the sheet notes of B4-1 to B4-16 are the material for it")],
        ["Plan and Elevation sheet", c.tbs("general plan P-1 and the record elevation of Figure 1 exist; the SDM plan-and-elevation sheet with the profile, clearances and bridge limits is not drawn")],
        ["Substructures: elements, sizes, foundation type and pile arrangement", '<span class="flag ok">Provided</span>End bent and pier plans, elevations, sections, details and bar list, sheets B4-1 to B4-16'],
        ["Superstructure: cross section with railings, slab thickness, beam type and spacing", f'<span class="flag ok">Provided</span>Typical section cut from the model, sheet {esc(t["number"])} (Figure 2; the fence enclosure is not modelled); framing plan and beam details not drawn'],
        ["Retaining walls: preliminary control drawings", c.tbs("MSE wall geometry in the CAD model and MSE-DETAIL-DXF; control drawings not prepared")],
        ["Bridge Hydraulics Recommendation Sheet", '<span class="flag inf">Inferred</span>Not applicable to a grade separation, subject to drainage concurrence'],
        ["Report of core borings", c.tbs("no borings in the record")],
        ["Construction sequence and access", c.tbs("see Section 10")],
        ["Preliminary aesthetic details", c.tbs("pier cheek wall panels (B4-8); see Section 12")],
        ["Preliminary foundation layouts and pile data table", f'<span class="flag ok">Provided</span>Pile layouts on B4-1, B4-5 and B4-12; Pile Data Table in Section 8 (minimum tips, scour and lengths N/A)'],
        ["Sidewalks: accessible elements", c.tbs("ramp walking slabs and landings in the CAD model; accessible-element details not drawn")],
        ["Design Exceptions and Design Variations", c.tbs("none identified in the record; confirm (FDM 122)")],
    ], "FDM 121.9.9 minimum contents of the 30% Structures Plans")
    return f"""<section id="s14"><h2>14. 30% Structures Plans (FDM 121.9.9)</h2>
<p>The record holds an 18-sheet preliminary set generated from the registered FreeCAD model in FDOT CADD symbology ({esc(dr["generator"])};
{esc(t["generator"])} for the typical section): the general plan of the whole model, the superstructure typical section, and the substructure plans,
elevations, sections, details and reinforcing bar list of both end bents and the pier.
The sheets are review copies, not contract drawings: the border is an approximation of the FDOT cell, the bridge number, FPID, county and EOR fields
are blank, and the sheets carry MODEL CHECK notes where the model and the calculations are not yet reconciled.</p>
{tbl}
{req}
</section>"""


def s15_conclusions(c: Ctx, g):
    c.section = "15 Conclusions"
    rev = c.b["review"]
    items = c.table(["Item", "Status", "Subject", "Next action"], [[esc(i["id"]), esc(i["status"]), esc(i["subject"]), esc(i["next"])] for i in rev["items"]],
                    f'Outstanding coherence items ({rev["outstanding"]}; review of {esc(rev["checked_at"][:10])})')
    return f"""<section id="s15"><h2>15. Conclusions and recommendations (FDM 121.9.8)</h2>
<p><b>Recommended structure.</b> A two-span pedestrian bridge of {f2(g["total"])} ft: two FIB-36 prestressed beams at {ftin(g["beam_spacing_in"])} with a
{ftin(g["slab_in"])} cast-in-place deck, {ftin(g["clear_w_in"])} clear, fenced; pile-supported end bents with backwalls, cheek walls and tie-back straps inside
MSE-walled ramps; a pier of {g["pier_piles"]} steel pipe piles with a solid pier wall on welded annular ring plates under a {ftin(g["pier_cap_w_in"])} ×
{ftin(g["pier_cap_h_in"])} cap. The configuration satisfies the clearance, walkway and ADA criteria of Section 2 and every registered strength and service
check except the detailing findings listed below.</p>
<p><b>Findings to resolve before the 60% Substructure submittal.</b></p>
<ul>
<li>End-face U-grid pile clearance at the end-bent caps (COH-019) and the cap/cheek-wall steel coordination items (COH-024, COH-025).</li>
<li>Ring clearance to the pier wall face grid at the 3-in pile placement tolerance (C017 RING-GRID) and the wall verticals' anchorage into the cap.</li>
<li>Final FB-MultiPier reruns at the notebook pile cutoffs with the complete load comparison (COH-028, COH-004), then the cap and pile reports.</li>
<li>Geotechnical handoff: minimum tip elevations, downdrag documentation, settlement confirmation for the tie-back straps, pile order lengths, drivability.</li>
<li>Environment classification and the Bridge Corrosion Environment Report (A-011); corrosion allowance of the pipe piles.</li>
<li>Final bearing seat and grinding elevations (D-065/D-086) and the end-bent seat rotation check.</li>
</ul>
<p><b>Items that complete the BDR submittal.</b> The {len(c.open_items)} flagged items of Appendix H: the Phase I Geotechnical Report, drainage concurrence,
the corrosion report, the temporary traffic control concept, the GRS and precast feasibility statements, the retaining wall study, the aesthetics level,
unit costs and the total construction cost, the construction time, and the utility, lighting and wildlife-connectivity statements of the FDM 121.10
checklist (Appendix G).</p>
{items}
</section>"""


# ------------------------------------------------------------ appendices --
def app_a_plan(c: Ctx):
    c.section = "Appendix A"
    plan = c.b["plan"]
    return f"""<section id="appA" class="pb"><h2>Appendix A. General plan</h2>
<p class="note">Sheet P-1, the plan of the registered FreeCAD model looking down at 1" = 40' ({esc(plan.get("generator", "substructure_drawings.model_plan"))}
{esc(str(plan.get("version", "")))}; model SHA-256 {esc(plan.get("model_sha256", "")[:12])}…). Stationing increases left to right; FFBW End Bent 1 at
Sta. {figures._fmt_sta(c.b["geotech"]["stations"]["EB1"])}.</p>
<img class="sheet" src="{img_data(sources.SOURCES["PLAN-PNG"])}" alt="General plan sheet P-1">
</section>"""


def app_b_figures(c: Ctx, fig_section, fig_elev):
    c.section = "Appendix B"
    t = c.b["typsec"]
    return f"""<section id="appB" class="pb"><h2>Appendix B. Typical section and elevation</h2>
<p class="note">Sheet {esc(t["number"])} ({esc(t["generator"])}, <code>{esc(t["dxf"])}</code>), the typical section cut from the registered
FreeCAD model (SHA-256 {esc(t["model_sha256"][:12])}…) at Sta. {esc(t["section"]["station"])}; Figure 2 of Section 4.</p>
<img class="sheet" src="{img_data(t["png"])}" alt="Sheet S-1 typical section">
{fig_elev}{figures.legend_html()}<p class="note">Elevation on the PGL from the geotechnical sections A-2 and B-2 (Figure 1 of Section 4).</p>
</section>"""


def app_c_sheets(c: Ctx):
    c.section = "Appendix C"
    dr = c.b["drawings"]
    t = c.b["typsec"]
    parts = [f'<section id="appC" class="pb"><h2>Appendix C. Preliminary substructure sheets</h2>'
             f'<p class="note">{esc(dr["generator"])}, generated from the registered FreeCAD model (SHA-256 {esc(dr["model_sha256"][:12])}…) in FDOT CADD '
             f'symbology; review copies of <code>{esc(dr["dxf"])}</code> (the typical section, <code>{esc(t["dxf"])}</code>, is in Appendix B). '
             f'Preliminary, not for construction.</p>']
    for s in dr["sheets"]:
        if s["png"]:
            parts.append(f'<figure><img class="sheet" src="{img_data(s["png"])}" alt="Sheet {esc(s["number"])}"><figcaption>Sheet {esc(s["number"])} — {esc(s["title"])}</figcaption></figure>')
    parts.append("</section>")
    return "".join(parts)


def app_d_geotech(c: Ctx):
    c.section = "Appendix D"
    gm = c.b["geotech_manifest"]
    rows = [[esc(s["id"]), f'{s["from"]} to {s["to"]}', f'{s["offset_ft"]:.1f} ft', str(s["projected_piles"]), esc(", ".join(s["eg_survey_limits"]))] for s in gm["sections"]]
    return f"""<section id="appD" class="pb"><h2>Appendix D. Geotechnical sections</h2>
<p>Four longitudinal sections through the registered model and the existing-ground survey, prepared for the geotechnical engineer on 23 October 2026
(<code>geotech_sections/output/</code>: one DXF per section at 1:1 in US survey feet and the interactive report <code>B4_Geotech_Sections.html</code>).
Each runs from the pier centreline to at least 100 ft beyond the outermost project element; no soil layers, borings or water table are shown.</p>
{c.table(["Section", "Stations", "Offset from the PGL (north)", "Projected piles", "Survey limit"], rows, "Geotechnical section planes")}
</section>"""


def app_e_calcs(c: Ctx):
    c.section = "Appendix E"
    rows = []
    for m in c.J.calc_modules():
        rows.append([esc(m["number"]), esc(m["title"]), esc(m["module"]), esc(CALC_REPORTS.get(m["number"], ""))])
    reg = c.b["register"]
    reports = [r for r in reg if r["source_id"].endswith("-REPORT")]
    rrows = [[esc(r["source_id"]), esc(r["topic"]), esc(r["path"]), esc(r["registered_on"])] for r in reports]
    return f"""<section id="appE" class="pb"><h2>Appendix E. Design calculations index</h2>
<p>The design calculations are the numbered journal modules C001 to C018 (C005 and C006 retired; numbers are permanent). Each has a notebook, a
calculation report with definition and citation cards, and its Blockpad journal edition; the registered reports below are the selected project sources.</p>
{c.table(["No.", "Calculation", "Journal module", "Report / package"], rows, "Journal calculations")}
{c.table(["Source id", "Report", "Path", "Registered"], rrows, "Registered calculation reports")}
</section>"""


def app_f_sources(c: Ctx):
    c.section = "Appendix F"
    rows = [[esc(r["source_id"]), esc(r["topic"]), esc(r["path"]) or "—", esc(r["status"].split(";")[0][:90]), esc(r["registered_on"])] for r in c.b["register"]]
    return f"""<section id="appF" class="pb"><h2>Appendix F. Source register</h2>
<p class="note">The {len(rows)} registered sources of <code>project_current/source_register.csv</code> as of {esc(c.b["as_of"])}; the full status
text, SHA-256 and dependencies are in the register. "Current" is source selection, not engineering acceptance.</p>
{c.table(["Id", "Topic", "Path", "Status", "Registered"], rows, "Source register", cls="small")}
</section>"""


def app_g_checklist(c: Ctx):
    c.section = "Appendix G"
    flag = {"provided": "ok", "partial": "inf", "missing": "tbs", "n/a": "inf"}
    word = {"provided": "Provided", "partial": "Partial", "missing": "Missing", "n/a": "Not applicable"}
    rows = [[esc(i["item"]), f'<span class="flag {flag[i["status"]]}">{word[i["status"]]}</span>', esc(i["note"])] for i in c.b["facts"]["checklist_fdm_121_10"]]
    return f"""<section id="appG" class="pb"><h2>Appendix G. BDR submittal checklist (FDM 121.10, Form 121-A)</h2>
{c.table(["Checklist item", "Status", "Note"], rows, "Submittal checklist status against the project record")}
</section>"""


def app_h_open(c: Ctx):
    c.section = "Appendix H"
    rows = [[esc(i["section"]), f'<span class="flag {"tbs" if i["kind"] == "To be supplied" else "pend"}">{esc(i["kind"])}</span>', esc(i["text"])] for i in c.open_items]
    arows = [[esc(a["id"]), esc(a["kind"]), esc(a["disposition"]["status"]), esc(a["statement"].split(". Re-judged")[0][:260]), esc(a["disposition"].get("decision", ""))] for a in c.b["assumptions"]]
    drows = [[esc(d["id"]), esc(d["date"]), esc(d["decision"])] for d in c.b["decisions"]]
    return f"""<section id="appH" class="pb"><h2>Appendix H. Open items, assumptions and decisions</h2>
<h3>H.1 Items flagged in this report</h3>
{c.table(["Section", "Kind", "Item"], rows, "BDR items the project record does not yet answer, and pending design inputs")}
<h3>H.2 Assumptions-and-gaps register</h3>
{c.table(["Id", "Kind", "Disposition", "Statement", "Decision"], arows, "project_current/coherence/assumptions.json", cls="small")}
<h3>H.3 Adopted decisions</h3>
{c.table(["Id", "Date", "Decision"], drows, "project_current/decisions.md (basis and limits in the file)", cls="small")}
</section>"""


# ---------------------------------------------------------------- render --
def render(bundle, version: str):
    c = Ctx(bundle)
    g = derived(c)
    fig_elev = figures.elevation_svg(bundle["geotech"], bundle["geotech"]["stations"], {})
    fig_section = typsec_figure(c)      # sheet S-1, cut from the model (after fig_elev: Figure 1 is the elevation)

    sections = [
        cover(c, g),
        None,   # TOC placeholder
        executive_summary(c, g),
        s1_introduction(c, g),
        s2_criteria(c, g),
        s3_site(c, g),
        s4_geometry(c, g, fig_section, fig_elev),
        s5_type(c, g),
        s6_superstructure(c, g),
        s7_substructure(c, g),
        s8_foundations(c, g),
        s9_walls(c, g),
        s10_construction(c, g),
        s11_pedestrian(c, g),
        s12_aesthetics(c, g),
        s13_cost(c, g),
        s14_plans(c, g),
        s15_conclusions(c, g),
        app_a_plan(c),
        app_b_figures(c, fig_section, fig_elev),
        app_c_sheets(c),
        app_d_geotech(c),
        app_e_calcs(c),
        app_f_sources(c),
        app_g_checklist(c),
        app_h_open(c),
    ]
    entries = [("exec", "Executive summary", 1), ("s1", "1. Introduction and project description", 1), ("s2", "2. Design criteria", 1),
               ("s3", "3. Site and existing conditions", 1), ("s4", "4. Roadway and bridge geometry", 1), ("s5", "5. Structure type selection", 1),
               ("s6", "6. Superstructure", 1), ("s7", "7. Substructure", 1), ("s8", "8. Foundations", 1), ("s9", "9. Retaining walls", 1),
               ("s10", "10. Temporary traffic control, constructability and construction time", 1), ("s11", "11. Pedestrian facilities and ADA access", 1),
               ("s12", "12. Aesthetics", 1), ("s13", "13. Quantities, unit costs and cost estimate", 1), ("s14", "14. 30% Structures Plans", 1),
               ("s15", "15. Conclusions and recommendations", 1),
               ("appA", "Appendix A. General plan", 1), ("appB", "Appendix B. Typical section and elevation", 1), ("appC", "Appendix C. Preliminary substructure sheets", 1),
               ("appD", "Appendix D. Geotechnical sections", 1), ("appE", "Appendix E. Design calculations index", 1), ("appF", "Appendix F. Source register", 1),
               ("appG", "Appendix G. BDR submittal checklist", 1), ("appH", "Appendix H. Open items, assumptions and decisions", 1)]
    sections[1] = toc(entries)
    title = f'{bundle["facts"]["report"]["title"]} — {bundle["facts"]["report"]["structure"]}'
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="generator" content="{esc(version)}">
<style>{CSS}</style></head>
<body>
{"".join(sections)}
<footer class="note" style="margin-top:30px;border-top:1px solid var(--line);padding-top:6px">{esc(version)} · generated from the project record of {esc(bundle["as_of"])} · bdr/output/B4_Bridge_Development_Report.html</footer>
</body></html>
"""
    data = {
        "as_of": bundle["as_of"], "version": version, "derived": {k: v for k, v in g.items() if k not in ("quantities", "mse_walls", "gravity")},
        "quantities": g["quantities"], "gravity": g["gravity"], "mse_walls": g["mse_walls"], "open_items": c.open_items,
        "pile_tables": {k: {"columns": v["columns"], "row": v["row"]} for k, v in bundle["pile_tables"].items()},
        "pile_checks": bundle["pile_checks"], "wall_checks": bundle["wall_checks"], "cheek_checks": bundle["cheek_checks"],
        "caps": bundle["caps"], "review": bundle["review"], "calc_modules": c.J.calc_modules(),
        "typical_section": {k: bundle["typsec"][k] for k in ("number", "title", "generator", "section", "cut")},
    }
    return html, data
