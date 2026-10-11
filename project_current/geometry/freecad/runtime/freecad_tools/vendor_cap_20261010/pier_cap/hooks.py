"""Straight extensions beyond the bend, not CRSI overall A/G dimensions.

CRSI Manual of Standard Practice, Table 7-2 (November 2019 errata),
also reproduced in CRSI's Spring 2024 product catalog, Desktop Reference Chart.
https://www.crsi.org/wp-content/uploads/CRSI_Product_Catalog_2024-Spring.pdf
Standard dimensions do not establish anchorage, engagement or seismic suitability.
"""

CRSI_HOOK_SOURCE = 'CRSI Table 7-2: straight stirrup/tie hook extensions'


def stirrup_hook_extension(bar, angle):
    """Inches after the bend; None means outside the CRSI #3–#8 table."""
    if bar not in range(3,9) or angle not in (0,90,135,180):return None
    db=bar/8.
    if angle==0:return 0.
    if angle==90:return max(6*db,3.) if bar<=5 else 12*db
    if angle==135:return max(6*db,3.)
    return max(4*db,2.5)
