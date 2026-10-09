"""Solid force traces with vertical jumps only at shared stations."""
import math

DEMAND='#1463ad'
DEMAND_LOWER='#49358b'
RESISTANCE='#c54a00'
THRESHOLD='#414a53'


def joined_trace(points):
    """Join touching segments, retaining both sides and their hover records.

    Input None marks a segment boundary. Only coincident endpoint stations
    remove that break; a missing span remains a gap, never an interpolation.
    """
    x=[];y=[];custom=[];boundary=False
    for point in points:
        if point is None:
            boundary=True
            continue
        station,value,detail=point
        if boundary and x:
            if math.isclose(station,x[-1],rel_tol=0,abs_tol=1e-9):
                station=x[-1]  # Normalize roundoff so the connection is vertical.
            else:
                x.append(None);y.append(None);custom.append(None)
        x.append(station);y.append(value);custom.append(detail)
        boundary=False
    return x,y,custom
