"""Validate our output against a known-good reference ('beriket' file).

Cell-by-cell property comparison keyed on the TFM tag. This is the trust feature: a user
can point Berik at a known-good reference file and watch it report an exact match — proving the
in-house tool reproduces the paid vendor before they rely on it.
"""
from __future__ import annotations
from collections import defaultdict
import ifcopenshell

from .reader import KEY_PSET, KEY_PROP


def _props_by_tag(model):
    out = defaultdict(dict)
    for el in model.by_type("IfcElement"):
        tag = None
        bag = {}
        for rel in getattr(el, "IsDefinedBy", []):
            if rel.is_a("IfcRelDefinesByProperties"):
                pdef = rel.RelatingPropertyDefinition
                if pdef.is_a("IfcPropertySet"):
                    for pr in pdef.HasProperties:
                        if pr.is_a("IfcPropertySingleValue"):
                            val = pr.NominalValue.wrappedValue if pr.NominalValue else None
                            bag[(pdef.Name, pr.Name)] = (str(val).strip() if val is not None else None)
                            if pdef.Name == KEY_PSET and pr.Name == KEY_PROP and val:
                                tag = str(val).strip()
        if tag:
            out[tag] = bag
    return out


def compare(our_ifc, answer_key):
    ours = _props_by_tag(ifcopenshell.open(str(our_ifc)))
    theirs = _props_by_tag(ifcopenshell.open(str(answer_key)))
    keys = set(ours) & set(theirs)
    ok = diff = missing = extra = 0
    samples = []
    for tag in keys:
        o, t = ours[tag], theirs[tag]
        for k, tv in t.items():
            if tv is None:
                continue
            ov = o.get(k)
            if ov is None:
                missing += 1
                if len(samples) < 25: samples.append(f"MISSING {tag} {k[0]}::{k[1]} (want '{tv}')")
            elif ov == tv:
                ok += 1
            else:
                diff += 1
                if len(samples) < 25: samples.append(f"DIFF {tag} {k[0]}::{k[1]}: ours='{ov}' theirs='{tv}'")
        for k, ov in o.items():
            if ov is not None and k not in t:
                extra += 1
    total = ok + diff + missing
    return {
        "tags_compared": len(keys),
        "cells_exact_match": ok,
        "cells_value_diff": diff,
        "cells_we_missed": missing,
        "cells_extra_vs_key": extra,
        "match_pct": round(100 * ok / total, 2) if total else 0.0,
        "sample_diffs": samples,
    }
