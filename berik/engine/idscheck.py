"""IDS acceptance gate (buildingSMART Information Delivery Specification).

Two modes, both via ifctester:
  * auto gate    — Berik generates a minimal IDS ("every proxy must carry its TFM Tag") and
                   validates the output, so the QC report speaks the buildingSMART standard.
  * project IDS  — if the client issued a `.ids`, validate against THEIR requirements (the way
                   mature Statens vegvesen / Nye Veier delivery actually works).

Everything is wrapped defensively: an ifctester hiccup must never break a commit.
"""
from __future__ import annotations
from .reader import KEY_PSET, KEY_PROP


def _summarise(specs):
    out = []
    overall_pass = True
    for sp in specs.specifications:
        passed = list(getattr(sp, "passed_entities", []) or [])
        failed = list(getattr(sp, "failed_entities", []) or [])
        if failed:
            overall_pass = False
        fail_ids = []
        for e in failed[:500]:
            gid = getattr(e, "GlobalId", None) or getattr(e, "Name", None) or str(e)
            fail_ids.append(str(gid))
        out.append({
            "name": getattr(sp, "name", "spec"),
            "passed": len(passed),
            "failed": len(failed),
            "status": not failed,
            "failed_ids": fail_ids,
        })
    return {"status": overall_pass, "specs": out}


def auto_gate(ifc_path):
    """Generate + run a minimal IDS: every IfcBuildingElementProxy must carry the TFM Tag."""
    try:
        from ifctester import ids
        import ifcopenshell
        specs = ids.Ids(title="Berik QC — påkrevd identifikasjon")
        spec = ids.Specification(name=f"Hvert objekt har {KEY_PSET}.{KEY_PROP}")
        spec.applicability.append(ids.Entity(name="IFCBUILDINGELEMENTPROXY"))
        spec.requirements.append(
            ids.Property(propertySet=KEY_PSET, baseName=KEY_PROP,
                         dataType="IFCLABEL", cardinality="required"))
        specs.specifications.append(spec)
        model = ifcopenshell.open(str(ifc_path))
        specs.validate(model)
        res = _summarise(specs)
        res["source"] = "auto"
        return res
    except Exception as e:  # never break a commit on a validation hiccup
        return {"status": None, "specs": [], "source": "auto", "error": str(e)}


def project_gate(ifc_path, ids_path):
    """Validate the output against a client-supplied project IDS file."""
    try:
        from ifctester import ids
        import ifcopenshell
        specs = ids.open(str(ids_path))
        model = ifcopenshell.open(str(ifc_path))
        specs.validate(model)
        res = _summarise(specs)
        res["source"] = "project"
        res["ids_file"] = str(ids_path)
        return res
    except Exception as e:
        return {"status": None, "specs": [], "source": "project", "error": str(e)}
