"""FDOT CADD and Structures Detailing Manual (SDM) conventions used by the DXF.

Level names, numbers and Bentley symbology come from the FDOT CADD Standard
Level Table dated 25 October 2023 (worksheet "Level Definition Details").
The same table and its DXF mapping were used for the earlier CAD_AI beam DXF
(``CAD_AI/reports/references/fdot-dxf-levels.json``).

Bentley color/weight numbers are not DXF values.  The DXF layer colors and
lineweights below follow the FDOT-seeded working DXF already in the project
(``project_current/geometry/details/B4 Pedestrian Bridge - Working.dxf``):
Bentley color 2 -> ACI 3, 4 -> ACI 2, 3 -> ACI 1, 1 -> ACI 5, 6 -> ACI 30 and
weight 0/1/2/3 -> 0/13/30/40 hundredths of a millimeter.  Line styles use the
same "DGN Style n" linetype names, which MicroStation maps back to its
standard line codes on import.
"""
import math
from fractions import Fraction

LEVEL_TABLE = {
    "source": "FDOT CADD Standard Level Table, 10-25-2023, worksheet 'Level Definition Details'",
    "url": "https://fdotwww.blob.core.windows.net/sitefinity/docs/default-source/cadd/downloads/"
           "publications/caddmanualfdm/levels/fdotcaddstandardleveltable-10-25-2023.xlsx?sfvrsn=5c1b90b4_2",
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
BENTLEY_WEIGHT_TO_LW = {0: 0, 1: 13, 2: 30, 3: 40}
STYLE_TO_LINETYPE = {0: "Continuous", 2: "DGN Style 2", 4: "DGN Style 4", 6: "DGN Style 6", 7: "DGN Style 7"}

# Linetype patterns (feet) copied from the FDOT-seeded working DXF.  "DGN Style 6"
# (dash-dot-dot) is not in that file; it is defined to the same scale.
LINETYPES = {
    "DGN Style 2": ("Dgn Style 2", [0.895099, 0.53706, -0.35804]),
    "DGN Style 4": ("Dgn Style 4", [0.128582, 0.064252, -0.032126, 0.000079, -0.032126]),
    "DGN Style 6": ("Dgn Style 6", [0.176696, 0.064252, -0.032126, 0.000079, -0.024094, 0.000079, -0.032126]),
    "DGN Style 7": ("Dgn Style 7", [0.16063, 0.072283, -0.032126, 0.024094, -0.032126]),
}
# Per-entity linetype scale per unit of drawing scale factor (so patterns plot
# at a consistent size in every view): dash ~0.12 in, centerline ~0.5 in.
LTSCALE_PER_SF = {"DGN Style 2": 0.0186, "DGN Style 4": 0.32, "DGN Style 6": 0.25, "DGN Style 7": 0.26}

# Plotted sizes, inches (FDOT-seeded working DXF styles: 0.0063 ft text).
TEXT_IN = 0.0756
TITLE_IN = 0.125
ARROW_IN = 0.0781
DOT_IN = 0.06          # filled dot at a symbolic stirrup end (CAD_AI convention)

TEXT_STYLE = "FDOT Structures"
OBLIQUE = 15.0         # slant of the FDOT structures lettering
DIM_STYLE = "FDOT Structures"

SCALES = {"3/8": 32.0, "3/4": 16.0, "1": 12.0, "1/2": 24.0}


def level_attrs(name):
    """DXF layer attributes for an FDOT level."""
    number, desc, color, style, weight = LEVELS[name]
    return {
        "color": BENTLEY_TO_ACI[color],
        "linetype": STYLE_TO_LINETYPE.get(style, "Continuous"),
        "lineweight": BENTLEY_WEIGHT_TO_LW.get(weight, 0),
        "description": "FDOT %d %s" % (number, desc),
    }


# --------------------------------------------------------------- formatting
_UNICODE = {Fraction(1, 8): "1/8", Fraction(1, 4): "1/4", Fraction(3, 8): "3/8", Fraction(1, 2): "1/2",
            Fraction(5, 8): "5/8", Fraction(3, 4): "3/4", Fraction(7, 8): "7/8",
            Fraction(1, 16): "1/16", Fraction(3, 16): "3/16", Fraction(5, 16): "5/16", Fraction(7, 16): "7/16",
            Fraction(9, 16): "9/16", Fraction(11, 16): "11/16", Fraction(13, 16): "13/16", Fraction(15, 16): "15/16"}


def round_in(inches, step):
    """Round to the nearest multiple of ``step`` inches, halves away from zero."""
    q = Fraction(inches).limit_denominator(1 << 20) / Fraction(step).limit_denominator(64)
    n = math.floor(q + Fraction(1, 2))
    return n * Fraction(step).limit_denominator(64)


def ft_in(length_ft, step=0.125, mtext=True, sign=False):
    """SDM 2.11.2.F dimension text: 4'-0 1/2", 7 1/2", 3/4".

    ``step`` is the precision in inches (SDM 2.11.3: concrete 1/8", rebar
    spacing and partial lengths 1/4", overall bar lengths 1").
    MTEXT output stacks the fraction (\\S1/2;).
    """
    total = round_in(abs(length_ft) * 12.0, step)
    neg = length_ft < 0 and total != 0
    whole_in = math.floor(total)
    fr = total - whole_in
    feet, inch = divmod(int(whole_in), 12)
    if mtext:
        fs = ("\\S%s;" % _UNICODE[fr].replace("/", "#")) if fr else ""
    else:
        fs = (" " + _UNICODE[fr]) if fr else ""
    if total >= 12:
        txt = "%d'-%d%s\"" % (feet, inch, fs)
    elif whole_in >= 1:
        txt = "%d%s\"" % (inch + 12 * feet, fs)
    else:
        txt = "%s\"" % (fs.strip() if fs else "0")
    return ("-" if neg else "") + txt


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
    return "%dÂ°%02d'%02d\"" % (d, m, s)
