"""ACI-style breakout geometry used as a trial transfer-region construction.

The 1.5 H:1 V projection (approximately 35 degrees) is the CCD breakout
envelope, not a compression spread rule or a verified annular-ring capacity.
Source: ACI 2023 Worsfold/Moehle/Silva webinar, slide 2 (ACI 318-19 diagram).
"""
from math import atan, degrees, hypot

ACI_SOURCE='https://www.concrete.org/portals/0/files/pdf/webinars/ws_F23_Worsford.pdf'


def geometry(case):
    slope=case.get('cone_slope_hv',1.5)
    radius=case['ring_od_in']/2
    face=case['thickness_in']/2
    clear=face-radius
    rise=max(0.,clear/slope)
    tol=case['placement_tolerance_in']
    end=(case['length_in']-(case['pile_count']-1)*case['pile_spacing_in'])/2
    return dict(enabled=case.get('support_model','ring_centers')=='face_transfer',
                slope_hv=slope,angle_deg=degrees(atan(1/slope)),ring_radius_in=radius,
                face_distance_in=face,radial_gap_in=clear,face_rise_in=rise,
                near_face_rise_in=max(0.,(clear-tol)/slope),far_face_rise_in=max(0.,(clear+tol)/slope),
                end_first_rise_in=max(0.,(end-radius)/slope),end_truncated=end<face,
                enclosed=clear>0,source=ACI_SOURCE)


def transfer_forces(reaction, case, cone):
    """Equilibrate a symmetric pair of trial ring-to-face compression links.

Each broad-face resultant receives half the ring reaction. A transverse tie
closes the spreading force. These are demands only: nodes lie on reference
face planes, lack cover/finite area, and tie routing must avoid the hollow pipe.
The existing longitudinal end couple remains a separate unresolved demand.
"""
    rise=cone['face_rise_in']+case['tie_offset_in']
    gap=max(0.,cone['radial_gap_in'])
    vertical=reaction/2
    horizontal=vertical*gap/rise if rise>0 else 0.
    return dict(face_vertical_kip=vertical,link_compression_kip=hypot(vertical,horizontal),
                transverse_tie_kip=horizontal,transverse_area_req_in2=horizontal/(case['phi_tie']*case['fy_ksi']),
                link_rise_in=rise,link_run_in=gap,
                vertical_residual_kip=2*vertical-reaction,
                status='PENDING — force demands only; finite nodes and tie anchorage unresolved')
