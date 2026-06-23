"""Dry-run the enrichment (compute what WILL change) and commit it (write to a copy).

Two phases, deliberately separate — this is the product's core safety promise:
  * plan_changes(): reads only. Returns every property write that would happen, classified
    new / overwrite / unchanged, so the sign-off screen can show the truth of the write.
  * write_model(): applies the plan to a COPY of the IFC. The source file is never touched.

All values are written as IfcLabel (matches the upstream tool's output). Existing Psets are
reused, not duplicated. Writes are batched for speed on large models.
"""
from __future__ import annotations
import pathlib
import ifcopenshell
import ifcopenshell.api.pset
import ifcopenshell.util.element as ue

from .matcher import index_by_tag
from .model import Change, FileAnalysis


def _current_value(el, pset_name, prop):
    pset = ue.get_pset(el, pset_name)
    if not pset:
        return None
    v = pset.get(prop)
    return None if v is None else str(v)


def _existing_pset_entity(el, name):
    """Return the IfcPropertySet entity on `el` with this name, or None (no duplicates)."""
    for rel in getattr(el, "IsDefinedBy", []):
        if rel.is_a("IfcRelDefinesByProperties"):
            pdef = rel.RelatingPropertyDefinition
            if pdef.is_a("IfcPropertySet") and pdef.Name == name:
                return pdef
    return None


def plan_changes(model, rows_by_tag, mapping):
    """Read-only. Return (changes, file_analysis-ish dict) for one model.

    changes: list[Change] across all matched objects.
    """
    index, untagged = index_by_tag(model, mapping.key_pset, mapping.key_prop)
    active = mapping.active()

    changes: list[Change] = []
    matched_tags = 0
    no_row_tags: list[str] = []
    objects_enriched = 0
    one_to_many = 0
    n_new = n_over = n_same = 0

    for tag, objs in index.items():
        if len(objs) > 1:
            one_to_many += 1
        row = rows_by_tag.get(tag)
        if row is None:
            no_row_tags.append(tag)
            continue
        matched_tags += 1
        for el in objs:
            touched = False
            for col in active:
                key = (col.pset, col.prop)
                if key not in row:
                    continue
                newv = row[key]
                oldv = _current_value(el, col.pset, col.prop)
                if oldv is None:
                    kind = "new"; n_new += 1
                elif oldv != newv:
                    kind = "overwrite"; n_over += 1
                else:
                    kind = "unchanged"; n_same += 1
                if kind != "unchanged":
                    touched = True
                changes.append(Change(tag=tag, pset=col.pset, prop=col.prop,
                                      old=oldv, new=newv, kind=kind))
            if touched:
                objects_enriched += 1

    schema = model.schema
    fa = FileAnalysis(
        file="",                       # filled by caller
        schema=schema,
        objects_total=len(model.by_type("IfcElement")),
        objects_with_tag=sum(len(v) for v in index.values()),
        objects_without_tag=len(untagged),
        unique_tags=len(index),
        tags_matched=matched_tags,
        tags_no_excel_row=len(no_row_tags),
        objects_enriched=objects_enriched,
        changes_new=n_new,
        changes_overwrite=n_over,
        changes_unchanged=n_same,
        one_to_many_tags=one_to_many,
        sample_changes=[c.to_dict() for c in changes if c.kind != "unchanged"][:200],
        untagged_objects=[getattr(e, "GlobalId", "?") for e in untagged],
        tags_no_row_list=no_row_tags,
    )
    return changes, fa, index


def write_model(src_path, rows_by_tag, mapping, out_dir):
    """Apply the plan to a COPY of the IFC. Returns (output_path, objects_enriched)."""
    src_path = pathlib.Path(src_path)
    out_dir = pathlib.Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    model = ifcopenshell.open(str(src_path))

    index, _ = index_by_tag(model, mapping.key_pset, mapping.key_prop)
    active = mapping.active()
    objects_enriched = 0

    model.begin_transaction() if hasattr(model, "begin_transaction") else None
    try:
        model.batch()
    except Exception:
        pass

    for tag, objs in index.items():
        row = rows_by_tag.get(tag)
        if not row:
            continue
        # group the row's writes by target Pset
        by_pset: dict[str, dict[str, str]] = {}
        for col in active:
            key = (col.pset, col.prop)
            if key in row:
                by_pset.setdefault(col.pset, {})[col.prop] = row[key]
        if not by_pset:
            continue
        for el in objs:
            wrote = False
            for pset_name, kv in by_pset.items():
                pset = _existing_pset_entity(el, pset_name)
                if pset is None:
                    pset = ifcopenshell.api.pset.add_pset(model, product=el, name=pset_name)
                props = {k: model.create_entity("IfcLabel", v) for k, v in kv.items()}
                ifcopenshell.api.pset.edit_pset(model, pset=pset, properties=props)
                wrote = True
            if wrote:
                objects_enriched += 1

    try:
        model.unbatch()
    except Exception:
        pass

    stem = src_path.stem
    for suf in ("_blank", "_uten_data", "_clean"):
        if stem.lower().endswith(suf):
            stem = stem[: -len(suf)]
            break
    out_path = out_dir / f"{stem}_beriket.ifc"
    model.write(str(out_path))
    return out_path, objects_enriched
