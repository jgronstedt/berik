/* ============================================================
   Berik — frontend controller. Vanilla JS, no deps.
   Talks to window.pywebview.api. Norwegian (bokmål) UI.
   ============================================================ */
'use strict';

/* ---------- progress bridge (define EARLY so backend calls land) ---------- */
window.berik = {
  onProgress(msg, frac){
    showOverlay();
    const m = document.getElementById('overlay-msg');
    const f = document.getElementById('overlay-fill');
    if (m && typeof msg === 'string') m.textContent = msg;
    if (f && typeof frac === 'number'){
      const pct = Math.max(0, Math.min(1, frac)) * 100;
      f.style.width = pct.toFixed(1) + '%';
    }
  }
};

/* ---------- module state ---------- */
const State = {
  excel: null,          // {path,name}
  ifc: [],              // [{path,name}]
  answerKey: null,      // string path
  version: '—',
  analysis: null,       // last analysis object
  excluded: [],         // [[pset,prop], ...]
  outDir: null,
  result: null,
};

/* ---------- tiny helpers ---------- */
const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const el = (tag, cls, txt) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (txt != null) e.textContent = txt;
  return e;
};
const fmt = n => (n == null || isNaN(n)) ? '0' : Number(n).toLocaleString('nb-NO');
const safe = v => (v === null || v === undefined || v === '') ? '' : String(v);

function api(){ return (window.pywebview && window.pywebview.api) || null; }

/* ---------- overlay & banner ---------- */
function showOverlay(){ $('#overlay').classList.add('show'); }
function hideOverlay(){
  const o = $('#overlay');
  o.classList.remove('show');
  $('#overlay-fill').style.width = '0%';
}
function showError(msg){
  const b = $('#banner');
  $('#banner-text').textContent = msg || 'Noe gikk galt. Prøv igjen.';
  b.hidden = false;
  requestAnimationFrame(() => b.classList.add('show'));
}
function hideError(){
  const b = $('#banner');
  b.classList.remove('show');
  setTimeout(() => { b.hidden = true; }, 300);
}

/* ---------- screen router ---------- */
const SCREENS = ['load', 'mapping', 'review', 'done'];
function go(name){
  SCREENS.forEach(s => {
    const sec = $('#screen-' + s);
    if (sec) sec.classList.toggle('is-active', s === name);
  });
  const active = $('#screen-' + name + ' .review-scroll, #screen-' + name + ' .sheet, #screen-' + name);
  if (active && active.scrollTo) active.scrollTo(0, 0);
}

/* ============================================================
   COUNT-UP animation
   ============================================================ */
function countUp(node, to, dur = 900){
  if (!node) return;
  to = Number(to) || 0;
  const from = 0;
  const start = performance.now();
  function step(now){
    const t = Math.min(1, (now - start) / dur);
    const eased = 1 - Math.pow(1 - t, 3);
    const val = Math.round(from + (to - from) * eased);
    node.textContent = fmt(val);
    if (t < 1) requestAnimationFrame(step);
    else node.textContent = fmt(to);
  }
  requestAnimationFrame(step);
}

/* ============================================================
   SCREEN 1 — LOAD
   ============================================================ */
function refreshLoadUI(){
  // excel
  const ex = $('#excel-chosen');
  const dzEx = $('#dz-excel');
  if (State.excel){
    ex.hidden = false; ex.textContent = State.excel.name;
    dzEx.classList.add('filled');
  } else {
    ex.hidden = true; dzEx.classList.remove('filled');
  }

  // ifc count + list
  const cnt = $('#ifc-count');
  const dzIfc = $('#dz-ifc');
  const list = $('#ifc-list');
  if (State.ifc.length){
    cnt.hidden = false;
    cnt.textContent = State.ifc.length === 1 ? '1 modell valgt' : State.ifc.length + ' modeller valgt';
    dzIfc.classList.add('filled');
    list.hidden = false;
    list.innerHTML = '';
    State.ifc.forEach(f => {
      const li = el('li');
      const name = el('span', 'ifc-name', f.name);
      const rm = el('button', 'ifc-rm', '×');
      rm.setAttribute('aria-label', 'Fjern ' + f.name);
      rm.addEventListener('click', async () => {
        const a = api(); if (!a) return;
        try { State.ifc = await a.remove_ifc(f.path) || []; refreshLoadUI(); }
        catch(e){ showError('Kunne ikke fjerne filen.'); }
      });
      li.append(name, rm);
      list.appendChild(li);
    });
  } else {
    cnt.hidden = true; dzIfc.classList.remove('filled');
    list.hidden = true; list.innerHTML = '';
  }

  // answer key
  const akn = $('#answer-key-name');
  if (State.answerKey){ akn.hidden = false; akn.textContent = State.answerKey.split('/').pop().split('\\').pop(); }
  else { akn.hidden = true; }

  // analyze gate + mapping link
  const ready = !!State.excel && State.ifc.length > 0;
  $('#analyze-btn').disabled = !ready;
  $('#mapping-link').hidden = !ready;
}

function wireLoad(){
  $('#dz-excel').addEventListener('click', async () => {
    const a = api(); if (!a) return;
    try {
      const r = await a.pick_excel();
      if (r){ State.excel = r; refreshLoadUI(); }
    } catch(e){ showError('Kunne ikke åpne Excel-filen.'); }
  });

  $('#dz-ifc').addEventListener('click', async () => {
    const a = api(); if (!a) return;
    try { State.ifc = await a.pick_ifc_files() || []; refreshLoadUI(); }
    catch(e){ showError('Kunne ikke velge IFC-filer.'); }
  });

  const folder = $('#ifc-folder-link');
  const pickFolder = async (ev) => {
    ev.stopPropagation(); ev.preventDefault();
    const a = api(); if (!a) return;
    try { State.ifc = await a.pick_ifc_folder() || []; refreshLoadUI(); }
    catch(e){ showError('Kunne ikke lese mappen.'); }
  };
  folder.addEventListener('click', pickFolder);
  folder.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') pickFolder(e); });

  // advanced toggle
  const advT = $('#adv-toggle');
  advT.addEventListener('click', () => {
    const open = advT.getAttribute('aria-expanded') === 'true';
    advT.setAttribute('aria-expanded', String(!open));
    $('#adv-panel').hidden = open;
  });
  $('#answer-key-btn').addEventListener('click', async () => {
    const a = api(); if (!a) return;
    try {
      const r = await a.set_answer_key(true);
      State.answerKey = r ? r.path : null;
      refreshLoadUI();
    } catch(e){ showError('Kunne ikke velge fasitfil.'); }
  });

  // analyze
  $('#analyze-btn').addEventListener('click', () => runAnalyze());

  // mapping link
  const mapLink = $('#mapping-link');
  const openMap = () => { if (State.analysis) renderMapping(); runAnalyzeThenMapping(); };
  mapLink.addEventListener('click', openMap);
  mapLink.addEventListener('keydown', e => { if (e.key === 'Enter') openMap(); });
}

async function runAnalyzeThenMapping(){
  // ensure we have an analysis (mapping screen needs analysis.mapping)
  if (State.analysis){ renderMapping(); go('mapping'); return; }
  const ok = await runAnalyze(true); // silent target
  if (ok){ renderMapping(); go('mapping'); }
}

/* ============================================================
   ANALYZE
   ============================================================ */
async function runAnalyze(toMapping = false){
  const a = api();
  if (!a){ showError('Kobling til Berik er ikke klar ennå.'); return false; }
  hideError();
  showOverlay();
  $('#overlay-msg').textContent = 'Analyserer modeller …';
  $('#overlay-fill').style.width = '4%';
  try {
    const res = await a.analyze(State.excluded);
    hideOverlay();
    if (res && res.error){ showError(res.error); return false; }
    if (!res || !res.analysis){ showError('Analysen returnerte ingen data.'); return false; }
    State.analysis = res.analysis;
    if (!toMapping){ renderReview(); go('review'); }
    return true;
  } catch(e){
    hideOverlay();
    showError('Analysen feilet: ' + (e && e.message ? e.message : 'ukjent feil'));
    return false;
  }
}

/* ============================================================
   SCREEN 2 — MAPPING
   ============================================================ */
function isExcluded(pset, prop){
  return State.excluded.some(p => p[0] === pset && p[1] === prop);
}
function renderMapping(){
  const m = State.analysis && State.analysis.mapping;
  if (!m) return;
  $('#map-key').textContent = m.key || '—';
  $('#map-note').textContent = m.tab
    ? `Berik leste kartleggingen automatisk fra fanen «${m.tab}».`
    : 'Berik leste kartleggingen automatisk.';

  // group columns by pset
  const groups = {};
  (m.columns || []).forEach(c => {
    const ps = c.pset || 'Uten Pset';
    (groups[ps] = groups[ps] || []).push(c);
  });

  const wrap = $('#map-groups');
  wrap.innerHTML = '';
  Object.keys(groups).forEach(ps => {
    const g = el('div', 'map-group');
    const head = el('div', 'map-group-head');
    head.appendChild(el('span', null, ps));
    head.appendChild(el('span', 'mg-count', groups[ps].length + (groups[ps].length === 1 ? ' egenskap' : ' egenskaper')));
    g.appendChild(head);

    const rows = el('div', 'map-rows');
    groups[ps].forEach(c => {
      const excluded = isExcluded(c.pset, c.prop) || c.include === false;
      const row = el('div', 'map-row' + (excluded ? ' excluded' : ''));
      row.appendChild(el('div', 'map-source', c.source_label || c.prop));
      row.appendChild(el('div', 'map-target', `${c.pset}.${c.prop}`));

      const tog = el('label', 'toggle');
      const inp = document.createElement('input');
      inp.type = 'checkbox';
      inp.checked = !excluded;
      inp.setAttribute('aria-label', `Inkluder ${c.pset}.${c.prop}`);
      inp.addEventListener('change', () => {
        if (inp.checked){
          State.excluded = State.excluded.filter(p => !(p[0] === c.pset && p[1] === c.prop));
          row.classList.remove('excluded');
        } else {
          if (!isExcluded(c.pset, c.prop)) State.excluded.push([c.pset, c.prop]);
          row.classList.add('excluded');
        }
      });
      tog.appendChild(inp);
      tog.appendChild(el('span', 'track'));
      tog.appendChild(el('span', 'knob'));
      row.appendChild(tog);
      rows.appendChild(row);
    });
    g.appendChild(rows);
    wrap.appendChild(g);
  });
}
function wireMapping(){
  $('#map-back').addEventListener('click', () => go('load'));
  $('#map-apply').addEventListener('click', async () => {
    const ok = await runAnalyze();
    if (ok) go('review');
  });
}

/* ============================================================
   SCREEN 3 — REVIEW
   ============================================================ */
function ragClass(rag){ return 'rag-' + (rag || 'green'); }

function renderReview(){
  const a = State.analysis;
  if (!a) return;
  const t = a.totals || {};

  // ----- ring -----
  const pct = Math.max(0, Math.min(100, Number(a.completeness_pct) || 0));
  const arc = $('#ring-arc');
  const C = 2 * Math.PI * 86; // 540.35
  arc.classList.remove('rag-green', 'rag-amber', 'rag-red');
  arc.classList.add(ragClass(a.rag));
  // reset then animate
  arc.style.strokeDashoffset = C;
  // count-up the pct text
  animatePct($('#ring-pct'), pct);
  requestAnimationFrame(() => {
    requestAnimationFrame(() => { arc.style.strokeDashoffset = C * (1 - pct / 100); });
  });

  // ----- headline -----
  countUp($('#hero-enriched'), t.objects_enriched);
  $('#hero-of').textContent = `av ${fmt(t.objects_with_tag)} taggede objekter`;
  countUp($('#st-files'), t.files);
  countUp($('#st-new'), t.changes_new);
  countUp($('#st-over'), t.changes_overwrite);
  countUp($('#st-matched'), t.tags_matched);

  // ----- per-file table -----
  const tbody = $('#file-tbody');
  tbody.innerHTML = '';
  (a.files || []).forEach(f => {
    const tr = document.createElement('tr');
    tr.appendChild(td(f.file, 'file-name'));
    const sc = document.createElement('td');
    sc.appendChild(el('span', 'schema-pill', f.schema || '—'));
    tr.appendChild(sc);
    tr.appendChild(td(`${fmt(f.objects_with_tag)} / ${fmt(f.objects_total)}`, 'num'));
    tr.appendChild(td(fmt(f.tags_matched), 'num'));
    tr.appendChild(td(fmt(f.objects_enriched), 'num'));
    tr.appendChild(td(fmt(f.one_to_many_tags), 'num'));
    tbody.appendChild(tr);
  });

  // ----- reconciliation -----
  renderReconciliation(a.reconciliation || {});

  // ----- health -----
  renderHealth(a.health || []);

  // ----- changes -----
  renderChanges(a.files || [], t);

  // ----- sign-off -----
  $('#commit-n').textContent = fmt(t.objects_enriched);
  refreshCommitGate();
}

function td(txt, cls){ const c = document.createElement('td'); if (cls) c.className = cls; c.textContent = txt; return c; }

function animatePct(node, to, dur = 1100){
  if (!node) return;
  const start = performance.now();
  function step(now){
    const p = Math.min(1, (now - start) / dur);
    const eased = 1 - Math.pow(1 - p, 3);
    const v = Math.round(to * eased);
    node.firstChild ? (node.firstChild.nodeValue = String(v)) : null;
    node.innerHTML = v + '<span class="ring-pct-sym">%</span>';
    if (p < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

/* ----- reconciliation ----- */
let _reconData = { excel: [], ifc: [] };
function renderReconciliation(r){
  // EXCEL orphans (array of tag strings)
  const exOrphans = r.excel_orphans || [];
  _reconData.excel = exOrphans;
  const exBadge = $('#recon-excel-badge');
  exBadge.textContent = fmt(exOrphans.length);
  exBadge.classList.toggle('warn', exOrphans.length > 0);

  const other = Number(r.excel_rows_other_files) || 0;
  const otherNode = $('#recon-excel-other');
  otherNode.textContent = other > 0
    ? `+${fmt(other)} rader hører til andre disiplinfiler`
    : '';

  renderReconList('#recon-excel-list', exOrphans, '');

  // IFC orphans (sample of {file,object,tag})
  const ifcSample = r.ifc_orphans_sample || [];
  _reconData.ifc = ifcSample;
  const ifcCount = (r.ifc_orphans_count != null) ? r.ifc_orphans_count : ifcSample.length;
  const ifcBadge = $('#recon-ifc-badge');
  ifcBadge.textContent = fmt(ifcCount);
  ifcBadge.classList.toggle('warn', ifcCount > 0);

  renderReconIfcList('#recon-ifc-list', ifcSample, '');
}
function renderReconList(sel, items, filter){
  const ul = $(sel); ul.innerHTML = '';
  const f = (filter || '').toLowerCase();
  const filtered = f ? items.filter(x => String(x).toLowerCase().includes(f)) : items;
  if (!filtered.length){ ul.appendChild(emptyLi(items.length ? 'Ingen treff.' : 'Ingenting her — alle rader er koblet.')); return; }
  const cap = 500;
  filtered.slice(0, cap).forEach(tag => {
    const li = el('li');
    li.appendChild(el('span', 'tag-mono', tag));
    ul.appendChild(li);
  });
  if (filtered.length > cap) ul.appendChild(emptyLi(`Viser ${cap} av ${fmt(filtered.length)}.`));
}
function renderReconIfcList(sel, items, filter){
  const ul = $(sel); ul.innerHTML = '';
  const f = (filter || '').toLowerCase();
  const filtered = f ? items.filter(x => JSON.stringify(x).toLowerCase().includes(f)) : items;
  if (!filtered.length){ ul.appendChild(emptyLi(items.length ? 'Ingen treff.' : 'Ingenting her — alle objekter har en rad.')); return; }
  filtered.slice(0, 500).forEach(o => {
    const li = el('li');
    li.appendChild(el('span', 'recon-item-file', (o.file || '') + ' ·'));
    li.appendChild(el('span', 'tag-mono', o.object || ''));
    if (o.tag){ li.appendChild(el('span', 'prop-mono', '· tagg ' + o.tag)); }
    ul.appendChild(li);
  });
}
function emptyLi(txt){ const li = el('li', 'empty', txt); return li; }

function wireReconciliation(){
  $$('.recon-head').forEach(btn => {
    btn.addEventListener('click', () => {
      const open = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', String(!open));
      const body = btn.parentElement.querySelector('.recon-body');
      body.hidden = open;
    });
  });
  $('#recon-excel-search').addEventListener('input', e =>
    renderReconList('#recon-excel-list', _reconData.excel, e.target.value));
  $('#recon-ifc-search').addEventListener('input', e =>
    renderReconIfcList('#recon-ifc-list', _reconData.ifc, e.target.value));
}

/* ----- health ----- */
let _activeHealth = null;
function renderHealth(health){
  const row = $('#health-chips');
  row.innerHTML = '';
  $('#health-detail').hidden = true;
  _activeHealth = null;

  if (!health.length){
    row.appendChild(el('span', 'chip sev-green', 'Ingen avvik funnet'));
    return;
  }
  health.forEach((h, i) => {
    const sev = h.severity || 'info';
    const chip = el('button', 'chip sev-' + sev);
    chip.type = 'button';
    chip.appendChild(el('span', 'chip-dot'));
    chip.appendChild(el('span', null, h.title || h.check || 'Sjekk'));
    if (h.count != null) chip.appendChild(el('span', 'chip-n', fmt(h.count)));
    chip.addEventListener('click', () => toggleHealth(h, i, chip));
    row.appendChild(chip);
  });
}
function toggleHealth(h, i, chip){
  const detail = $('#health-detail');
  $$('.chip', $('#health-chips')).forEach(c => c.classList.remove('is-active'));
  if (_activeHealth === i){ detail.hidden = true; _activeHealth = null; return; }
  _activeHealth = i;
  chip.classList.add('is-active');
  $('#health-detail-title').textContent = h.detail || h.title || '';
  $('#health-search').value = '';
  _healthItems = h.items || [];
  renderHealthList('');
  detail.hidden = false;
}
let _healthItems = [];
function renderHealthList(filter){
  const ul = $('#health-list'); ul.innerHTML = '';
  const f = (filter || '').toLowerCase();
  const filtered = f ? _healthItems.filter(x => JSON.stringify(x).toLowerCase().includes(f)) : _healthItems;
  if (!filtered.length){ ul.appendChild(emptyLi(_healthItems.length ? 'Ingen treff.' : 'Ingen detaljer.')); return; }
  filtered.slice(0, 1000).forEach(item => {
    const li = el('li');
    if (item && typeof item === 'object'){
      const txt = item.tag || item.object || item.gid || JSON.stringify(item);
      li.appendChild(el('span', 'tag-mono', String(txt)));
      if (item.detail) li.appendChild(el('span', 'prop-mono', '· ' + item.detail));
      if (item.file) li.appendChild(el('span', 'recon-item-file', '· ' + item.file));
    } else {
      li.appendChild(el('span', 'tag-mono', String(item)));
    }
    ul.appendChild(li);
  });
  if (filtered.length > 1000) ul.appendChild(emptyLi(`Viser 1000 av ${fmt(filtered.length)}.`));
}
function wireHealth(){
  $('#health-detail-close').addEventListener('click', () => {
    $('#health-detail').hidden = true;
    $$('.chip', $('#health-chips')).forEach(c => c.classList.remove('is-active'));
    _activeHealth = null;
  });
  $('#health-search').addEventListener('input', e => renderHealthList(e.target.value));
}

/* ----- changes (dry-run diff) ----- */
let _allChanges = [];
function renderChanges(files, totals){
  _allChanges = [];
  files.forEach(f => {
    (f.sample_changes || []).forEach(c => _allChanges.push(c));
  });
  const totalChanges = (Number(totals.changes_new) || 0) + (Number(totals.changes_overwrite) || 0);
  const head = $('#changes-count');
  const shown = Math.min(_allChanges.length, 300);
  if (totalChanges > shown){
    head.textContent = `viser ${fmt(shown)} av ${fmt(totalChanges)}`;
  } else {
    head.textContent = `${fmt(_allChanges.length)} endringer`;
  }
  renderChangeList('');
}
function renderChangeList(filter){
  const ul = $('#changes-list'); ul.innerHTML = '';
  const f = (filter || '').toLowerCase();
  let list = _allChanges;
  if (f){
    list = _allChanges.filter(c =>
      String(c.tag || '').toLowerCase().includes(f) ||
      String(c.pset || '').toLowerCase().includes(f) ||
      String(c.prop || '').toLowerCase().includes(f) ||
      String(c.new || '').toLowerCase().includes(f));
  }
  if (!list.length){ ul.appendChild(emptyLi(_allChanges.length ? 'Ingen treff.' : 'Ingen endringer å vise.')); return; }
  list.slice(0, 300).forEach(c => {
    const kind = c.kind === 'overwrite' ? 'overwrite' : 'new';
    const li = el('li', 'chg kind-' + kind);
    li.appendChild(el('span', 'chg-loc', `${safe(c.tag)} · ${safe(c.pset)}.${safe(c.prop)}`));
    li.appendChild(el('span', 'chg-arrow', ' '));
    if (kind === 'overwrite'){
      li.appendChild(oldVal(c.old));
      li.appendChild(arrow());
      li.appendChild(newVal(c.new));
    } else {
      li.appendChild(emptyToken());
      li.appendChild(arrow());
      li.appendChild(newVal(c.new));
    }
    ul.appendChild(li);
  });
  if (list.length > 300) ul.appendChild(emptyLi(`Viser 300 av ${fmt(list.length)}.`));
}
function oldVal(v){ return el('span', 'chg-old', `'${safe(v)}'`); }
function newVal(v){ return el('span', 'chg-val', `'${safe(v)}'`); }
function emptyToken(){ return el('span', 'chg-empty', '(tom)'); }
function arrow(){ return el('span', 'chg-arrow', '→'); }

function wireChanges(){
  $('#changes-search').addEventListener('input', e => renderChangeList(e.target.value));
}

/* ----- sign-off ----- */
function refreshCommitGate(){
  const name = $('#approver').value.trim();
  $('#commit-btn').disabled = name.length === 0;
}
function wireSignoff(){
  $('#approver').addEventListener('input', refreshCommitGate);
  $('#outdir-btn').addEventListener('click', async () => {
    const a = api(); if (!a) return;
    try {
      const dir = await a.choose_output_dir();
      if (dir){
        State.outDir = dir;
        const p = $('#outdir-path');
        p.hidden = false; p.textContent = dir; p.title = dir;
      }
    } catch(e){ showError('Kunne ikke velge mappe.'); }
  });
  $('#commit-btn').addEventListener('click', () => runCommit());
  $('#rev-back').addEventListener('click', () => go('load'));
}

async function runCommit(){
  const a = api();
  if (!a){ showError('Kobling til Berik er ikke klar ennå.'); return; }
  const name = $('#approver').value.trim();
  if (!name){ showError('Skriv inn navnet ditt for å godkjenne.'); return; }
  hideError();
  showOverlay();
  $('#overlay-msg').textContent = 'Skriver beriket IFC …';
  $('#overlay-fill').style.width = '4%';
  try {
    const res = await a.commit(name, State.excluded);
    hideOverlay();
    if (res && res.error){ showError(res.error); return; }
    if (!res || !res.result){ showError('Skriving returnerte ingen data.'); return; }
    State.result = res.result;
    renderDone();
    go('done');
  } catch(e){
    hideOverlay();
    showError('Skriving feilet: ' + (e && e.message ? e.message : 'ukjent feil'));
  }
}

/* ============================================================
   SCREEN 4 — DONE
   ============================================================ */
function renderDone(){
  const r = State.result;
  if (!r) return;
  const files = r.written_files || [];
  const totalEnriched = files.reduce((s, f) => s + (Number(f.objects_enriched) || 0), 0);
  const m = files.length;
  $('#done-title').textContent =
    `Beriket ${fmt(totalEnriched)} ${totalEnriched === 1 ? 'objekt' : 'objekter'} i ${fmt(m)} ${m === 1 ? 'fil' : 'filer'}.`;

  // validation badge (top-level or per-file roll-up)
  const val = r.validation || (files.find(f => f.validation) || {}).validation;
  const badge = $('#done-validation');
  if (val && val.match_pct != null){
    badge.hidden = false;
    badge.textContent = `Validert mot fasit: ${val.match_pct}% eksakt`;
  } else {
    badge.hidden = true;
  }

  // file list
  const ul = $('#done-file-list');
  ul.innerHTML = '';
  files.forEach(f => {
    const li = el('li');
    li.appendChild(el('span', 'dfl-src', fileLeaf(f.source)));
    li.appendChild(el('span', 'dfl-arrow', '→'));
    li.appendChild(el('span', 'dfl-out', fileLeaf(f.output)));
    li.appendChild(el('span', 'dfl-n', fmt(f.objects_enriched) + ' beriket'));
    ul.appendChild(li);
  });

  // report buttons enable/disable
  $('#done-report').disabled = !r.report_html;
  $('#done-xlsx').disabled = !r.report_xlsx;
}
function fileLeaf(p){ return p ? String(p).split('/').pop().split('\\').pop() : ''; }

function wireDone(){
  $('#done-openfolder').addEventListener('click', async () => {
    const a = api(); if (!a) return;
    try { await a.open_output_folder(); } catch(e){ showError('Kunne ikke åpne mappen.'); }
  });
  $('#done-report').addEventListener('click', async () => {
    const a = api(); if (!a || !State.result) return;
    try { await a.open_path(State.result.report_html); } catch(e){ showError('Kunne ikke åpne rapporten.'); }
  });
  $('#done-xlsx').addEventListener('click', async () => {
    const a = api(); if (!a || !State.result) return;
    try { await a.open_path(State.result.report_xlsx); } catch(e){ showError('Kunne ikke åpne datarapporten.'); }
  });
  $('#done-new').addEventListener('click', () => resetAll());
}

function resetAll(){
  // keep loaded files? safest is a fresh run: re-pull state, clear analysis/result
  State.analysis = null;
  State.result = null;
  State.excluded = [];
  $('#approver').value = '';
  $('#commit-btn').disabled = true;
  go('load');
  refreshLoadUI();
}

/* ============================================================
   BOOT
   ============================================================ */
function wireBanner(){
  $('#banner-close').addEventListener('click', hideError);
}

async function pullState(){
  const a = api();
  if (!a) return;
  try {
    const s = await a.get_state();
    if (s){
      State.excel = s.excel || null;
      State.ifc = s.ifc || [];
      State.answerKey = s.answer_key || null;
      State.version = s.version != null ? s.version : '—';
      $('#ver-load').textContent = State.version;
    }
  } catch(e){ /* backend may not be ready; ignore */ }
  refreshLoadUI();
}

function boot(){
  wireLoad();
  wireMapping();
  wireReconciliation();
  wireHealth();
  wireChanges();
  wireSignoff();
  wireDone();
  wireBanner();
  refreshLoadUI();
  go('load');

  // wait for pywebview bridge, then pull persisted state
  if (window.pywebview && window.pywebview.api){
    pullState();
  } else {
    window.addEventListener('pywebviewready', pullState, { once: true });
    // belt-and-suspenders poll in case the event already fired or is unavailable
    let tries = 0;
    const iv = setInterval(() => {
      if (window.pywebview && window.pywebview.api){ clearInterval(iv); pullState(); }
      else if (++tries > 40){ clearInterval(iv); }
    }, 250);
  }
}

if (document.readyState === 'loading'){
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}
