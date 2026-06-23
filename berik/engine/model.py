"""Typed result objects shared across the engine and the UI bridge.

Everything the UI renders is one of these dataclasses, serialised with `to_dict()`.
Keep them JSON-friendly: primitives, lists, dicts only.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional


# --------------------------------------------------------------------- mapping
@dataclass
class ColumnSpec:
    """One Excel column routed to one IFC property."""
    col_index: int
    pset: str
    prop: str
    source_label: str           # the raw header as written in the sheet
    include: bool = True        # user can toggle a column off in the mapping table


@dataclass
class Mapping:
    """The Excel→IFC column map, parsed from the sheet and user-tunable."""
    tab: str
    key_pset: str
    key_prop: str
    columns: list[ColumnSpec] = field(default_factory=list)

    @property
    def psets(self) -> list[str]:
        return sorted({c.pset for c in self.columns if c.include})

    def active(self) -> list[ColumnSpec]:
        return [c for c in self.columns if c.include]

    def to_dict(self):
        return {
            "tab": self.tab,
            "key": f"{self.key_pset}.{self.key_prop}",
            "psets": self.psets,
            "columns": [asdict(c) for c in self.columns],
        }


# --------------------------------------------------------------- change / diff
@dataclass
class Change:
    """A single property write that WILL happen (dry-run) or DID happen (commit)."""
    tag: str
    pset: str
    prop: str
    old: Optional[str]
    new: str
    kind: str                   # "new" | "overwrite" | "unchanged"

    def to_dict(self):
        return asdict(self)


# ------------------------------------------------------------- health findings
SEV_ORDER = {"red": 0, "amber": 1, "green": 2, "info": 3}


@dataclass
class HealthFinding:
    check: str                  # short id, e.g. "duplicate_tags"
    title: str                  # human title (Norwegian)
    severity: str               # "red" | "amber" | "green" | "info"
    count: int
    detail: str = ""
    items: list[str] = field(default_factory=list)   # affected tags / rows (full, never truncated)

    def to_dict(self):
        return asdict(self)


# ------------------------------------------------------------- per-file result
@dataclass
class FileAnalysis:
    file: str
    schema: str
    objects_total: int
    objects_with_tag: int
    objects_without_tag: int
    unique_tags: int
    tags_matched: int
    tags_no_excel_row: int
    objects_enriched: int       # objects that will receive >=1 property
    changes_new: int
    changes_overwrite: int
    changes_unchanged: int
    one_to_many_tags: int       # tags that map to >1 object
    sample_changes: list[dict] = field(default_factory=list)
    untagged_objects: list[str] = field(default_factory=list)   # IfcGlobalId list
    tags_no_row_list: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


# ----------------------------------------------------------- reconciliation
@dataclass
class Reconciliation:
    excel_rows_total: int
    excel_rows_matched: int             # rows that hit >=1 object across the batch
    excel_orphans: list[str]            # IN-SCOPE rows with no object (real orphans)
    excel_rows_other_files: int         # rows whose Disiplinmodell names an unloaded file
    ifc_objects_total: int
    ifc_objects_matched: int
    ifc_orphans_count: int              # objects with no excel row (incl. untagged)
    ifc_orphans_sample: list[dict] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


# ----------------------------------------------------------------- whole run
@dataclass
class Analysis:
    """The full pre-commit picture the sign-off screen renders. No writes have happened."""
    excel_name: str
    mapping: Mapping
    files: list[FileAnalysis]
    reconciliation: Reconciliation
    health: list[HealthFinding]
    completeness_pct: float
    rag: str                            # "green" | "amber" | "red"
    totals: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "excel_name": self.excel_name,
            "mapping": self.mapping.to_dict(),
            "files": [f.to_dict() for f in self.files],
            "reconciliation": self.reconciliation.to_dict(),
            "health": [h.to_dict() for h in self.health],
            "completeness_pct": self.completeness_pct,
            "rag": self.rag,
            "totals": self.totals,
        }


@dataclass
class CommitResult:
    approver: str
    timestamp: str
    out_dir: str
    written_files: list[dict]           # {source, output, objects_enriched}
    report_html: Optional[str] = None
    report_xlsx: Optional[str] = None
    validation: Optional[dict] = None   # if an answer key was supplied
    ids: Optional[dict] = None          # buildingSMART IDS acceptance-gate result

    def to_dict(self):
        return asdict(self)
