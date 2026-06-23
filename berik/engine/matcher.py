"""Index IFC objects by their TFM Tag — one tag maps to MANY objects (one-to-many).

A tagged run (a cable, a trekkerør) is drawn as many proxy objects that all share the
same TFM Tag, so matching is row -> [objects]. We index in a single pass and never
re-scan per Excel row (the O(n^2) trap).
"""
from __future__ import annotations
from collections import defaultdict
import ifcopenshell
import ifcopenshell.util.element as ue

from .reader import KEY_PSET, KEY_PROP


def open_model(path):
    return ifcopenshell.open(str(path))


def index_by_tag(model, key_pset=KEY_PSET, key_prop=KEY_PROP):
    """Return (index, untagged).

    index:    {tfm_tag: [elements]}  (one-to-many)
    untagged: [elements with no tag]  (the controlled exception list)
    """
    index: dict[str, list] = defaultdict(list)
    untagged: list = []
    for el in model.by_type("IfcElement"):
        pset = ue.get_pset(el, key_pset)
        tag = None
        if pset:
            raw = pset.get(key_prop)
            if raw is not None and str(raw).strip():
                tag = str(raw).strip()
        if tag:
            index[tag].append(el)
        else:
            untagged.append(el)
    return index, untagged


def object_label(el):
    """Stable label for an object in reports: GlobalId + IFC class."""
    gid = getattr(el, "GlobalId", "?")
    return f"{gid}:{el.is_a()}"
