# Berik — Excel → IFC metadata enrichment

> *Berik* is Norwegian for "enrich". A local desktop app that writes metadata from an Excel
> equipment list onto the right objects inside one or more IFC models, with a real QA dashboard
> and a sign-off gate. Built by GRAIL.

It replaces a manual, multi-step enrichment workflow (export the Excel to CSV, delete every
zero by hand, upload it plus the IFC to a separate tool, download the enriched model) with one
local app: it reads the `.xlsm` directly. **No CSV step, no upload, files never leave the
machine.**

Validated cell-by-cell against a known-good reference model, Berik reproduces the expected
enriched output **100% exact** (5 400 cells, 0 diffs).

---

## What makes it good (not just functional)

- **The sign-off screen** — before anything is written, you see the *truth of the write*:
  every value (`object-tag · Pset.Property: (empty) → 'value'`), the two-way reconciliation,
  a RAG completeness score, the data-health checks. Then you approve. Most tools write blind or
  check without writing; Berik shows the pre-commit diff.
- **Write-to-copy, always** — the source IFC is never touched. Berik writes `_beriket` copies.
- **One-to-many matching** — a tag is drawn as many proxy objects; Berik writes the row to
  every object sharing the tag (the match logic an engineer gets wrong by hand).
- **Discipline-scoped reconciliation** — one Excel feeds several discipline IFCs; Berik scopes
  "orphan" counting by the discipline-model column so a single-file run doesn't cry wolf.
- **Data-health pre-flight** — duplicate tags, malformed tags, encoding problems, both-way
  orphans, value-collisions, bad document links — each fully listed and searchable.
- **A delivery-grade QC report** — a branded, print-to-PDF HTML record + an Excel data workbook,
  ready to attach to the project portal.
- **Validate against a reference** — point Berik at a known-good reference file and it reports
  the exact match, building trust before the team relies on it.

---

## Architecture

```
berik/
  app.py                 pywebview entry — the Api class bridged to the UI
  berik/
    engine/              pure Python, no UI (fully unit-testable)
      reader.py          read .xlsm directly; parse the CSV-tab Pset::Property map; clean/dedup
      matcher.py         index IFC objects by tag (one-to-many)
      enrich.py          plan_changes() = dry-run diff;  write_model() = write to a copy
      reconcile.py       two-way reconciliation, scoped by discipline model
      healthcheck.py     the data-health checks
      validate.py        cell-by-cell compare vs a reference file
      pipeline.py        analyze() (read-only) + commit() (write) — maps to the UI flow
      model.py           typed result objects (JSON-serialisable for the UI)
    report.py            QC report: branded HTML + Excel
    ui/                  index.html + app.css + app.js (vanilla, offline) + assets/ (logos)
  build/app.spec         PyInstaller spec (onedir)
  .github/workflows/     windows-build.yml — builds the .exe on a Windows runner
  tests/                 test_engine.py (asserts 100% vs a reference), qa_render.py (screenshots)
```

**Deterministic core, AI nowhere in the write path.** The match key is clean by design, so v1
is pure ETL.

---

## Run locally (development, macOS/Windows/Linux)

```bash
pip install -r requirements.txt
python3 app.py                 # opens the native window
python3 tests/test_engine.py   # engine regression: asserts 100% reproduction of a reference
python3 tests/qa_render.py     # screenshots every screen + the report (needs playwright)
```

The engine alone (no UI):

```python
from berik.engine import analyze, commit
a = analyze("equipment.xlsm", ["model_blank.ifc"])          # read-only; inspect a.to_dict()
result, _, _ = commit("equipment.xlsm", ["model_blank.ifc"], "out/", approver="Jane Doe")
```

## Build the Windows .exe

PyInstaller cannot cross-build, so the `.exe` is produced on a **Windows runner**:

- Push a `v*` tag (or run the `build-windows` workflow manually). It pip-installs, runs
  `pyinstaller build/app.spec`, and uploads **`Berik-win64.zip`** as a workflow artifact.
- Or, on any Windows machine: `pip install -r requirements.txt pyinstaller` then
  `pyinstaller build/app.spec --noconfirm` → `dist/Berik/`.

### How a user receives and runs it
1. Download `Berik-win64.zip`.
2. Unzip anywhere in the user folder (Desktop, Documents) — **no installer, no admin**.
3. Double-click `Berik.exe`.

`onedir` (not `onefile`) avoids per-launch temp extraction — faster start, fewer Defender/
SmartScreen flags. WebView2 is present on Windows 11 and almost all Windows 10; the first run
self-installs the ~2 MB runtime per-user if missing.

> **Code signing:** an unsigned exe may show a SmartScreen "unknown publisher" prompt and could
> be quarantined by corporate IT. An OV code-signing certificate (~$250/yr) removes this. The
> `signtool` step is stubbed in the workflow.

---

## Known decision: the dimension column

A common upstream workflow silently **drops the `Dimensjon H,B,D (mm)` column** even when it has
real data (`"1420x700x500"`). Berik carries it through by default (it's genuine dimension
metadata). To match the upstream output exactly instead, toggle that column off in the mapping
screen. Default = keep.

## v2 roadmap (architected for, not yet built)
- **IDS acceptance gate** — drop in the project's `.ids` and validate in the client's own
  information-requirement language (ifctester is already a dependency).
- **BCF issue export** — emit object-side failures as BCF topics that open *on the offending
  object* in Solibri/BIMcollab.
- **V770 objektkode + MMI** — validate object codes against the Statens vegvesen codelist and
  show the MMI maturity distribution vs the delivery target.
- **Geometry-derived quantities** — auto-fill lengths/dimensions from model geometry.
- **Saved mapping profiles per project**, recent-files, real PDF export.
