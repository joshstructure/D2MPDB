"""T022: submission formatting of the hand-authored calculation modules (byte-surgical, rerunnable).

`transform(name, text)` returns the edited component text of one module (CRLF kept, nothing re-serialised):

* every static text value cell (`<c ...><textvalue>text</textvalue></c>`) becomes a multiline cell (`<textcell>` holding one
  paragraph) so the text wraps instead of clipping; formula cells stay value cells (numbers, PASS/FAIL colour rules);
* the numbered titles of MSEWallExclusion (C015) and BearingDesign (C016);
* the working language of those two modules (model hashes, task and decision identifiers, implementation status) moves into
  hidden sections or is reworded; superseded history (PierLevelSeatOverride) is hidden;
* three sentences of C002, C004 and C006 that spoke of "this journal";
* the index (PedBridge) link labels and a revision note; the DecisionLog entry.

Every anchor must occur exactly once (`rep`), so a changed base stops the build instead of silently skipping an edit.
No formula string, cache, canvas or resource is touched.
"""
import re

TNR = 'Times New Roman'
TITLES = {'MSEWallExclusion': ('MSE Wall Exclusion - Both End Bents', 'C015 - MSE Wall Exclusion - Both End Bents'),
          'BearingDesign': ('Bearings and Support Details', 'C016 - Bearings and Support Details')}
INDEX_LABELS = [   # (link target, old label, new label) in PedBridge
    ('MSEWallExclusion', 'MSE wall exclusion boxes (D-055 wall lines)', 'C015 - MSE Wall Exclusion (D-055 wall lines)'),
    ('BearingDesign', 'Bearings and Support Details', 'C016 - Bearings and Support Details'),
    ('MSEWallExclusion', 'MSE wall exclusion boxes - both end bents', 'C015 - MSE Wall Exclusion - Both End Bents'),
    ('CapDesignBasis', 'Cap design basis - shared factors (19 October 2026)', 'C007 - Cap Design Basis (shared factors, 19 October 2026)'),
    ('CapDesignEndBentOne', 'Cap design - End Bent 1 (distilled, 19 October 2026 case)', 'C008 - End Bent 1 Cap Design (19 October 2026 case)'),
    ('CapDesignEndBentTwo', 'Cap design - End Bent 2 (distilled, 19 October 2026 case)', 'C009 - End Bent 2 Cap Design (19 October 2026 case)'),
    ('CapDesignPier', 'Cap design - Pier (distilled, 19 October 2026 case)', 'C010 - Pier Cap Design (19 October 2026 case)'),
    ('PileDesignEndBentOne', 'Pile design - End Bent 1 (distilled, 19 October 2026 case)', 'C011 - End Bent 1 Pile Design (19 October 2026 case)'),
    ('PileDesignEndBentTwo', 'Pile design - End Bent 2 (distilled, 19 October 2026 case)', 'C012 - End Bent 2 Pile Design (19 October 2026 case)'),
    ('PileDesignPier', 'Pile design - Pier (distilled, 19 October 2026 case)', 'C013 - Pier Pile Design (19 October 2026 case)'),
    ('EndBentBackwallDesign', 'End-bent backwall, cheek walls and tie-back straps (distilled, 19 October 2026 case, live references)',
     'C014 - End Bent 1 Backwall, Cheek Walls and Tie-Back Straps (19 October 2026 case, live references)'),
]
REVISION_NOTE = ('Revision: 20 October 2026, submission formatting (T022): the calculation modules are numbered C007 to C016 (cap '
                 'design basis C007, cap designs C008 to C010, pile designs C011 to C013, end-bent backwall C014, MSE wall exclusion '
                 'C015, bearings and support details C016; C005 stays retired); the working language of each calculation (provenance, '
                 'tool status, pending items, decision and task identifiers) sits in hidden WorkingNotes sections; table text is in '
                 'multiline cells; "distilled" no longer appears in titles or visible text. No formula, cache or value changed.')
DECISION_SECTION = 'SubmissionFormatting20261020'
DECISION_HEADING = '2026-10-20 - Calculation numbering C007 to C016 and submission formatting (T022)'
DECISION = ('User direction of 20 October 2026: the design and analysis calculations are to be submitted as a finished product. '
            'The calculation modules are numbered in the existing C-series (C001 to C004 and C006 unchanged; C005 stays retired as the '
            'deleted live pier cap module whose formula set the repository still names): C007 CapDesignBasis, C008 CapDesignEndBentOne, '
            'C009 CapDesignEndBentTwo, C010 CapDesignPier, C011 PileDesignEndBentOne, C012 PileDesignEndBentTwo, C013 PileDesignPier, '
            'C014 EndBentBackwallDesign, C015 MSEWallExclusion, C016 BearingDesign. In every calculation module the working language '
            '(how the edition was produced, package and file hashes, tool status, pending-item bookkeeping, decision and task identifiers, '
            'superseded history) is moved into hidden sections (WorkingNotes and the hidden subsections of C015 and C016) and the '
            'visible text no longer says "distilled", "notebook", "tool" or "journal"; static table text is written in multiline cells '
            'so it wraps instead of clipping, while formula cells stay value cells for the PASS/FAIL colour rules; the live project '
            'stamp becomes result-only definitions (Stamp_Firm = ProjectInfo.Firm and the other seven) in multiline cells. The '
            'generated editions (cap, pile and backwall Blockpad sheets, their Mathcad sheets and the three notebooks) are rebuilt by '
            'their generators, which now enforce the visible-text rule at build time; every formula and cache value is unchanged '
            '(result-only caches drop the "= " prefix, as Blockpad writes them natively). Native recalculation, appearance and '
            'engineering reviews not performed; FBMP not rerun; no engineering value changed.')


def once(text, old, label, n=1):
    found = text.count(old)
    assert found == n, f'{label}: expected {n} occurrence(s), found {found}: {old[:100]!r}'


def rep(text, old, new, label):
    once(text, old, label)
    return text.replace(old, new)


def nl_of(text):
    return '\r\n' if '\r\n' in text else '\n'


# ----------------------------------------------------------------------------- table cells
STATIC_CELL = re.compile(r'<c capture="False"((?: (?:background|fontweight)="[^"]*")*)>(?:<textvalue>([^<]*)</textvalue>|<textvalue/>)</c>')
TABLE_BLOCK = re.compile(r'<table\b.*?</table>', re.S)
FONTSIZE = re.compile(r'<stylerule\b[^>]*\bfontsize="([^"]+)"')


def multiline_cells(text):
    """Static text value cells -> multiline cells, table by table (the paragraph takes the table's stylerule font size)."""
    def fix_table(m):
        block = m.group(0)
        size = FONTSIZE.search(block)
        fontsize = size.group(1) if size else '10'

        def cell(c):
            attrs, value = c.group(1), c.group(2) or ''
            bold = 'fontweight="bold"' in attrs
            background = re.search(r' background="[^"]*"', attrs)
            cell_attrs = ' capture="False"' + (background.group(0) if background else '')
            para_attrs = f' fontfamily="{TNR}" fontsize="{fontsize}" spacingafter="0"' + (' fontweight="bold" horzalign="Center"' if bold else '')
            return f'<textcell{cell_attrs}><paragraph{para_attrs}>{value}</paragraph></textcell>'
        return STATIC_CELL.sub(cell, block)
    return TABLE_BLOCK.sub(fix_table, text)


def hidden(name, inner, nl, indent):
    return (f'{indent}<section name="{name}" capture="False" hide="true">{nl}' + inner + f'{nl}{indent}</section>')


# ----------------------------------------------------------------------------- the modules
def title(text, name):
    old, new = TITLES[name]
    return rep(text, f'title="{old}"', f'title="{new}"', f'{name} title')


def mse_wall_exclusion(text):
    nl = nl_of(text)
    text = title(text, 'MSEWallExclusion')
    old = ('<paragraph fontfamily="Times New Roman" fontsize="11" spacingafter="6" background="#FFF8E9">Shared pile size, spacing and cap '
           'dimensions are live journal references (235-in cap since 19 October 2026, D-036). Use nominal pile width only, without a '
           'placement envelope. Wall positions are the saved CAD snapshot of 19 October 2026 (D-055 model); the 8-in cheek webs outside '
           'the cap ends are not part of this screen. In that model the side walls stand 114 in from the pile row, at the 24-in criterion '
           'within 0.0002 in: the side-wall rows below read MEETS CLEAR or SHORTFALL only by the last digits of the saved coordinates.</paragraph>')
    new = ('<paragraph fontfamily="Times New Roman" fontsize="11" spacingafter="6" background="#FFF8E9">Shared pile size, spacing and cap '
           'dimensions are read from Bridge Geometry (235-in cap). Use nominal pile width only, without a placement envelope. Wall '
           'positions are the wall lines of the CAD model of 19 October 2026; the 8-in cheek webs outside the cap ends are not part of '
           'this screen. In that model the side walls stand 114 in from the pile row, at the 24-in criterion within 0.0002 in: the '
           'side-wall rows below read MEETS CLEAR or SHORTFALL only by the last digits of the model coordinates.</paragraph>')
    text = rep(text, old, new + nl + hidden('WorkingNotesInputs', ' ' * 12 + old, nl, ' ' * 8), 'MSE inputs paragraph')
    text = rep(text, 'is the specified layout criterion for this task.', 'is the specified layout criterion for this check.', 'MSE task sentence')
    start = '        <paragraph fontfamily="Times New Roman" fontsize="11" spacingafter="6" fontweight="bold">SOURCE AND PROVENANCE</paragraph>'
    end_marker = '        <paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6">' + nl + '            <link address="https://www.fdot.gov/'
    once(text, start, 'MSE provenance heading')
    once(text, end_marker, 'MSE FDOT link')
    i, j = text.index(start), text.index(end_marker)
    block = text[i:j].rstrip('\r\n')
    assert block.count('<paragraph') == 3 and 'Saved model SHA-256' in block, 'MSE provenance block changed'
    text = text[:i] + hidden('WorkingNotesSources', '    ' + block.replace(nl, nl + '    '), nl, ' ' * 8) + nl + text[j:]
    return multiline_cells(text)


def bearing_design(text):
    nl = nl_of(text)
    text = title(text, 'BearingDesign')
    text = rep(text, 'The journal does not contain a separate top-of-footing datum for this pile-supported pier.',
               'No separate top-of-footing datum is defined for this pile-supported pier.', 'datum sentence')
    text = rep(text, ' Exact fingerprints and independent arithmetic are retained with task T019.', '', 'T019 sentence')
    p = ' ' * 16 + '<paragraph fontfamily="Times New Roman" fontsize="11" spacingafter="5">'
    span1 = p + 'Span 1: PrestressedBeamV6.2_Pedestrian_2Beam_Span1.xmcd; SHA-256 a6b0f967d271c193591d477e219ac66f98b72309d19958a04c6cd08e575a8dcd.</paragraph>'
    span2 = p + 'Span 2: PrestressedBeamV6.2_Pedestrian_2Beam_Span2.xmcd; SHA-256 182e3471f169d3a379c437ad12f359d567813bd4631bcc0b82e78ad860fa91b8.</paragraph>'
    block = span1 + nl + span2
    text = rep(text, block, hidden('BPSourceFingerprints', ' ' * 4 + block.replace(nl, nl + ' ' * 4), nl, ' ' * 16), 'span worksheet fingerprints')
    text = rep(text, '<section name="PierLevelSeatOverride" capture="False" hide="false">',
               '<section name="PierLevelSeatOverride" capture="False" hide="true">', 'superseded override section')
    # the adopted level-seat geometry: the decision stays visible, the direction/implementation bookkeeping moves to a hidden subsection
    para = '<paragraph fontfamily="Times New Roman" fontsize="11" spacingafter="7">'
    text = rep(text, '<heading level="2">Adopted override D-065: level as-cast bearing seats at all supports</heading>',
               '<heading level="2">Adopted bearing-seat geometry: level as-cast bearing seats at all supports</heading>', 'D-065 heading')
    moved = []

    def take(old, label):
        nonlocal text
        once(text, old + nl, label)
        text = text.replace(old + nl, '')
        moved.append(old)

    direction = (para + 'User direction adopted 20 October 2026. This decision supersedes D-064, extends the override to both end bents, '
                 'and selects numerical as-cast pedestal elevations. Maximum means the highest point of each original pedestal top, not the '
                 'highest support elevation across the bridge. Each pedestal is a solid with one horizontal top face; pads are uniform '
                 'thickness and level on that face.</paragraph>')
    text = rep(text, direction, para + 'Design decision (20 October 2026): level as-cast pedestal tops at all supports, each at the maximum '
               'elevation of its original top. Maximum means the highest point of each original pedestal top, not the highest support '
               'elevation across the bridge. Each pedestal is a solid with one horizontal top face; pads are uniform thickness and level on '
               'that face.</paragraph>', 'D-065 direction paragraph')
    moved.append(direction)
    def dyn_para(key, value):      # the native serialisation of these string definitions (single-quoted formula attribute)
        return (para + f'<dynexp formula=\'{key} = "{value}"\' mathlayout="on" showsteps="False"><expbody>{key} = "{value}"</expbody>'
                '</dynexp></paragraph>')

    take(dyn_para('BP_all_seat_override', 'D-065: LEVEL AS-CAST TOPS AT PRIOR MAXIMUM ELEVATIONS'), 'BP_all_seat_override')
    datum = (para + 'Elevations use the existing model datum and are stored at native precision; both pedestals at a support share the listed '
             'value. Prior source model SHA-256: 7de4f5dbeba60c95cd1f383d6474d1b9e79299dd68dd095b00395b6fa21f0f43. Caps, beam profile/camber, '
             'deck and all other geometry are unchanged. The pad thickness is retained; no taper, compression or beveled plate is invented.</paragraph>')
    text = rep(text, datum, para + 'Elevations use the existing model datum and are stored at native precision; both pedestals at a support '
               'share the listed value. Caps, beam profile/camber, deck and all other geometry are unchanged. The pad thickness is retained; '
               'no taper, compression or beveled plate is invented.</paragraph>', 'D-065 datum paragraph')
    moved.append(datum)
    for key, value in (('BP_all_seat_CAD_status', 'IMPLEMENTED: native editable level pedestals and linked level pads; steel elevations preserved'),
                       ('BP_all_seat_final_fit_status', 'FAIL IN UNDEFORMED MODEL: as-cast stock overlaps unchanged beams; final setting and grinding remain open'),
                       ('BP_all_seat_downstream_status', 'Notebook, B4 geometry table and drawings pending reconciliation to D-065')):
        take(dyn_para(key, value), key)
    text = rep(text, ' The prior D-047 compression-only disposition and retained tension-development diagnostics are unchanged.</paragraph>',
               '</paragraph>', 'D-047 sentence')
    moved.append(para + 'The prior D-047 compression-only disposition and retained tension-development diagnostics are unchanged.</paragraph>')
    text = rep(text, para + 'Bearing basis: retain T019 / D-063 PierLevelSeatCheck and its signed rotations, saved analysis assumptions and '
               'limitations. Its conditional',
               para + 'Bearing basis: the pier level-seat check above (PierLevelSeatCheck) applies with its signed rotations, saved analysis '
               'assumptions and limitations. Its conditional', 'bearing basis sentence')
    take(para + 'Verification: six valid single-solid level pedestals, eight uniform level pads with pedestal contact, native elevation '
         'edit/restore and cage regeneration, protected original geometry/marks and saved-file reopen were checked. Native Blockpad '
         'recalculation, appearance review and engineering acceptance were not performed for this documentary addition. See T021 '
         'verification and CAD evidence/2026-10-20-level-bearing-seats.</paragraph>', 'verification paragraph')
    notes = hidden('AllLevelSeatOverrideNotes', nl.join(' ' * 4 + m for m in moved), nl, '')
    text = rep(text, '</section>' + nl + ' ' * 12 + para.replace('spacingafter="7"', 'spacingafter="5"') + 'Design scope: the Type F gravity',
               notes + nl + '</section>' + nl + ' ' * 12 + para.replace('spacingafter="7"', 'spacingafter="5"') + 'Design scope: the Type F gravity',
               'end of AllLevelSeatOverride')
    return multiline_cells(text)


def fence_wind(text):
    text = rep(text, 'We will retain this journal’s stated', 'These calculations retain the stated', 'C002 contract sentence')
    return multiline_cells(text)


def superstructure_uplift(text):
    text = rep(text, 'Bearing-pad and anchorage capacities are not defined in this journal.',
               'Bearing-pad and anchorage capacities are not defined in these calculations.', 'C004 journal sentence')
    return multiline_cells(text)


def pier_wall_fins(text):
    text = rep(text, 'existing FBMP loads and unrelated journal calculations are not changed.',
               'existing FBMP loads and unrelated calculations are not changed.', 'C006 journal sentence')
    return multiline_cells(text)


def ped_bridge(text):
    nl = nl_of(text)
    for target, old, new in INDEX_LABELS:
        text = rep(text, f'<link address="#{target}">{old}</link>', f'<link address="#{target}">{new}</link>', f'index label {target}')
    anchor = (' ' * 8 + '<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">Revision: 19 October 2026, '
              'end-bent backwall report added (T017):')
    note = ' ' * 8 + f'<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">{REVISION_NOTE}</paragraph>'
    return rep(text, anchor, note + nl + anchor, 'revision paragraph')


def decision_log(text):
    nl = nl_of(text)
    tail = ' ' * 8 + '</section>' + nl + ' ' * 4 + '</report>'
    assert text.endswith(tail), 'DecisionLog does not end with a section inside the report'
    assert f'name="{DECISION_SECTION}"' not in text
    entry = nl.join([' ' * 8 + f'<section name="{DECISION_SECTION}" capture="False" hide="false">',
                     ' ' * 12 + f'<heading level="1" keepwithnext="True">{DECISION_HEADING}</heading>',
                     ' ' * 12 + f'<paragraph fontfamily="{TNR}" fontsize="11" leftindent="0" spacingafter="7">{DECISION}</paragraph>',
                     ' ' * 8 + '</section>'])
    return text[:-len(' ' * 4 + '</report>') - len(nl)] + nl + entry + nl + ' ' * 4 + '</report>'


TRANSFORMS = {
    'MSEWallExclusion': mse_wall_exclusion, 'BearingDesign': bearing_design, 'FenceWind': fence_wind,
    'SuperstructureUplift': superstructure_uplift, 'PierWallFins': pier_wall_fins,
    'C001WindLoadOnPedBridgeSuperstructure': multiline_cells, 'BridgeMovement': multiline_cells,
    'PedBridge': ped_bridge, 'DecisionLog': decision_log,
}


def transform(name, text):
    return TRANSFORMS[name](text)
