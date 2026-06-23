"""End-to-end engine test against sample files + a reference answer key.

Run:  python3 tests/test_engine.py
Proves: analyze() produces correct dashboard/reconcile/health, and commit() reproduces
a reference 'beriket' file at 100% cell-match.
"""
import sys, pathlib, json
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from berik.engine import analyze, commit  # noqa: E402

SAMPLES = pathlib.Path(
    pathlib.Path(__file__).resolve().parent / "fixtures"  # drop sample IFC/xlsm here to run
)
EXCEL = SAMPLES / "equipment-list.xlsm"
BLANK = SAMPLES / "model_blank.ifc"
ANSWER = SAMPLES / "model_beriket.ifc"
OUT = ROOT / "tests" / "_out"


def main():
    print("=== ANALYZE (read-only) ===")
    a = analyze(EXCEL, [BLANK], progress=lambda m, f: None)
    print(f"  excel: {a.excel_name}")
    print(f"  mapping tab: {a.mapping.tab}  psets: {a.mapping.psets}")
    print(f"  completeness: {a.completeness_pct}%  RAG: {a.rag}")
    print(f"  totals: {json.dumps(a.totals, ensure_ascii=False)}")
    f0 = a.files[0]
    print(f"  file: objs={f0.objects_total} tagged={f0.objects_with_tag} "
          f"untagged={f0.objects_without_tag} uniq_tags={f0.unique_tags} "
          f"matched={f0.tags_matched} 1:many={f0.one_to_many_tags}")
    print(f"  changes: new={f0.changes_new} overwrite={f0.changes_overwrite} "
          f"unchanged={f0.changes_unchanged}")
    print(f"  reconciliation: excel_orphans={len(a.reconciliation.excel_orphans)} "
          f"ifc_orphans={a.reconciliation.ifc_orphans_count}")
    print("  health:")
    for h in a.health:
        print(f"    [{h.severity}] {h.title}: {h.count}  — {h.detail[:60]}")

    print("\n=== COMMIT (write + validate vs answer key) ===")
    result, _, _ = commit(EXCEL, [BLANK], OUT, approver="Jane Doe",
                          answer_key=ANSWER, progress=lambda m, f: None)
    w = result.written_files[0]
    print(f"  wrote: {w['output']}  objects_enriched={w['objects_enriched']}")
    v = result.validation
    print(f"  VALIDATION: {v['match_pct']}% exact "
          f"({v['cells_exact_match']} ok / {v['cells_value_diff']} diff / "
          f"{v['cells_we_missed']} missed / {v['cells_extra_vs_key']} extra)")
    assert v["match_pct"] == 100.0 and v["cells_value_diff"] == 0 and v["cells_we_missed"] == 0, \
        "REGRESSION: no longer reproduces the answer key exactly"
    print("\n  PASS — engine reproduces the reference output exactly.")
    # clean the heavy output
    for p in OUT.glob("*.ifc"):
        p.unlink()


if __name__ == "__main__":
    main()
