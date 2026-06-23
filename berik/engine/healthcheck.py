"""Data-health pre-flight — the checks a BIM QA reviewer wants before release.

Each check returns a HealthFinding with a severity (red/amber/green/info), a count, and the
FULL list of affected items (never truncated — the UI makes it expandable/searchable).

v1 ships the domain-agnostic, high-value checks. V770 objektkode-codelist validation and
MMI-distribution are v2 (they need the project codelist + the MMI property name).
"""
from __future__ import annotations
import re
from collections import Counter

from .model import HealthFinding

# A Norwegian-infra TFM/RDS-style tag looks like  +N34VEE6RS=411.500-NK115
TAG_PATTERN = re.compile(r"^[+<].+[=].+[-.].+", re.UNICODE)
# mojibake / problem characters that break Norwegian text
SUSPECT_CHARS = ("Ã¥", "Ã¦", "Ã¸", "�", " ")  # å æ ø mojibake, replacement char, nbsp


def _finding(check, title, sev, items, detail=""):
    return HealthFinding(check=check, title=title, severity=sev,
                         count=len(items), items=sorted(set(items))[:5000], detail=detail)


def run_health(rows_by_tag, raw_tags, per_file_index, untagged_by_file, plan_changes_by_file,
               tag_discipline=None, loaded_stems=None):
    """Return list[HealthFinding]. `raw_tags` is every Excel tag incl. duplicates."""
    tag_discipline = tag_discipline or {}
    loaded_stems = set(loaded_stems or [])
    findings: list[HealthFinding] = []

    # 1. Duplicate tags in the Excel (same full tag in >1 row)
    dupes = [t for t, n in Counter(raw_tags).items() if n > 1]
    findings.append(_finding(
        "duplicate_tags", "Duplikate TFM-tagger i Excel",
        "amber" if dupes else "green", dupes,
        "Samme tag i flere rader — raden med mest data brukes." if dupes else "Ingen duplikater."))

    # 2. Malformed / suspicious tags
    malformed = [t for t in set(raw_tags) if not TAG_PATTERN.match(t) or len(t) > 80]
    findings.append(_finding(
        "malformed_tags", "Tagger med uventet format",
        "amber" if malformed else "green", malformed,
        "Tag matcher ikke forventet TFM/RDS-mønster." if malformed else "Alle tagger har gyldig form."))

    # 3. Encoding / whitespace problems in tags
    bad_chars = [t for t in set(raw_tags)
                 if any(s in t for s in SUSPECT_CHARS) or t != t.strip() or "  " in t]
    findings.append(_finding(
        "encoding", "Tegnsett- eller mellomrom-problemer",
        "amber" if bad_chars else "green", bad_chars,
        "Mojibake, hardt mellomrom eller dobbelt mellomrom oppdaget." if bad_chars else "Rent tegnsett."))

    # 4. Excel rows with no object anywhere (orphans) — scoped by Disiplinmodell so rows
    #    belonging to unloaded discipline files are NOT counted as errors.
    ifc_tags = set()
    for idx in per_file_index.values():
        ifc_tags |= set(idx)

    def in_scope(tag):
        disc = tag_discipline.get(tag)
        return (disc is None) or (not loaded_stems) or (disc in loaded_stems)

    excel_orphans = sorted(t for t in (set(rows_by_tag) - ifc_tags) if in_scope(t))
    other_files = sum(1 for t in set(rows_by_tag) if not in_scope(t))
    findings.append(_finding(
        "excel_orphans", "Excel-rader uten objekt i lastet modell",
        "amber" if excel_orphans else "green", excel_orphans,
        "Utstyr listet i Excel for en lastet fil, men ikke funnet som objekt." if excel_orphans
        else "Alle Excel-rader for de lastede filene har objekt."))
    if other_files:
        findings.append(HealthFinding(
            check="other_discipline_rows", title="Excel-rader for andre disiplinfiler",
            severity="info", count=other_files, items=[],
            detail=f"{other_files} rader hører til IFC-filer som ikke er lastet i denne kjøringen "
                   f"(forventet — én Excel mater hele settet på ~7 filer)."))

    # 5. Objects with no Excel row (incl. untagged)
    obj_orphans = []
    for fname, idx in per_file_index.items():
        for tag, objs in idx.items():
            if tag not in rows_by_tag:
                obj_orphans += [f"{fname}:{tag}"] * len(objs)
    untagged_total = sum(len(v) for v in untagged_by_file.values())
    sev = "amber" if (obj_orphans or untagged_total) else "green"
    findings.append(HealthFinding(
        check="object_orphans", title="Objekter uten Excel-rad",
        severity=sev, count=len(obj_orphans) + untagged_total,
        items=sorted(set(obj_orphans))[:5000],
        detail=f"{untagged_total} objekter uten tag (kontrollert unntaksliste) + "
               f"{len(obj_orphans)} objekter med tag som mangler Excel-rad."))

    # 6. Value-collision overwrites (object already had a different value)
    overwrites = []
    for fname, changes in plan_changes_by_file.items():
        for c in changes:
            if c.kind == "overwrite":
                overwrites.append(f"{c.tag} · {c.pset}.{c.prop}: '{c.old}' → '{c.new}'")
    findings.append(_finding(
        "overwrites", "Verdier som overskrives",
        "amber" if overwrites else "green", overwrites,
        "Objektet hadde allerede en annen verdi — kontroller før skriving." if overwrites
        else "Ingen eksisterende verdier overskrives."))

    # 7. Orphan / malformed document links
    bad_links = []
    for (tag), props in rows_by_tag.items():
        for (pset, prop), val in props.items():
            if pset == "D_Dokumentknyttinger" and val:
                if not (val.startswith("http://") or val.startswith("https://")):
                    bad_links.append(f"{tag} · {prop}: {val[:60]}")
    findings.append(_finding(
        "doc_links", "Dokumentlenker som ikke er gyldige URL-er",
        "amber" if bad_links else "green", bad_links,
        "Lenkefelt uten gyldig http(s)-URL." if bad_links else "Alle dokumentlenker er gyldige URL-er."))

    return findings
