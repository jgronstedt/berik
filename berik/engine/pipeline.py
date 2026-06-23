"""Orchestrate a run: analyze (read-only, for the sign-off screen) and commit (write).

The split mirrors the product's safety promise — nothing is written until the user has seen
the full picture and approved it.
"""
from __future__ import annotations
import pathlib
from datetime import datetime, timezone

from . import reader, enrich, reconcile as reconcile_mod, healthcheck, validate as validate_mod
from . import idscheck
from .matcher import open_model
from .model import Analysis, CommitResult


def _apply_excludes(mapping, excluded):
    """excluded: iterable of [pset, prop] pairs to turn off."""
    ex = {(p, q) for p, q in (excluded or [])}
    for c in mapping.columns:
        if (c.pset, c.prop) in ex:
            c.include = False
    return mapping


def _rag(pct):
    return "green" if pct >= 98 else ("amber" if pct >= 90 else "red")


def analyze(excel_path, ifc_paths, tab=None, excluded=None, progress=None):
    """Read-only. Returns an Analysis describing exactly what a commit would do."""
    def tick(msg, frac):
        if progress:
            progress(msg, frac)

    excel_path = pathlib.Path(excel_path)
    ifc_paths = [pathlib.Path(p) for p in ifc_paths]

    tick("Leser Excel-listen…", 0.05)
    mapping, rows_by_tag, tag_discipline = reader.read_workbook(excel_path, tab)
    _apply_excludes(mapping, excluded)
    raw_tags = reader.raw_tag_rows(excel_path, mapping.tab)
    loaded_stems = {reader.normalize_stem(p.name) for p in ifc_paths}

    files, per_file_index, untagged_by_file, plan_by_file = [], {}, {}, {}
    n = max(len(ifc_paths), 1)
    for i, p in enumerate(ifc_paths):
        tick(f"Analyserer {p.name}…", 0.1 + 0.7 * i / n)
        model = open_model(p)
        changes, fa, index = enrich.plan_changes(model, rows_by_tag, mapping)
        fa.file = p.name
        files.append(fa)
        per_file_index[p.name] = index
        untagged_by_file[p.name] = [
            el for el in model.by_type("IfcElement")
            if not any(
                rel.is_a("IfcRelDefinesByProperties")
                and rel.RelatingPropertyDefinition.is_a("IfcPropertySet")
                and rel.RelatingPropertyDefinition.Name == mapping.key_pset
                and any(pr.Name == mapping.key_prop and pr.NominalValue and pr.NominalValue.wrappedValue
                        for pr in rel.RelatingPropertyDefinition.HasProperties)
                for rel in getattr(el, "IsDefinedBy", [])
            )
        ]
        plan_by_file[p.name] = changes

    tick("Avstemmer Excel mot modell…", 0.85)
    recon = reconcile_mod.reconcile(rows_by_tag, per_file_index, untagged_by_file,
                                    tag_discipline, loaded_stems)

    tick("Kjører datakvalitetssjekker…", 0.92)
    health = healthcheck.run_health(rows_by_tag, raw_tags, per_file_index,
                                    untagged_by_file, plan_by_file,
                                    tag_discipline, loaded_stems)

    # completeness = tagged objects that received their data / all tagged objects
    objs_with_tag = sum(f.objects_with_tag for f in files)
    objs_enriched = sum(f.objects_enriched for f in files)
    pct = round(100 * objs_enriched / objs_with_tag, 2) if objs_with_tag else 0.0

    totals = {
        "files": len(files),
        "objects_total": sum(f.objects_total for f in files),
        "objects_with_tag": objs_with_tag,
        "objects_without_tag": sum(f.objects_without_tag for f in files),
        "objects_enriched": objs_enriched,
        "changes_new": sum(f.changes_new for f in files),
        "changes_overwrite": sum(f.changes_overwrite for f in files),
        "tags_matched": sum(f.tags_matched for f in files),
        "excel_orphans": len(recon.excel_orphans),
        "ifc_orphans": recon.ifc_orphans_count,
    }
    tick("Klar.", 1.0)
    return Analysis(
        excel_name=excel_path.name, mapping=mapping, files=files,
        reconciliation=recon, health=health,
        completeness_pct=pct, rag=_rag(pct), totals=totals,
    )


def commit(excel_path, ifc_paths, out_dir, approver, tab=None, excluded=None,
           answer_key=None, ids_path=None, progress=None, tool_version="1.0"):
    """Write enriched copies of each IFC + return a CommitResult. Source files untouched."""
    def tick(msg, frac):
        if progress:
            progress(msg, frac)

    excel_path = pathlib.Path(excel_path)
    ifc_paths = [pathlib.Path(p) for p in ifc_paths]
    out_dir = pathlib.Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)

    tick("Leser Excel-listen…", 0.03)
    mapping, rows_by_tag, _ = reader.read_workbook(excel_path, tab)
    _apply_excludes(mapping, excluded)

    written = []
    n = max(len(ifc_paths), 1)
    for i, p in enumerate(ifc_paths):
        tick(f"Beriker {p.name}…", 0.05 + 0.8 * i / n)
        out_path, enriched = enrich.write_model(p, rows_by_tag, mapping, out_dir)
        rec = {"source": p.name, "output": out_path.name, "objects_enriched": enriched}
        if answer_key:
            rec["validation"] = validate_mod.compare(out_path, answer_key)
        written.append((rec, out_path))

    # buildingSMART IDS acceptance gate on the written output(s).
    tick("Kjører IDS-validering…", 0.9)
    first_out = written[0][1] if written else None
    ids_result = None
    if first_out is not None:
        ids_result = (idscheck.project_gate(first_out, ids_path) if ids_path
                      else idscheck.auto_gate(first_out))

    written_recs = [r for r, _ in written]
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    result = CommitResult(
        approver=approver, timestamp=ts, out_dir=str(out_dir),
        written_files=written_recs,
        validation=(written_recs[0].get("validation") if (answer_key and written_recs) else None),
        ids=ids_result,
    )
    tick("Ferdig.", 1.0)
    return result, mapping, rows_by_tag
