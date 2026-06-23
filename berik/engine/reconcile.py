"""Two-way reconciliation across the whole batch.

Both directions, because each catches a different real error:
  * Excel rows with NO object in ANY file  -> equipment listed but not modelled (or a typo'd tag)
  * IFC objects with NO Excel row           -> modelled but undocumented (incl. untagged objects)

The match is computed across the full set of files, since one Excel feeds the ~7-file batch
and an "orphan" only counts if it matches nothing anywhere.
"""
from __future__ import annotations
from .matcher import object_label
from .model import Reconciliation


def reconcile(rows_by_tag, per_file_index, untagged_by_file, tag_discipline=None, loaded_stems=None):
    """per_file_index: {filename: {tag: [objects]}}; untagged_by_file: {filename: [objects]}.

    Orphan-counting is scoped by Disiplinmodell: an Excel row is only a real orphan if it
    belongs to a LOADED discipline file. Rows naming unloaded files are reported separately,
    so a single-file run doesn't falsely flag the other disciplines' rows as errors.
    """
    tag_discipline = tag_discipline or {}
    loaded_stems = set(loaded_stems or [])
    excel_tags = set(rows_by_tag)
    ifc_tags = set()
    ifc_objects_total = 0
    for idx in per_file_index.values():
        ifc_tags |= set(idx)
        ifc_objects_total += sum(len(v) for v in idx.values())
    untagged_total = sum(len(v) for v in untagged_by_file.values())
    ifc_objects_total += untagged_total

    def in_scope(tag):
        disc = tag_discipline.get(tag)
        return (disc is None) or (not loaded_stems) or (disc in loaded_stems)

    other_files = sum(1 for t in excel_tags if not in_scope(t))
    excel_orphans = sorted(t for t in (excel_tags - ifc_tags) if in_scope(t))
    matched_tags = excel_tags & ifc_tags

    # objects with no excel row = objects under a tag with no row + all untagged objects
    ifc_orphan_objs = []
    for fname, idx in per_file_index.items():
        for tag, objs in idx.items():
            if tag not in rows_by_tag:
                for o in objs:
                    ifc_orphan_objs.append({"file": fname, "object": object_label(o), "tag": tag})
    for fname, objs in untagged_by_file.items():
        for o in objs:
            ifc_orphan_objs.append({"file": fname, "object": object_label(o), "tag": None})

    ifc_matched_objs = ifc_objects_total - len(ifc_orphan_objs)

    return Reconciliation(
        excel_rows_total=len(excel_tags),
        excel_rows_matched=len(matched_tags),
        excel_orphans=excel_orphans,
        excel_rows_other_files=other_files,
        ifc_objects_total=ifc_objects_total,
        ifc_objects_matched=ifc_matched_objs,
        ifc_orphans_count=len(ifc_orphan_objs),
        ifc_orphans_sample=ifc_orphan_objs[:500],
    )
