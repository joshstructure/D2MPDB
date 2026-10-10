"""Presentation references verified against LRFD 10th ed. and FDOT January 2026.

Article references describe the basis of the existing calculation, not completion
of every provision in that article. Project screens retain their own attribution.
"""
from html import escape

LRFD = 'AASHTO LRFD BDS, 10th ed. (2024; September 2025 errata)'
SDG = 'FDOT Structures Manual, January 2026 — Vol. 1, SDG'
SDM = 'FDOT Structures Manual, January 2026 — Vol. 2, SDM'


def lrfd(locator, purpose):
    return LRFD, locator, purpose


def sdg(locator, purpose):
    return SDG, locator, purpose


def sdm(locator, purpose):
    return SDM, locator, purpose


CRACKING = (
    lrfd('Art. 5.6.7; Eqs. 5.6.7-1 and 5.6.7-2', 'Crack-control bar spacing and strain ratio'),
    lrfd('Art. 5.6.1', 'Service section-analysis assumptions'),
)
CLEARANCE = (
    lrfd('Arts. 5.10.3.1.1 and 5.10.3.1.3', 'Cast-in-place bar and multilayer clear spacing'),
    sdm('Arts. 4.3.2 and 4.3.4', 'Minimum spacing and reinforcement fit'),
)
SHRINKAGE = (
    lrfd('Art. 5.10.6; Eqs. 5.10.6-1 and 5.10.6-2', 'Surface reinforcement area and spacing'),
    sdm('Art. 4.3.1A', 'Shrinkage and temperature spacing reference'),
)
SHEAR = (
    lrfd('Art. 5.7.3.3; Eqs. 5.7.3.3-1 through 5.7.3.3-4', 'Nominal shear resistance, section limit, concrete and stirrup contributions'),
    lrfd('Arts. 5.7.2.8, 5.7.3.4.1 and 5.7.3.4.2', 'Effective shear depth and applicable β / θ procedure'),
    lrfd('Art. 5.5.4.2', 'Resistance factor'),
)
MIN_SHEAR = lrfd('Art. 5.7.2.5; Eq. 5.7.2.5-1', 'Minimum transverse reinforcement')
ACROSS = sdg('Art. 4.1.4C; Figure 4.1.4-1', 'Across-member spacing of stirrup legs')
WINDOW = sdg('Art. 4.1.4A; LRFD Figure C5.7.3.3-2', 'Actual stirrup area intersecting the shear-design window')
TORSION = (
    lrfd('Art. 5.7.2.1', 'Torsion investigation threshold and combined shear demand'),
    lrfd('Arts. 5.7.3.6.1 and 5.7.3.6.2; Eq. 5.7.3.6.2-1', 'Combined transverse steel and torsional resistance'),
    lrfd('Arts. 5.7.2.4 and 5.10.8.2.6d', 'Closed torsion reinforcement and closure anchorage'),
)
HOOKS = (
    lrfd('Art. 5.10.2.1; Table 5.10.2.3-1', 'Standard hook extensions and inside bend diameters'),
    sdm('Arts. 4.3.4 and 4.3.8', 'Hook fit, clearance, and orientation'),
)
DEVELOPMENT = (
    lrfd('Art. 5.10.8.2.1; Eqs. 5.10.8.2.1a-1 and 5.10.8.2.1a-2', 'Straight-bar tension development'),
    lrfd('Art. 5.10.8.2.4a; Eqs. 5.10.8.2.4a-1 and 5.10.8.2.4a-2', 'Hooked-bar development'),
)


def references_for(e, check):
    """Return (source, locator, purpose) entries plus any attribution qualifier."""
    key = check.key
    if key.startswith('Chk_end_grid_bend_'):
        return (lrfd('Art. 5.10.2.1', 'General reinforcing-bar minimum bend diameters'),), ''
    if key.startswith('Chk_end_grid_clear_'):
        return (lrfd('Art. 5.10.3.1.1', 'Parallel reinforcement clear spacing'),), 'The entered project clear spacing may govern.'
    if key in ('Chk_end_grid_fit','Chk_end_grid_collision'):
        return (sdm('Art. 4.3.4', 'Reinforcement fit and clearance'),), 'Drawn geometry screen, not a strength ratio or final fabrication check.'
    if key == 'Status_end_grid_anchorage':
        return (lrfd('Art. 5.10.8', 'Reinforcement development and anchorage'),), 'Entered U return lengths require separate development and pile-clearance review.'
    if key.startswith('Chk_fdot_bar_'):
        return (sdm('Art. 4.3.11', 'Minimum #4 cast-in-place bar; maximum #11 cap main bar and #6 stirrup'),), ''
    if key.startswith('Chk_fdot_cover_'):
        return (sdg('Art. 1.4.2; Table 1.4.2-1', 'Exterior substructure clear cover by environmental classification and face condition'),), 'This FDOT table replaces LRFD 5.10.1 for the modeled cover policy.'
    if key.startswith('Chk_flex_'):
        return (
            lrfd('Art. 5.6.3.2.1; Eq. 5.6.3.2.1-1', 'Factored flexural resistance Mr = φMn'),
            lrfd('Art. 5.6.3.2.3, using Eq. 5.6.3.2.2-1', 'Rectangular-section nominal flexural resistance'),
            lrfd('Arts. 5.6.2.1, 5.6.2.2 and 5.5.4.2', 'Section assumptions, concrete stress block, and resistance factor'),
        ), 'The displayed Mn relation is the nonprestressed, singly reinforced specialization.'
    if key.startswith('Chk_min_'):
        return (
            lrfd('Art. 5.6.3.3; Eq. 5.6.3.3-1', 'Minimum flexural resistance: lesser of 1.33Mu and the cracking criterion'),
            lrfd('Art. 5.4.2.6', 'Modulus of rupture'),
            sdg('Art. 4.1.5', 'Locations requiring the minimum-reinforcement check'),
        ), ''
    if key.startswith('Chk_strain_'):
        return (lrfd('Arts. 5.6.2.1 and 5.5.4.2', 'Strain compatibility and strain-dependent resistance factors'),), (
            'The fixed 0.005 criterion is the notebook screen for its adopted flexural factor; grade and section applicability remain part of the review.')
    if key.startswith(('Chk_I_', 'Chk_drawn_I_')):
        return CRACKING + (sdg('Art. 3.10F; see also Art. 4.1.8A', 'FDOT 0.80Fy service-stress limit for Fy < 75 ksi and exposure rules'),), ''
    if key == 'Status_III' or key.startswith('Chk_drawn_III_'):
        return (sdg('Art. 3.10A', 'Service III outer-layer tension limit of 24 ksi; live-load factor 0.8'),) + CRACKING, ''
    if key == 'Status_fatigue':
        return (
            lrfd('Art. 5.5.3.1; Eq. 5.5.3.1-1', 'Factored fatigue stress range versus threshold and applicability'),
            lrfd('Art. 5.5.3.2; Eq. 5.5.3.2-1', 'Straight reinforcing-bar fatigue threshold'),
            lrfd('Table 3.4.1-1; Art. 3.6.1.4', 'Fatigue I load factor and fatigue loading'),
        ), 'This row uses the straight-bar calculation; splice-specific fatigue is a separate review.'
    if key.startswith(('Chk_shear_', 'Chk_actual_shear_')):
        return SHEAR + ((WINDOW,) if e.lrfd else ()), ''
    if key.startswith(('Chk_spacing_', 'Chk_actual_pitch_')):
        return (
            lrfd('Art. 5.7.2.6; Eqs. 5.7.2.6-1 and 5.7.2.6-2', 'Maximum along-member transverse spacing'),
            MIN_SHEAR, ACROSS,
        ) + (() if e.lrfd else (lrfd('Art. 5.7.3.3; Eq. 5.7.3.3-4', 'Spacing required by shear strength'),)), ''
    if key.startswith('Chk_actual_min_'):
        return (MIN_SHEAR, WINDOW), ''
    if key.startswith('Chk_drawn_hoop_legs_'):
        return (ACROSS,), ''
    if key.startswith('Chk_torsteel_') or key == 'Status_actual_torsion':
        return TORSION, 'Open U-bars are not credited as closed torsion paths.'
    if key.startswith('Chk_long_'):
        return (
            lrfd('Art. 5.7.3.5; Eq. 5.7.3.5-1', 'Longitudinal reinforcement for moment, axial force, and shear'),
            lrfd('Art. 5.7.3.6.3; Eq. 5.7.3.6.3-1', 'Longitudinal reinforcement with investigated torsion'),
        ) + ((lrfd('Commentary C5.7.3.5', 'Developed steel and direct-loading treatment'),) if e.lrfd else ()), ''
    if key == 'Chk_skin_area':
        return (lrfd('Art. 5.6.7; Eq. 5.6.7-3', 'Skin reinforcement depth trigger, area, and distribution'),), ''
    if key == 'Chk_skin_space':
        return (lrfd('Art. 5.6.7', 'Skin reinforcement spacing: dℓ/6 and 12 in limits'),), ''
    if key in ('Chk_shrink_area', 'Chk_shrink_space', 'Chk_drawn_shrink_B'):
        return SHRINKAGE, 'Any smaller adopted surface-spacing limit is a project setting, shown separately from the code limit.'
    if key.startswith(('Chk_clear_', 'Chk_added_clear_', 'Chk_actual_clear_', 'Chk_hoop_clear_')):
        return CLEARANCE, 'The larger entered project clearance also applies.'
    if key.startswith('Chk_alignment_'):
        return (lrfd('Art. 5.10.3.1.3', 'Vertical alignment of bars in closely spaced layers'),), ''
    if key in ('Chk_added_fit', 'Chk_actual_longitudinal_fit'):
        return (sdm('Art. 4.3.4', 'Reinforcing fit and clearance'),), 'Geometric screen using entered cover and cage geometry; exposure-based cover selection is separate.'
    if key == 'Chk_hook_fit':
        return HOOKS, 'Fit screen only; development is checked separately.'
    if key in ('Chk_hook_cage', 'Chk_hook_pairs'):
        return CLEARANCE + HOOKS, 'Uses actual hook geometry and the adopted project clearance.'
    if key == 'Status_hook_development':
        return DEVELOPMENT + (
            lrfd('Art. 5.10.8.1.2', 'Flexural bar termination and extension'),
            sdm('Arts. 4.3.6 and 4.3.8', 'Embedment and hook detailing'),
        ), 'The cited cutoff and confinement requirements remain open where this row is pending.'
    if key == 'Status_continuous_anchorage':
        return (DEVELOPMENT[0],
            lrfd('Arts. 5.10.8.1.2 and 5.10.8.4', 'Support extensions, termination, and splices'),
            sdm('Art. 4.3.5', 'Splice detailing'),
        ), 'The splice-state readiness flag is a notebook gate, not a splice resistance equation.'
    if key.startswith('Status_transverse_development_'):
        return HOOKS + (
            lrfd('Arts. 5.10.8.2.6a and 5.10.8.2.6b; Eq. 5.10.8.2.6b-1', 'Stirrup anchorage, longitudinal-bar engagement, and embedment'),
            lrfd('Art. 5.10.8.2.6d', 'Closed-stirrup splice and lap requirements'),
            sdg('Art. 4.1.4B', 'Closed twin-leg stirrups and permitted open-stirrup locations'),
        ), 'Geometric and readiness flags are notebook checks; their numeric flags are not code D/C equations.'
    if key == 'Status_aggregate':
        return (CLEARANCE[0], sdm('Art. 4.3.2', 'Minimum bar spacing')), 'Aggregate confirmation is an input-readiness check.'
    if key == 'Chk_piles':
        return (
            lrfd('Art. 10.7.1.2', 'Pile spacing, clearance, and cap embedment provisions'),
            sdg('Art. 3.5.4', 'FDOT modification to minimum pile spacing'),
        ), 'This row checks spacing, entered edge allowance, and pile count; it does not verify pile-connection strength or minimum embedment.'
    if key == 'Status_pile_hoops':
        return (sdg('Art. 4.1.4B', 'Stirrup arrangement at pile heads'), sdm('Art. 4.3.4', 'Fit and clearance')), 'Actual arrangement and anchorage must be supplied.'
    if key == 'Status_actual_review':
        return (
            lrfd('Arts. 5.5.1.2.3, 5.7.1.2 and 5.8', 'D-region applicability and local load-path design'),
            sdg('Art. 4.1.4A–C', 'Shear reinforcement arrangement'),
            sdm('Art. 4.3.4', 'Fit and congestion review'),
        ), 'Review gate; no completed D-region resistance is assigned by this row.'
    if key == 'Status_lrfd_end_regions':
        return (
            lrfd('Arts. 5.7.3.2, 5.8 and 5.10.8.1.2', 'Support/end-region design and flexural anchorage'),
        ), 'Review gate for regions outside the transverse schedule.'
    if key == 'Status_lrfd_regions':
        return (lrfd('Art. 5.7.3.5; Commentary C5.7.3.5', 'Direct-loading treatment of longitudinal reinforcement'),), 'Eligibility requires the recorded project load path.'
    if key == 'Status_lrfd_strain':
        return (lrfd('Art. 5.7.3.4.2; Eqs. 5.7.3.4.2-1 through 5.7.3.4.2-4', 'Calculated shear parameters and longitudinal-strain treatment'),), 'No clipping or adopted resistance above 0.006. Simplified strain is not required.'
    if key in ('Status_signed_axial_source','Status_lrfd_search','Status_uniform_schedule'):
        return (lrfd('Arts. 5.7.3.4.2 and 5.7.3.5', 'Concurrent section actions and signed axial force'), WINDOW), 'Notebook source, convergence or station-placement readiness gate; not an additional code resistance equation.'
    if key == 'Status_lrfd_domain':
        return (
            lrfd('Arts. 5.1, 5.4.3.3, 5.7 and 5.10.8.2', 'Material and member applicability of shear and development provisions'),
        ), 'This is the notebook implementation-domain gate; its limits do not establish full FDOT material acceptance.'
    if key == 'Chk_actual_end':
        return (), 'Project/detailing screen: end distance ≤ half the tighter pitch limit. This is not a numbered LRFD end-region design equation.'
    if key in ('Chk_loads', 'Chk_bars', 'Chk_counts', 'Chk_geometry'):
        return (), 'Notebook input validation — no governing code equation. Valid input values alone do not establish code compliance.'
    if key in ('Status_layout', 'Status_section', 'Status_lrfd_source'):
        return (), 'Notebook analysis-source consistency check — no governing code equation.'
    if key == 'Status_overall':
        return (), 'Notebook summary of the individual checks — no single governing code equation.'
    return (), 'Code reference not assigned to this check; see its stated basis.'


def references_html(e, check):
    refs, note = references_for(e, check)
    sources = dict.fromkeys(ref[0] for ref in refs)
    groups = []
    for source in sources:
        items = ''.join('<li><b>'+escape(locator)+'</b> — '+escape(purpose)+'</li>'
                        for owner, locator, purpose in refs if owner == source)
        groups.append('<p>'+escape(source)+'</p><ul>'+items+'</ul>')
    if note:
        groups.append('<p>'+escape(note)+'</p>')
    return '<div class="check-references"><p><b>Code references</b></p>'+''.join(groups)+'</div>'
