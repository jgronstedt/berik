#!/usr/bin/env python3
"""Berik — desktop app entry point (pywebview).

A native window hosting the HTML/CSS/JS UI in ui/, with this Api class bridged to
JavaScript. Long jobs (analyze / commit) run on pywebview's js_api thread and push
progress to the UI via window.evaluate_js(...).

Run locally:  python3 app.py
Ship:         bundled with PyInstaller (see build/app.spec) on a Windows runner.
"""
from __future__ import annotations
import json
import os
import pathlib
import sys
import threading
import traceback


# --- Windows launch hardening (must run BEFORE importing webview -> clr) ------
# pywebview hosts the WebView2 UI through WinForms, which loads pythonnet's
# Python.Runtime.dll via the .NET Framework. When Berik is downloaded as a ZIP
# and extracted by Windows, every extracted file carries the "Mark-of-the-Web"
# zone tag, and .NET Framework refuses to load a zone-tagged managed assembly --
# the launch then dies with "Failed to resolve Python.Runtime.Loader.Initialize".
# The user owns these files (Berik runs from their own folder), so we strip the
# zone tag from our own bundle on startup. No admin rights, no user action.
def _strip_mark_of_the_web() -> None:
    if not (getattr(sys, "frozen", False) and os.name == "nt"):
        return
    roots = {
        pathlib.Path(getattr(sys, "_MEIPASS", "") or "."),
        pathlib.Path(sys.executable).resolve().parent,
    }
    for root in roots:
        if not root.is_dir():
            continue
        for f in root.rglob("*"):
            try:
                if f.is_file():
                    os.remove(f"{f}:Zone.Identifier")   # delete the ADS if present
            except OSError:
                pass                                      # no tag, or can't touch -- fine


def _fatal_launch_error(exc: Exception) -> None:
    """Last-resort, human-readable dialog if the UI runtime still won't start."""
    msg = (
        "Berik klarte ikke a starte grensesnittet.\n\n"
        "Dette skyldes nesten alltid at Windows har blokkert de nedlastede "
        "filene.\n\nLosning: Hoyreklikk ZIP-filen FOR du pakker den ut -> "
        "Egenskaper -> huk av «Fjern blokkering» / «Unblock» -> pakk ut "
        "pa nytt og start Berik.\n\n"
        f"Teknisk feil: {exc}"
    )
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, "Berik", 0x10)  # MB_ICONERROR
    except Exception:
        print(msg, file=sys.stderr)
    sys.exit(1)


_strip_mark_of_the_web()
try:
    import webview
except Exception as _exc:               # pythonnet / clr failed to initialise
    _fatal_launch_error(_exc)

from berik.engine import analyze as engine_analyze, commit as engine_commit
from berik import report as report_mod

# Resolve resources for both source runs and the PyInstaller-frozen bundle.
if getattr(sys, "frozen", False):
    APP_DIR = pathlib.Path(sys._MEIPASS)              # noqa: SLF001
else:
    APP_DIR = pathlib.Path(__file__).resolve().parent
UI_DIR = APP_DIR / "berik" / "ui"
VERSION = "1.1"


def _js(window, fn, *args):
    """Call a JS function safely with JSON-encoded args."""
    if window is None:
        return
    payload = ",".join(json.dumps(a, ensure_ascii=False) for a in args)
    try:
        window.evaluate_js(f"window.berik && window.berik.{fn} && window.berik.{fn}({payload});")
    except Exception:
        pass


class Api:
    def __init__(self):
        self.window = None
        self.excel_path: str | None = None
        self.excel_name: str | None = None
        self.ifc_paths: list[str] = []
        self.answer_key: str | None = None
        self.out_dir: str | None = None
        self.last_analysis = None
        self.last_commit = None

    # ----------------------------------------------------------------- pickers
    def pick_excel(self):
        res = self.window.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=False,
            file_types=("Excel (*.xlsm;*.xlsx)", "Alle filer (*.*)"))
        if res:
            self.excel_path = res[0]
            self.excel_name = pathlib.Path(res[0]).name
            return {"path": self.excel_path, "name": self.excel_name}
        return None

    def pick_ifc_files(self):
        res = self.window.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=True,
            file_types=("IFC-modeller (*.ifc)", "Alle filer (*.*)"))
        if res:
            self._add_ifc(res)
        return self._ifc_list()

    def pick_ifc_folder(self):
        res = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        if res:
            folder = pathlib.Path(res[0])
            found = sorted(str(p) for p in folder.glob("*.ifc")
                           if "beriket" not in p.stem.lower())
            self._add_ifc(found)
        return self._ifc_list()

    def add_dropped_paths(self, paths):
        """Files dropped onto the window — sort into excel vs ifc by extension."""
        for p in paths or []:
            ext = pathlib.Path(p).suffix.lower()
            if ext in (".xlsm", ".xlsx"):
                self.excel_path, self.excel_name = p, pathlib.Path(p).name
            elif ext == ".ifc" and "beriket" not in pathlib.Path(p).stem.lower():
                self._add_ifc([p])
        return self.get_state()

    def _add_ifc(self, paths):
        have = set(self.ifc_paths)
        for p in paths:
            if p not in have:
                self.ifc_paths.append(p)
                have.add(p)

    def _ifc_list(self):
        return [{"path": p, "name": pathlib.Path(p).name} for p in self.ifc_paths]

    def clear_ifc(self):
        self.ifc_paths = []
        return self._ifc_list()

    def remove_ifc(self, path):
        self.ifc_paths = [p for p in self.ifc_paths if p != path]
        return self._ifc_list()

    def set_answer_key(self, enable):
        """Toggle: if enabled, use a picked reference file to validate output."""
        if not enable:
            self.answer_key = None
            return None
        res = self.window.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=False,
            file_types=("IFC fasit (*.ifc)", "Alle filer (*.*)"))
        if res:
            self.answer_key = res[0]
            return {"path": self.answer_key, "name": pathlib.Path(res[0]).name}
        return None

    def get_state(self):
        return {
            "excel": {"path": self.excel_path, "name": self.excel_name} if self.excel_path else None,
            "ifc": self._ifc_list(),
            "answer_key": pathlib.Path(self.answer_key).name if self.answer_key else None,
            "version": VERSION,
        }

    # ----------------------------------------------------------------- analyze
    def analyze(self, excluded=None):
        if not self.excel_path or not self.ifc_paths:
            return {"error": "Velg både en Excel-liste og minst én IFC-fil."}

        def progress(msg, frac):
            _js(self.window, "onProgress", msg, frac)

        try:
            a = engine_analyze(self.excel_path, self.ifc_paths,
                               excluded=excluded, progress=progress)
            self.last_analysis = a
            return {"ok": True, "analysis": a.to_dict()}
        except Exception as e:
            traceback.print_exc()
            return {"error": f"Analyse feilet: {e}"}

    # ------------------------------------------------------------------ commit
    def choose_output_dir(self):
        res = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        if res:
            self.out_dir = res[0]
            return self.out_dir
        return None

    def commit(self, approver, excluded=None):
        if not approver or not approver.strip():
            return {"error": "Skriv inn navnet på den som godkjenner."}
        if not self.out_dir:
            # default: an output folder next to the first IFC
            self.out_dir = str(pathlib.Path(self.ifc_paths[0]).parent / "Beriket")

        def progress(msg, frac):
            _js(self.window, "onProgress", msg, frac)

        try:
            result, mapping, rows_by_tag = engine_commit(
                self.excel_path, self.ifc_paths, self.out_dir, approver.strip(),
                excluded=excluded, answer_key=self.answer_key,
                progress=progress, tool_version=VERSION)
            # Build the QC report from the analysis + commit result.
            progress("Lager QC-rapport…", 0.95)
            html, xlsx = report_mod.build_reports(
                self.last_analysis, result, self.out_dir, approver.strip(), VERSION)
            result.report_html = html
            result.report_xlsx = xlsx
            self.last_commit = result
            return {"ok": True, "result": result.to_dict()}
        except Exception as e:
            traceback.print_exc()
            return {"error": f"Skriving feilet: {e}"}

    # ------------------------------------------------------------------- utils
    def open_output_folder(self):
        if self.out_dir:
            _open_in_os(self.out_dir)
            return True
        return False

    def open_path(self, path):
        if path:
            _open_in_os(path)
            return True
        return False


def _open_in_os(path):
    import sys, subprocess, os
    try:
        if sys.platform.startswith("darwin"):
            subprocess.run(["open", path])
        elif os.name == "nt":
            os.startfile(path)  # noqa
        else:
            subprocess.run(["xdg-open", path])
    except Exception:
        pass


def main():
    api = Api()
    window = webview.create_window(
        "Berik — Excel til IFC",
        url=str(UI_DIR / "index.html"),
        js_api=api,
        width=1180, height=820, min_size=(980, 680),
        background_color="#222754",
    )
    api.window = window
    # Pin the WebView2/EdgeChromium backend explicitly so the loader path is
    # deterministic (no silent fallback to the legacy IE/mshtml renderer, which
    # would mangle the modern HTML/CSS UI). If the runtime still can't start,
    # show a human-readable dialog instead of a raw traceback.
    try:
        webview.start(gui="edgechromium", debug=False)
    except Exception as exc:
        _fatal_launch_error(exc)


if __name__ == "__main__":
    main()
