"""FDOT CADD Manual and Structures Detailing Manual (SDM) conventions used by the DXF.

Symbology follows the FDOT CADD Manual (``CADD_MANUAL``; sections and PDF
pages cited below) and the FDOT CADD Standard Level Table (``LEVEL_TABLE``):

- Levels (5.10.1.3, p. 47): every element is on a Structures level with
  ByLevel color, line style and weight; layer 0 carries nothing.
- Colors (5.10 Color Symbology, p. 48): the default Bentley color table.
  Bentley 0-7 map to ACI as in the FDOT-workspace DXF export in the project
  (``project_current/geometry/details/B4 Pedestrian Bridge - Working.dxf``).
- Line styles (5.10.3.2, p. 49): Bentley line style n is the Autodesk
  linetype DGNn of FDOT.LIN.
- Line weights (5.10 Line Weight Symbology, p. 50): the manual's
  Bentley/Autodesk mapping table.
- Text (5.12, pp. 52-54): the FDOT TrueType fonts, the FDOT text style names
  and heights and the special characters of the FDOT fonts.
"""
import math
from fractions import Fraction

CADD_MANUAL = {
    "source": "FDOT CADD Manual, Topic No. 625-050-001, publish date November 1, 2024",
    "file": "caddmanual2025.pdf",
    "sha256": "3074d0027748686d38bababae898e1f9f1cf0b13d0fe241b2fb4cdbcf07de222",
    "sections": "5.10 levels/layers and symbology (PDF pp. 46-50); 5.12 text (pp. 52-54); 7.11 prints (pp. 94-96)",
}

LEVEL_TABLE = {
    "source": "FDOT CADD Standard Level Table, 10-25-2023, worksheet 'Level Definition Details'",
    "url": "https://fdotwww.blob.core.windows.net/sitefinity/docs/default-source/cadd/downloads/"
           "publications/caddmanualfdm/levels/fdotcaddstandardleveltable-10-25-2023.xlsx?sfvrsn=5c1b90b4_2",
    "file": "fdotcaddstandardleveltable-10-25-2023.xlsx",
    "sha256": "8d2ac22a556721927c11af15c3d9ea73f5b809806a100cd4b982b4328b735d50",
}

# name: (FDOT level number, description, Bentley color, Bentley style, Bentley weight)
LEVELS = {
    "SubStrConc": (2200, "Substructure Concrete", 2, 0, 3),
    "SubStrConc_h": (2201, "Substructure Concrete Hidden", 2, 2, 3),
    "SubStrConc2": (2210, "Substructure Concrete Misc", 2, 0, 3),
    "SubStrConc2_h": (2211, "Substructure Concrete Misc Hidden", 2, 2, 3),
    "PileConc": (2202, "Pile Concrete", 2, 0, 3),
    "PileConc_h": (2203, "Pile Concrete Hidden", 2, 2, 2),
    "PileSteel": (2204, "Pile Steel H-Piles & Pipe", 6, 0, 1),
    "PileSteel_h": (2205, "Pile Steel H-Piles & Pipe Hidden", 6, 2, 1),
    "BearingPadMisc": (2450, "Bearings Miscellaneous Pads", 1, 0, 1),
    "BeamConc_h": (2111, "Beams Concrete Hidden", 2, 2, 2),
    "AppSlabConc": (2400, "Approach Slab Concrete", 2, 0, 3),
    "AppSlabConc_h": (2401, "Approach Slab Concrete Hidden", 2, 2, 2),
    "WallMSEPanel": (2606, "Wall MSE Panels", 2, 0, 3),
    "WallMSEPanel_h": (2607, "Wall MSE Panels Hidden", 2, 2, 2),
    "Rebar": (2250, "Reinforcing Major", 4, 0, 1),
    "Rebar_h": (2251, "Reinforcing Hidden", 4, 2, 1),
    "Rebar2": (2252, "Auxillary Rebar", 4, 0, 1),
    "Patterning": (2703, "All; Any Patterning", 3, 0, 1),
    "CL_Major": (2002, "Use as needed", 3, 7, 0),
    "CL_Minor": (2003, "Use as needed", 0, 4, 0),
    "BaseLineSurveyPGL": (2004, "Baseline Survey orProfile Grade Line", 3, 6, 0),
    "Dimension": (2001, "Dimension Lines", 0, 0, 0),
    "Leader": (2006, "Leader lines, Weld Symbols", 0, 0, 0),
    "TextStructures": (2010, "Structures Text", 0, 0, 0),
    "Symbols": (2704, "All Symbols not covered by Structures Site Menu", 0, 0, 1),
    "Tables": (2007, "Data Tables and All Autodesk Tables", 0, 0, 1),
    "Border": (2000, "Border Elements & Text", 0, 0, 1),
    "TextStructShtNo": (2016, "Sheet Number for Structures Border Sheet Numbers", 0, 0, 0),
    "ClipBorder_dp": (105, "CLIP Border", 4, 2, 0),
}

BENTLEY_TO_ACI = {0: 7, 1: 5, 2: 3, 3: 1, 4: 2, 5: 6, 6: 30, 7: 4}

# Line Weight Symbology (5.10, PDF p. 50): MicroStation weight -> Autodesk
# line weight in mm, written as DXF lineweights (1/100 mm).
BENTLEY_WEIGHT_TO_LW = {0: 9, 1: 15, 2: 20, 3: 30, 4: 35, 5: 40, 6: 53, 7: 60, 8: 70, 9: 80, 10: 90, 11: 90,
                        12: 100, 13: 106, 14: 120, 15: 120, 16: 140, 17: 140, 18: 140}
BENTLEY_WEIGHT_TO_LW.update({w: 211 for w in range(19, 31)})

# Line styles (5.10.3.2, PDF p. 49): Bentley line style n = Autodesk linetype
# DGNn (FDOT.LIN).  A MicroStation DWG/DXF export writes "DGN Style n" for the
# same line codes; set LINETYPE_NAME = "DGN Style %d" to write those names for a
# round trip to MicroStation line codes.
LINETYPE_NAME = "DGN%d"
# Pattern lengths (feet).  Styles 2 and 6 are as in the FDOT-workspace DXF
# export (style 6, dash-dot-dot, is not in that file and is defined to the
# same scale).  Styles 4 and 7 are the two centerline styles and are long
# dash, short dash (never dash-dot with a dot; STYLE_GUIDE D3, markup
# "Centerlines should have dashes not dots"): each pattern is the long dash,
# a gap, the short dash (a tenth of the long dash) and a gap, so that with
# LTSCALE_PER_SF = 0.5 the long dash plots about 0.45 in (style 4) and 0.6 in
# (style 7) on paper.
LINETYPE_PATTERNS = {
    2: [0.895099, 0.53706, -0.35804],
    4: [0.1125, 0.075, -0.015, 0.0075, -0.015],
    6: [0.176696, 0.064252, -0.032126, 0.000079, -0.024094, 0.000079, -0.032126],
    7: [0.15, 0.1, -0.02, 0.01, -0.02],
}
STYLE_TO_LINETYPE = {0: "Continuous"}
STYLE_TO_LINETYPE.update({n: LINETYPE_NAME % n for n in LINETYPE_PATTERNS})
LINETYPES = {LINETYPE_NAME % n: ("DGN line code %d" % n, p) for n, p in LINETYPE_PATTERNS.items()}
HIDDEN_LINETYPE = STYLE_TO_LINETYPE[2]
# Per-entity linetype scale per unit of drawing scale factor (so patterns plot
# at a consistent size in every view): hidden dash ~0.12 in, centerline long
# dash ~0.45 in (style 4) and ~0.6 in (style 7) with a short dash a tenth as
# long between them.
LTSCALE_PER_SF = {LINETYPE_NAME % n: s for n, s in {2: 0.0186, 4: 0.5, 6: 0.25, 7: 0.5}.items()}

# FDOT TrueType fonts (5.12, PDF p. 52): name -> (file, family, bold).  The
# family and bold flag go into the text style's extended font data, from
# which the receiving workstation resolves the installed font.  FDOT and FDOT
# Bold are one family (subfamily Bold); the FDOT fonts carry their own 12
# degree slant, so the styles have no oblique angle.
FONTS = {
    "FDOT": ("FDOT.ttf", "FDOT", False),
    "FDOT Bold": ("FDOTBold.ttf", "FDOT", True),
    "FDOT Imprint": ("FDOTImprint.ttf", "FDOT Imprint", False),
    "FDOT Imprint Bold": ("FDOTImprintBold.ttf", "FDOT Imprint Bold", True),
    "FDOT Mono": ("FDOTMono.ttf", "FDOT Mono", False),
}
# FDOT Text Styles (5.12.1.1, PDF pp. 52-53): name -> (font, height, width) in
# feet on the 1:1 sheet.  The DXF styles have height 0; entity heights are
# these heights times the drawing scale factor.  "FDOT Imprint" is the
# border-cell lettering (FDOT Imprint is "used mainly within the FDOT sheet
# border"), sized to its cell.
TEXT_STYLES = {
    "FDOT Structures": ("FDOT", 0.0063, 0.0063),
    "FDOT Structures Annotation": ("FDOT", 0.0063, 0.0063),
    "FDOT Structures Views_SectionArrow": ("FDOT Bold", 0.008, 0.008),
    "FDOT Structures Initials": ("FDOT", 0.0058, 0.0058),
    "FDOT (Small)": ("FDOT", 0.005833, 0.005833),
    "FDOT (Medium)": ("FDOT", 0.008333, 0.008333),
    "FDOT (Large)": ("FDOT", 0.010417, 0.010417),
    "FDOT Bold (Medium)": ("FDOT Bold", 0.008333, 0.008333),
    "FDOT Bold (Large)": ("FDOT Bold", 0.010417, 0.010417),
    "FDOT Mono (Small)": ("FDOT Mono", 0.006, 0.006),
    "FDOT_SHEET_DESCRIPTION": ("FDOT Imprint Bold", 0.010417, 0.010417),
    "FDOT_SHEET_COUNTY": ("FDOT Bold", 0.005833, 0.005833),
    "FDOT_SHEET_FPID": ("FDOT Bold", 0.005833, 0.005833),
    "FDOT_SHEET_SR": ("FDOT Bold", 0.005833, 0.005833),
    "FDOT_SHEET_REVISION_DATE": ("FDOT Mono", 0.005, 0.004),
    "FDOT_SHEET_REVISION_DESCRIPTION": ("FDOT Mono", 0.005, 0.004),
    "FDOT Imprint": ("FDOT Imprint", None, None),
}
TEXT_STYLE = "FDOT Structures"                       # notes, callouts, table values
DIM_TEXT_STYLE = "FDOT Structures Annotation"        # dimension text
LETTER_STYLE = "FDOT Structures Views_SectionArrow"  # section and view letters
TITLE_STYLE = "FDOT Bold (Large)"                    # view titles, bridge number
TABLE_TITLE_STYLE = "FDOT Bold (Medium)"             # table titles and headings, sheet number
HEADING_STYLE = "FDOT (Medium)"                      # NOTES: headings, project name
SMALL_STYLE = "FDOT (Small)"                         # table column heads, small notes, border values
SHEET_TITLE_STYLE = "FDOT_SHEET_DESCRIPTION"
BORDER_STYLE = "FDOT Imprint"
STAMP_STYLE = "FDOT Mono (Small)"
DIM_STYLE = "FDOT Structures Note-Arrow"


def style_in(name):
    """Plotted text height of an FDOT text style, inches."""
    return TEXT_STYLES[name][1] * 12.0


# Plotted sizes, inches.
TEXT_IN = style_in(TEXT_STYLE)             # 0.0756
NOTE_IN = TEXT_IN
TITLE_IN = style_in(TITLE_STYLE)           # 0.125
TABLE_TITLE_IN = style_in(TABLE_TITLE_STYLE)  # 0.10
ARROW_IN = 0.0781      # DIMASZ of FDOT Structures Note-Arrow (0.006509 ft)
DOT_IN = 0.05          # filled dot: bar end-on in a section / stirrup end in elevation
FRACTION = 0.7         # DIMTFAC of FDOT Structures Note-Arrow; height of a stacked fraction
# FDOT Text Size (5.12.1.2, PDF p. 53): line spacing averages three-fourths of
# the text height, a line pitch of 1.75 text heights, which is 1.05 times the
# MTEXT single line spacing (5/3 of the text height).
LINE_PITCH = 1.75
MTEXT_LINE_SPACING = LINE_PITCH / (5.0 / 3.0)

# Drawing scale name (inches per foot) -> scale factor (feet per paper foot).
SCALES = {"3/8": 32.0, "3/4": 16.0, "1": 12.0, "1/2": 24.0, "1-1/2": 8.0}


def level_attrs(name):
    """DXF layer attributes for an FDOT level."""
    number, desc, color, style, weight = LEVELS[name]
    return {
        "color": BENTLEY_TO_ACI[color],
        "linetype": STYLE_TO_LINETYPE[style],
        "lineweight": BENTLEY_WEIGHT_TO_LW[weight],
        "description": "FDOT %d %s" % (number, desc),
    }


# ------------------------------------------------- FDOT font characters
# FDOT Special Symbols (5.12, PDF p. 54), checked by rendering the installed
# FDOT, FDOT Bold and FDOT Mono fonts (the Imprint fonts lack them): U+00A1
# is the centerline symbol, U+00BC-00BE the quarters, U+0183-0186 the eighths
# and U+0187-018E the sixteenths, drawn as small tight fractions.
# FDOT_FONT_GLYPHS = False writes the centerline as U+2104 and fractions as
# MTEXT diagonal stacks, for a receiving workstation without the FDOT fonts.
FDOT_FONT_GLYPHS = True
CL_GLYPH = "¡"
CL_FALLBACK = "℄"
FRACTION_GLYPHS = {Fraction(1, 4): "¼", Fraction(1, 2): "½", Fraction(3, 4): "¾"}
FRACTION_GLYPHS.update({Fraction(n, 8): chr(0x183 + i) for i, n in enumerate((1, 3, 5, 7))})
FRACTION_GLYPHS.update({Fraction(n, 16): chr(0x187 + i) for i, n in enumerate(range(1, 16, 2))})


def font_text(s):
    """Text as written to the DXF: with FDOT_FONT_GLYPHS off, the FDOT
    centerline character becomes U+2104."""
    return s if FDOT_FONT_GLYPHS else s.replace(CL_GLYPH, CL_FALLBACK)


# --------------------------------------------------------------- formatting
_FRACTION_TEXT = {fr: "%d/%d" % (fr.numerator, fr.denominator) for fr in FRACTION_GLYPHS}


def round_in(inches, step):
    """Round to the nearest multiple of ``step`` inches, halves away from zero."""
    q = Fraction(inches).limit_denominator(1 << 20) / Fraction(step).limit_denominator(64)
    n = math.floor(q + Fraction(1, 2))
    return n * Fraction(step).limit_denominator(64)


def ft_in(length_ft, step=0.125, mtext=True, sign=False):
    """SDM 2.11.2.F dimension text: 4'-0 1/2", 7 1/2", 3/4".

    ``step`` is the precision in inches (SDM 2.11.3: concrete 1/8", rebar
    spacing and partial lengths 1/4", overall bar lengths 1").
    Drawing text (``mtext``) writes the fraction tight against the whole
    number as an FDOT font fraction character (4'-0½"), see ``frac``;
    otherwise as plain text (4'-0 1/2").
    """
    total = round_in(abs(length_ft) * 12.0, step)
    neg = length_ft < 0 and total != 0
    whole_in = math.floor(total)
    fr = total - whole_in
    feet, inch = divmod(int(whole_in), 12)
    if mtext:
        fs = frac(fr) if fr else ""
    else:
        fs = (" " + _FRACTION_TEXT[fr]) if fr else ""
    if total >= 12:
        txt = "%d'-%d%s\"" % (feet, inch, fs)
    elif whole_in >= 1:
        txt = "%d%s\"" % (inch + 12 * feet, fs)
    else:
        txt = "%s\"" % (fs.strip() if fs else "0")
    return ("-" if neg else "") + txt


def frac(fr):
    """Fraction of an inch in drawing text: the FDOT font character
    (frac(Fraction(1, 2)) -> '½'); with FDOT_FONT_GLYPHS off an MTEXT
    diagonal stack ({\\H0.7x;\\S1#2;})."""
    if FDOT_FONT_GLYPHS:
        return FRACTION_GLYPHS[fr]
    return "{\\H%gx;\\S%s;}" % (FRACTION, _FRACTION_TEXT[fr].replace("/", "#"))


def ft_in_list(length_in, step=0.25):
    """Bar-list FT-IN without unit marks (FDOT bar list form): 20-4, 18-8¾."""
    total = round_in(length_in, step)
    whole = math.floor(total)
    fr = total - whole
    feet, inch = divmod(int(whole), 12)
    return "%d-%d%s" % (feet, inch, frac(fr) if fr else "")


def bar_len(length_in):
    """Overall bar length rounded to the nearest inch (SDM 4.3.10.C): 20'-5"."""
    n = int(math.floor(length_in + 0.5))
    feet, inch = divmod(n, 12)
    return "%d'-%d\"" % (feet, inch)


def bar_len_list(length_in):
    """Bar-list style FT-IN pair, nearest inch."""
    n = int(math.floor(length_in + 0.5))
    return divmod(n, 12)


def elev(z_ft):
    """Elevations to 0.001 ft without unit (SDM 2.11.1.E / 2.11.3.I)."""
    return "%.3f" % (math.floor(z_ft * 1000.0 + 0.5) / 1000.0)


def station(s_ft):
    s = math.floor(s_ft * 100.0 + 0.5) / 100.0
    hundreds = int(s // 100)
    return "%d+%05.2f" % (hundreds, s - 100 * hundreds)


def dms(angle_deg):
    total = int(math.floor(abs(angle_deg) * 3600 + 0.5))
    d, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return "%d°%02d'%02d\"" % (d, m, s)
