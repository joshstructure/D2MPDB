"""Original mechanics fixture, explicitly without a protruding pile head.

This preserves the original Mathcad/C005 arithmetic regression independently
of the new pile-interference cases. It is not the notebook's starting design.
"""
from pier_cap.model import default_case as unconfirmed_case, set_inputs
from pier_cap.fbmp import import_fbmp_xml as import_xml


def default_case():
    return set_inputs(unconfirmed_case(),Ready_pile=True,Pile_embed=0,C_pile=0)


def import_fbmp_xml(source, **kwargs):
    kwargs.setdefault('base',default_case())
    return import_xml(source,**kwargs)
