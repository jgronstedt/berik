"""Visual QA harness — screenshots the QC report + every app screen with real data.

Injects a mock window.pywebview.api (loaded with the real analyzed sample data) so the UI
renders exactly as it would in the packaged app, then captures each screen to tests/_qa/.
Run:  python3 tests/qa_render.py
"""
import json, pathlib, time
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
UI = ROOT / "berik" / "ui" / "index.html"
QA = HERE / "_qa"; QA.mkdir(exist_ok=True)

analysis = json.loads((HERE / "_qa_analysis.json").read_text())
result = json.loads((HERE / "_qa_result.json").read_text())

MOCK = """
window.pywebview = { api: {
  get_state: async () => ({excel:{path:'equipment-list.xlsm', name:'equipment-list.xlsm'},
    ifc:[{path:'model_blank.ifc', name:'model_blank.ifc'}],
    answer_key:'model_beriket.ifc', version:'1.0'}),
  pick_excel: async () => ({path:'x.xlsm', name:'x.xlsm'}),
  pick_ifc_files: async () => ([{path:'a.ifc',name:'a.ifc'}]),
  pick_ifc_folder: async () => ([{path:'a.ifc',name:'a.ifc'}]),
  remove_ifc: async () => ([]), clear_ifc: async () => ([]),
  set_answer_key: async () => ({path:'k.ifc',name:'k.ifc'}),
  analyze: async () => (window.__ANALYSIS__),
  choose_output_dir: async () => ('/Users/me/Beriket'),
  commit: async () => (window.__RESULT__),
  open_output_folder: async () => true, open_path: async () => true,
}};
window.__ANALYSIS__ = {ok:true, analysis: __A__};
window.__RESULT__   = {ok:true, result: __R__};
"""


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1180, "height": 820}, device_scale_factor=2)
        init = MOCK.replace("__A__", json.dumps(analysis)).replace("__R__", json.dumps(result))
        pg.add_init_script(init)
        pg.goto(UI.as_uri())
        pg.wait_for_timeout(700)
        pg.screenshot(path=str(QA / "01-load.png"))

        # to review
        pg.click("#analyze-btn")
        pg.wait_for_timeout(1400)
        pg.screenshot(path=str(QA / "03-review-top.png"))
        pg.evaluate("document.querySelector('#screen-review .review-scroll, #screen-review').scrollTo(0, 700)")
        pg.wait_for_timeout(500)
        pg.screenshot(path=str(QA / "03-review-mid.png"))
        pg.evaluate("document.querySelector('#screen-review .review-scroll, #screen-review').scrollTo(0, 1500)")
        pg.wait_for_timeout(400)
        pg.screenshot(path=str(QA / "03-review-low.png"))

        # sign off
        pg.fill("#approver", "Jane Doe")
        pg.wait_for_timeout(200)
        pg.click("#commit-btn")
        pg.wait_for_timeout(1200)
        pg.screenshot(path=str(QA / "04-done.png"))

        # the QC report
        rep = HERE / "_qa_out" / "QC-rapport.html"
        if rep.exists():
            pg2 = b.new_page(viewport={"width": 1000, "height": 1400}, device_scale_factor=2)
            pg2.goto(rep.as_uri())
            pg2.wait_for_timeout(500)
            pg2.screenshot(path=str(QA / "report-full.png"), full_page=True)
        b.close()
    print("screens written to", QA)


if __name__ == "__main__":
    main()
