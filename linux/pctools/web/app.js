/* PC-Tools für Linux – Oberfläche (Vanilla JS, keine externen Abhängigkeiten).
 * Alle sichtbaren Texte sind Deutsch und laufen durch die Funktion t(); Platzhalter {0}, {1}.
 * Alle Daten vom Server werden vor der Ausgabe mit esc() maskiert. */
'use strict';

// ------------------------------------------------------------------ Grundlagen
const TOKEN = (() => {
  const q = new URLSearchParams(location.search).get('t');
  try {
    if (q) { sessionStorage.setItem('pct-token', q); }
    if (q) { history.replaceState(null, '', '/'); }
    return q || sessionStorage.getItem('pct-token') || '';
  } catch (e) { return q || ''; }
})();

let STR = {};            // aktuelle Übersetzungen
let INIT = null;         // Daten von /api/init
let currentPage = 'overview';
let renderSeq = 0;       // verhindert, dass alte Antworten neue Seiten überschreiben

function t(s, ...args) {
  let r = (STR[s] || s);
  if (args.length) r = r.replace(/\{(\d+)\}/g, (m, i) => (i < args.length ? String(args[i]) : m));
  return r;
}

function esc(v) {
  return String(v === null || v === undefined ? '' : v)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function $(sel, root) { return (root || document).querySelector(sel); }
function $$(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

function fmtSize(n) {
  if (n === null || n === undefined) return '?';
  const u = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0; n = Number(n);
  while (Math.abs(n) >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return (i === 0 ? String(Math.round(n)) : n.toFixed(1)).replace('.', ',') + ' ' + u[i];
}

function fmtUptime(sec) {
  const d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600), m = Math.floor((sec % 3600) / 60);
  if (d) return t('{0} Tage, {1} Std.', d, h);
  if (h) return t('{0} Std., {1} Min.', h, m);
  return t('{0} Min.', m);
}

async function api(path, body) {
  const opts = { headers: { 'X-PCT-Token': TOKEN } };
  if (body !== undefined) {
    opts.method = 'POST';
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, opts);
  } catch (e) {
    showBanner(t('Keine Verbindung zu PC-Tools. Wurde das Programm beendet? Bitte neu starten.'), true);
    throw e;
  }
  if (res.status === 403) {
    showBanner(t('Zugriff verweigert. Bitte PC-Tools über das Startmenü neu öffnen.'), true);
    throw new Error('403');
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
  return data;
}

function showBanner(text, crit) {
  const b = $('#banner');
  b.textContent = text;
  b.className = 'banner' + (crit ? ' crit' : '');
  b.hidden = !text;
}

let toastTimer = null;
function toast(text) {
  const el = $('#toast');
  el.textContent = text;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 4000);
}

function setBusy(on) { $('#busy').hidden = !on; }

// Dialog: buttons = [{label, value, primary}] -> Promise mit value
function dialog(title, bodyHtml, buttons) {
  const dlg = $('#dlg');
  $('#dlg-title').textContent = title;
  $('#dlg-body').innerHTML = bodyHtml;
  const act = $('#dlg-actions');
  act.innerHTML = '';
  return new Promise((resolve) => {
    (buttons || [{ label: t('OK'), value: true, primary: true }]).forEach((b) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn' + (b.primary ? ' primary' : '');
      btn.textContent = b.label;
      btn.addEventListener('click', () => { dlg.close(); resolve(b.value); });
      act.appendChild(btn);
    });
    dlg.onclose = () => resolve(false);
    dlg.onclick = null;
    dlg.showModal();
  });
}

function confirmDlg(title, html, okLabel) {
  return dialog(title, html, [
    { label: t('Abbrechen'), value: false },
    { label: okLabel || t('Fortfahren'), value: true, primary: true },
  ]);
}

function adminNote() {
  if (!INIT || INIT.root_method === 'pkexec') return '<p class="muted small">' + esc(t('Das System fragt gleich nach deinem Kennwort (Administratorrechte).')) + '</p>';
  if (INIT.root_method === 'sudo') return '<p class="muted small">' + esc(t('pkexec fehlt – es wird sudo ohne Kennwortabfrage versucht. Das klappt nur, wenn sudo so eingerichtet ist.')) + '</p>';
  return '<p class="notice warn">' + esc(t('Weder pkexec noch sudo gefunden – Administratoraktionen sind nicht möglich.')) + '</p>';
}

// ------------------------------------------------------------------ Aufträge
// Startet einen Hintergrundauftrag und zeigt Fortschritt + Protokoll in container.
async function runJob(kind, params, container, onDone) {
  container.innerHTML = '<div class="job card"><div class="row"><b class="job-title"></b><span class="spacer"></span>' +
    '<span class="badge job-state"></span></div><div class="progress indet"><i></i></div><pre class="log"></pre></div>';
  const title = $('.job-title', container), state = $('.job-state', container);
  const log = $('.log', container), bar = $('.progress', container);
  let id;
  try {
    id = (await api('/api/jobs/start', { kind, params })).id;
  } catch (e) {
    log.textContent = t('Fehler: {0}', e.message);
    return null;
  }
  setBusy(true);
  let since = 0;
  return new Promise((resolve) => {
    const poll = async () => {
      let j;
      try {
        j = await api('/api/jobs/' + id + '?since=' + since);
      } catch (e) { setBusy(false); resolve(null); return; }
      title.textContent = j.title;
      since = j.next;
      if (j.lines.length) {
        log.textContent += j.lines.join('\n') + '\n';
        log.scrollTop = log.scrollHeight;
      }
      if (j.progress !== null && j.progress !== undefined) {
        bar.classList.remove('indet');
        $('i', bar).style.width = j.progress + '%';
      }
      if (j.state === 'running') {
        state.textContent = t('läuft …');
        setTimeout(poll, 700);
        return;
      }
      setBusy(false);
      bar.classList.remove('indet');
      $('i', bar).style.width = '100%';
      state.textContent = j.state === 'done' ? t('fertig') : t('Fehler');
      state.className = 'badge job-state ' + (j.state === 'done' ? 'ok' : 'crit');
      if (onDone) onDone(j.result, j);
      resolve(j.result);
    };
    poll();
  });
}

// ------------------------------------------------------------------ Bausteine
function sevLabel(s) {
  return { crit: t('kritisch'), warn: t('Warnung'), info: t('Hinweis'), ok: t('in Ordnung') }[s] || s;
}

function findingsList(list, withPage) {
  if (!list || !list.length) return '<p class="muted">' + esc(t('Keine Auffälligkeiten.')) + '</p>';
  return '<ul class="findings">' + list.map((f) =>
    '<li class="sev-' + esc(f.severity) + '"><span class="dot"></span><div class="txt"><b>' + esc(f.title) + '</b>' +
    (f.detail ? '<span class="muted">' + esc(f.detail) + '</span>' : '') +
    (f.fix ? '<div class="fixbox">' + esc(t('Lösung:')) + ' ' + esc(f.fix) + '</div>' : '') + '</div>' +
    (f.action ? '<button class="btn small primary" data-fix="' + esc(f.action) + '">' + esc(t('Beheben')) + '</button>' : '') +
    (withPage && f.page ? '<button class="btn small" data-goto="' + esc(f.page) + '">' + esc(t('Öffnen')) + '</button>' : '') +
    '</li>').join('') + '</ul>';
}

function usageBar(pct) {
  const cls = pct >= 95 ? 'crit' : pct >= 90 ? 'warn' : '';
  return '<div class="bar ' + cls + '"><i style="width:' + Math.min(100, Math.max(0, Number(pct) || 0)) + '%"></i></div>';
}

function na() { return '<span class="muted">' + esc(t('nicht verfügbar')) + '</span>'; }

function bindCommon(root) {
  $$('[data-goto]', root).forEach((b) => b.addEventListener('click', () => go(b.dataset.goto)));
  $$('[data-fix]', root).forEach((b) => b.addEventListener('click', () => doFix(b.dataset.fix)));
}

async function doFix(action) {
  const texts = {
    'enable-ufw': t('Die Firewall ufw wird eingeschaltet. Eingehende Verbindungen werden dann blockiert (SSH bleibt erlaubt, falls es läuft).'),
    'enable-firewalld': t('Die Firewall firewalld wird eingeschaltet und beim Start automatisch geladen.'),
    'enable-fstrim': t('Der wöchentliche TRIM-Dienst (fstrim.timer) wird eingeschaltet. Das hält SSDs schnell.'),
  };
  if (!await confirmDlg(t('Problem beheben'), '<p>' + esc(texts[action] || action) + '</p>' + adminNote())) return;
  const box = document.createElement('div');
  $('#content').prepend(box);
  await runJob('fix', { action }, box, () => setTimeout(() => go(currentPage), 1500));
}

// ------------------------------------------------------------------ Seiten
const PAGES = {};

PAGES.overview = async (el) => {
  const d = await api('/api/overview');
  const i = d.info, h = d.health;
  const circ = 2 * Math.PI * 58;
  const lightText = { green: t('Alles in Ordnung'), yellow: t('Einiges zu tun'), red: t('Handlungsbedarf') }[h.light];
  el.innerHTML =
    '<div class="card"><div class="hero">' +
      '<div class="score light-' + esc(h.light) + '"><svg viewBox="0 0 140 140"><circle class="track" cx="70" cy="70" r="58"/>' +
      '<circle cx="70" cy="70" r="58" stroke-dasharray="' + circ + '" stroke-dashoffset="' + (circ * (1 - h.score / 100)) + '"/></svg>' +
      '<div class="val">' + esc(h.score) + '<small>' + esc(t('von 100')) + '</small></div></div>' +
      '<div style="flex:1;min-width:240px"><h2 class="light-' + esc(h.light) + '" style="font-size:20px;margin:0 0 6px">' + esc(lightText) + '</h2>' +
      '<p class="muted" style="margin:0 0 14px">' + esc(t('Alles pflegen installiert alle Updates und räumt Paket-Cache, Journal und Vorschaubilder auf.')) + '</p>' +
      '<button class="btn primary big" id="maintain">' + esc(t('Alles pflegen')) + '</button>' +
      (h.smart_checked ? '' : ' <button class="btn" data-goto="disks">' + esc(t('SMART prüfen')) + '</button>') +
      '</div></div><div id="maintain-job"></div></div>' +
    '<div class="card"><h2>' + esc(t('Befunde')) + '</h2>' + findingsList(h.findings, true) + '</div>' +
    '<div class="grid">' +
      '<div class="card"><h2>' + esc(t('System')) + '</h2><dl class="kv">' +
        '<dt>' + esc(t('Distribution')) + '</dt><dd>' + esc(i.distro) + '</dd>' +
        '<dt>' + esc(t('Kernel')) + '</dt><dd>' + esc(i.kernel) + '</dd>' +
        '<dt>' + esc(t('Desktop')) + '</dt><dd>' + esc(i.desktop) + '</dd>' +
        '<dt>' + esc(t('Laufzeit')) + '</dt><dd>' + esc(fmtUptime(i.uptime)) + '</dd>' +
        '<dt>' + esc(t('Pakete')) + '</dt><dd>' + esc(i.package_manager) + (i.flatpak ? ' · Flatpak' : '') + (i.snap ? ' · Snap' : '') + '</dd>' +
      '</dl></div>' +
      '<div class="card"><h2>' + esc(t('Prozessor und Speicher')) + '</h2><dl class="kv">' +
        '<dt>' + esc(t('CPU')) + '</dt><dd>' + esc(i.cpu.model) + '</dd>' +
        '<dt>' + esc(t('Kerne')) + '</dt><dd>' + esc(i.cpu.cores) + ' (' + esc(i.cpu.arch) + ')</dd>' +
        '<dt>' + esc(t('Auslastung')) + '</dt><dd>' + esc((i.cpu.load || []).map((x) => x.toFixed(2)).join(' / ')) + '</dd>' +
        '<dt>' + esc(t('RAM')) + '</dt><dd>' + esc(t('{0} frei von {1}', fmtSize(i.mem_available), fmtSize(i.mem_total))) + '</dd>' +
        '<dt>' + esc(t('Auslagerung')) + '</dt><dd>' + (i.swap_total ? esc(t('{0} belegt von {1}', fmtSize(i.swap_total - i.swap_free), fmtSize(i.swap_total))) : esc(t('keine'))) + '</dd>' +
      '</dl></div>' +
      '<div class="card"><h2>' + esc(t('Datenträger')) + '</h2>' + (i.disks.length ? i.disks.map((x) =>
        '<div style="margin-bottom:10px"><div class="row"><b>' + esc(x.mount) + '</b><span class="spacer"></span><span class="muted small">' +
        esc(t('{0} frei von {1}', fmtSize(x.avail), fmtSize(x.size))) + '</span></div>' + usageBar(x.percent) + '</div>').join('') : na()) +
      '</div>' +
    '</div>';
  bindCommon(el);
  $('#maintain').addEventListener('click', async () => {
    const ok = await confirmDlg(t('Alles pflegen'),
      '<p>' + esc(t('Folgendes wird jetzt erledigt:')) + '</p><ul><li>' + esc(t('alle Updates installieren (System, Flatpak, Snap)')) + '</li><li>' +
      esc(t('Paket-Cache leeren')) + '</li><li>' + esc(t('Systemprotokoll auf 14 Tage kürzen')) + '</li><li>' +
      esc(t('Vorschaubilder-Cache leeren')) + '</li></ul>' + adminNote(), t('Jetzt pflegen'));
    if (!ok) return;
    $('#maintain').disabled = true;
    await runJob('maintain', {}, $('#maintain-job'), (r) => {
      if (r && r.reboot) toast(t('Neustart erforderlich, damit alle Updates wirksam werden.'));
    });
    $('#maintain').disabled = false;
  });
};

function updTable(list, emptyText) {
  if (list === null || list === undefined) return na();
  if (!list.length) return '<p class="muted">' + esc(emptyText) + '</p>';
  return '<div class="table-wrap"><table><thead><tr><th>' + esc(t('Paket')) + '</th><th>' + esc(t('Neue Version')) +
    '</th><th>' + esc(t('Installiert')) + '</th><th>' + esc(t('Quelle')) + '</th></tr></thead><tbody>' +
    list.map((p) => '<tr><td>' + esc(p.name) + (p.security ? ' <span class="badge crit">' + esc(t('Sicherheit')) + '</span>' : '') +
      '</td><td>' + esc(p.new) + '</td><td class="muted">' + esc(p.old || '–') + '</td><td class="muted">' + esc(p.repo) + '</td></tr>').join('') +
    '</tbody></table></div>';
}

PAGES.updates = async (el) => {
  el.innerHTML = '<div class="card"><div class="row"><button class="btn primary" id="u-install" disabled>' + esc(t('Alle installieren')) + '</button>' +
    '<button class="btn" id="u-check">' + esc(t('Erneut suchen')) + '</button>' +
    '<button class="btn" id="u-refresh">' + esc(t('Paketquellen online aktualisieren')) + '</button></div>' +
    '<p class="muted small" style="margin:10px 0 0">' + esc(t('"Erneut suchen" nutzt die vorhandenen Paketlisten. "Online aktualisieren" lädt neue Listen (Administratorrechte).')) + '</p>' +
    '<div id="u-job"></div></div><div id="u-list"></div>';
  const show = (d) => {
    if (!d) return;
    const total = d.system.length + (d.flatpak || []).length + (d.snap || []).length;
    $('#u-install').disabled = total === 0;
    $('#u-list').innerHTML =
      (d.reboot_required ? '<div class="notice warn">' + esc(t('Neustart erforderlich: Einige Updates werden erst nach einem Neustart wirksam.')) + '</div>' : '') +
      '<div class="card"><h2>' + esc(t('Systempakete ({0})', d.package_manager || '–')) + ' <span class="badge">' + d.system.length + '</span>' +
      (d.security ? ' <span class="badge crit">' + esc(t('{0} Sicherheit', d.security)) + '</span>' : '') + '</h2>' +
      (d.system_note ? '<p class="muted">' + esc(d.system_note) + '</p>' : '') + updTable(d.system, t('Alles aktuell.')) + '</div>' +
      '<div class="card"><h2>Flatpak <span class="badge">' + (d.flatpak ? d.flatpak.length : '–') + '</span></h2>' + updTable(d.flatpak, t('Alles aktuell.')) + '</div>' +
      '<div class="card"><h2>Snap <span class="badge">' + (d.snap ? d.snap.length : '–') + '</span></h2>' + updTable(d.snap, t('Alles aktuell.')) + '</div>';
    $('#u-install').onclick = async () => {
      const sources = ['system'];
      if (d.flatpak && d.flatpak.length) sources.push('flatpak');
      if (d.snap && d.snap.length) sources.push('snap');
      if (!await confirmDlg(t('Updates installieren'), '<p>' + esc(t('{0} Updates werden installiert. Das kann einige Minuten dauern. Bitte den Rechner währenddessen nicht ausschalten.', total)) + '</p>' + adminNote(), t('Installieren'))) return;
      await runJob('updates-install', { sources }, $('#u-job'), (r) => {
        if (r && r.reboot) toast(t('Neustart erforderlich, damit alle Updates wirksam werden.'));
        check(false);
      });
    };
  };
  const check = (online) => runJob('updates-check', { online }, $('#u-job'), (r) => show(r));
  $('#u-check').onclick = () => check(false);
  $('#u-refresh').onclick = async () => {
    if (!await confirmDlg(t('Paketquellen aktualisieren'), '<p>' + esc(t('Die Paketlisten werden aus dem Internet neu geladen.')) + '</p>' + adminNote())) return;
    runJob('refresh', {}, $('#u-job'), (r) => r && r.data && show(r.data));
  };
  const c = await api('/api/updates/cached');
  if (c.data && c.data.apps_checked) show(c.data);
  else check(false);
};

PAGES.cleanup = async (el) => {
  el.innerHTML = '<div class="card"><p class="muted">' + esc(t('Analysiere … (Größen werden berechnet)')) + '</p><div class="progress indet"><i></i></div></div>';
  const d = await api('/api/cleanup');
  el.innerHTML = '<div class="card"><h2>' + esc(t('Was kann weg?')) + '</h2>' +
    d.items.map((it) =>
      '<label class="check"><input type="checkbox" name="clean" value="' + esc(it.id) + '"' + (it.available ? '' : ' disabled') +
      (it.available && it.default ? ' checked' : '') + '><div style="flex:1"><div class="row"><b>' + esc(it.title) + '</b>' +
      (it.root ? ' <span class="badge">' + esc(t('Administrator')) + '</span>' : '') + '<span class="spacer"></span><b>' +
      (it.size !== null && it.size !== undefined ? esc(fmtSize(it.size)) : (it.count !== undefined ? esc(t('{0} Pakete', it.count)) : '')) + '</b></div>' +
      '<div class="muted small">' + esc(it.desc) + '</div>' + (it.note ? '<div class="small" style="color:var(--warn)">' + esc(it.note) + '</div>' : '') +
      (it.details && it.details.length ? '<details class="small"><summary>' + esc(t('Liste anzeigen ({0})', it.details.length)) + '</summary><code>' +
        esc(it.details.join(', ')) + '</code></details>' : '') + '</div></label>').join('') +
    '<div class="row" style="margin-top:12px"><button class="btn primary" id="c-run">' + esc(t('Ausgewählte bereinigen')) + '</button>' +
    '<button class="btn" id="c-again">' + esc(t('Neu analysieren')) + '</button></div><div id="c-job"></div></div>' +
    '<div class="card"><h2>' + esc(t('Größte Ordner in ~/.cache')) + ' <span class="badge">' + esc(fmtSize(d.cache_total)) + '</span></h2>' +
    '<p class="muted small">' + esc(t('Nur zur Information – PC-Tools löscht hier nichts automatisch. Programme legen hier Zwischendaten ab, die sie bei Bedarf neu erzeugen.')) + '</p>' +
    (d.cache_folders.length ? '<table><tbody>' + d.cache_folders.map((f) => '<tr><td>~/.cache/' + esc(f.name) + '</td><td class="num">' + esc(fmtSize(f.size)) + '</td></tr>').join('') + '</tbody></table>' : '<p class="muted">–</p>') +
    '</div>';
  $('#c-again').onclick = () => go('cleanup');
  $('#c-run').onclick = async () => {
    const sel = $$('input[name=clean]:checked', el).map((x) => x.value);
    if (!sel.length) { toast(t('Bitte mindestens einen Punkt auswählen.')); return; }
    const chosen = d.items.filter((it) => sel.includes(it.id));
    const needsRoot = chosen.some((it) => it.root);
    const warn = chosen.filter((it) => it.confirm).map((it) => '<p class="notice warn">' + esc(t('Achtung: "{0}" lässt sich nicht rückgängig machen.', it.title)) + '</p>').join('');
    if (!await confirmDlg(t('Aufräumen'), '<ul>' + chosen.map((it) => '<li>' + esc(it.title) + '</li>').join('') + '</ul>' + warn + (needsRoot ? adminNote() : ''), t('Bereinigen'))) return;
    await runJob('clean', { items: sel }, $('#c-job'));
  };
};

PAGES.autostart = async (el) => {
  const d = await api('/api/autostart');
  el.innerHTML = '<div class="card"><h2>' + esc(t('Programme beim Anmelden')) + '</h2>' +
    '<p class="muted small">' + esc(t('Ausschalten legt eine Kopie in {0} mit "Hidden=true" an. Systemdateien werden nie verändert.', d.user_dir)) + '</p>' +
    (d.entries.length ? '<div class="table-wrap"><table><thead><tr><th></th><th>' + esc(t('Name')) + '</th><th>' + esc(t('Befehl')) + '</th><th>' + esc(t('Quelle')) + '</th></tr></thead><tbody>' +
      d.entries.map((e) => '<tr' + (e.relevant ? '' : ' class="muted"') + '><td><label class="switch"><input type="checkbox" data-file="' + esc(e.file) + '"' + (e.enabled ? ' checked' : '') +
        '><span></span></label></td><td><b>' + esc(e.name) + '</b><div class="muted small">' + esc(e.comment) + (e.relevant ? '' : ' (' + esc(t('nicht für diesen Desktop')) + ')') + '</div></td><td><code>' + esc(e.exec) + '</code></td><td>' +
        esc({ system: t('System'), user: t('Benutzer'), override: t('System, angepasst') }[e.source]) + '</td></tr>').join('') + '</tbody></table></div>'
      : '<p class="muted">' + esc(t('Keine Autostart-Einträge gefunden.')) + '</p>') + '</div>' +
    '<div class="card"><h2>' + esc(t('Aktivierte Benutzerdienste (systemd --user)')) + '</h2>' +
    (d.user_units === null ? na() : d.user_units.length ? '<table><tbody>' + d.user_units.map((u) => '<tr><td><code>' + esc(u.unit) + '</code></td><td class="muted">' + esc(u.state) + '</td></tr>').join('') + '</tbody></table>' : '<p class="muted">–</p>') +
    '<p class="muted small">' + esc(t('Nur Anzeige. Abschalten im Terminal mit: systemctl --user disable NAME')) + '</p></div>';
  $$('input[data-file]', el).forEach((cb) => cb.addEventListener('change', async () => {
    const r = await api('/api/autostart/toggle', { file: cb.dataset.file, enabled: cb.checked });
    if (r.error) { toast(r.error); cb.checked = !cb.checked; } else toast(cb.checked ? t('Eingeschaltet.') : t('Ausgeschaltet. Wirkt ab der nächsten Anmeldung.'));
  }));
};

PAGES.services = async (el) => {
  const d = await api('/api/services');
  const unitTable = (list, user) => {
    if (list === null || list === undefined) return na();
    if (!list.length) return '<p class="muted">' + esc(t('Keine fehlgeschlagenen Dienste.')) + '</p>';
    return '<div class="table-wrap"><table><tbody>' + list.map((u) => '<tr><td><b>' + esc(u.unit) + '</b><div class="muted small">' + esc(u.description) +
      '</div></td><td><span class="badge crit">' + esc(u.sub) + '</span></td><td class="num">' +
      '<button class="btn small" data-journal="' + esc(u.unit) + '" data-user="' + (user ? 1 : 0) + '">' + esc(t('Protokoll')) + '</button> ' +
      (/\.service$/.test(u.unit) ? '<button class="btn small primary" data-restart="' + esc(u.unit) + '" data-user="' + (user ? 1 : 0) + '">' + esc(t('Neu starten')) + '</button>' : '') +
      '</td></tr>').join('') + '</tbody></table></div>';
  };
  const b = d.boot;
  el.innerHTML = '<div class="card"><h2>' + esc(t('Fehlgeschlagene Systemdienste')) + '</h2>' + unitTable(d.system, false) + '</div>' +
    '<div class="card"><h2>' + esc(t('Fehlgeschlagene Benutzerdienste')) + '</h2>' + unitTable(d.user, true) + '</div><div id="s-job"></div>' +
    '<div class="card"><h2>' + esc(t('Startzeit')) + '</h2>' + (b.available ? '<p>' + esc(b.summary) + '</p>' +
      (b.blame.length ? '<h3>' + esc(t('Langsamste Dienste beim Start')) + '</h3><table><tbody>' + b.blame.map((x) => '<tr><td><code>' + esc(x.unit) + '</code></td><td class="num">' + esc(x.time) + '</td></tr>').join('') + '</tbody></table>' : '')
      : '<p class="muted">' + esc(b.summary || t('nicht verfügbar')) + '</p>') + '</div>';
  $$('[data-journal]', el).forEach((btn) => btn.addEventListener('click', async () => {
    const r = await api('/api/services/journal?unit=' + encodeURIComponent(btn.dataset.journal) + '&user=' + btn.dataset.user);
    dialog(t('Protokoll: {0}', btn.dataset.journal), '<pre class="log">' + esc(r.text || r.error) + '</pre>');
  }));
  $$('[data-restart]', el).forEach((btn) => btn.addEventListener('click', async () => {
    const user = btn.dataset.user === '1';
    if (!await confirmDlg(t('Dienst neu starten'), '<p>' + esc(t('{0} wird neu gestartet.', btn.dataset.restart)) + '</p>' + (user ? '' : adminNote()))) return;
    await runJob('restart-unit', { unit: btn.dataset.restart, user }, $('#s-job'), () => setTimeout(() => go('services'), 1500));
  }));
};

PAGES.disks = async (el) => {
  const d = await api('/api/disks');
  const smart = d.smart;
  const tr = d.trim;
  el.innerHTML = '<div class="card"><h2>' + esc(t('Dateisysteme')) + '</h2><div class="table-wrap"><table><thead><tr><th>' + esc(t('Einhängepunkt')) + '</th><th>' + esc(t('Typ')) +
    '</th><th style="width:30%">' + esc(t('Belegung')) + '</th><th class="num">' + esc(t('Frei')) + '</th></tr></thead><tbody>' +
    d.filesystems.map((f) => '<tr><td><b>' + esc(f.mount) + '</b><div class="muted small">' + esc(f.device) + '</div></td><td>' + esc(f.fstype) +
      (f.notes.length ? '<div class="muted small">' + esc(f.notes.join(' · ')) + '</div>' : '') + '</td><td>' + usageBar(f.percent) +
      '<span class="small muted">' + esc(f.percent) + '%</span></td><td class="num">' + esc(fmtSize(f.avail)) + '<div class="muted small">' + esc(t('von {0}', fmtSize(f.size))) + '</div></td></tr>').join('') +
    '</tbody></table></div></div>' +
    '<div class="grid">' +
    '<div class="card"><h2>' + esc(t('SMART (Laufwerksgesundheit)')) + '</h2>' +
      (!d.smartctl ? '<p class="muted">' + esc(t('smartctl ist nicht installiert (Paket smartmontools).')) + '</p>' :
        (smart ? smart.disks.map((s) => '<div class="row" style="margin-bottom:8px"><span class="dot ' + (s.passed ? 'ok' : s.passed === false ? 'crit' : '') + '"></span><b>' + esc(s.device) + '</b><span class="muted small">' + esc(s.model) + '</span><span class="spacer"></span>' +
          '<span class="badge ' + (s.passed ? 'ok' : s.passed === false ? 'crit' : '') + '">' + esc(s.passed ? t('in Ordnung') : s.passed === false ? t('WARNUNG') : t('nicht unterstützt')) + '</span>' +
          (s.temp ? '<span class="small muted">' + esc(s.temp) + ' °C</span>' : '') + (s.warnings.length ? '<div class="small" style="width:100%;color:var(--warn)">' + esc(s.warnings.join(', ')) + '</div>' : '') + '</div>').join('') || '<p class="muted">–</p>'
          : '<p class="muted">' + esc(t('Noch nicht geprüft. Das Lesen der SMART-Werte braucht Administratorrechte (nur lesend).')) + '</p>') +
        '<button class="btn primary" id="smart-btn">' + esc(t('SMART prüfen')) + '</button>') + '<div id="smart-job"></div></div>' +
    '<div class="card"><h2>TRIM (SSD)</h2>' + (!tr.available ? na() :
      '<p>' + esc(tr.enabled ? t('Der wöchentliche TRIM-Dienst (fstrim.timer) ist eingeschaltet.') : t('Der wöchentliche TRIM-Dienst (fstrim.timer) ist ausgeschaltet.')) + '</p>' +
      (tr.enabled ? '' : '<button class="btn primary" data-fix="enable-fstrim">' + esc(t('Einschalten')) + '</button>')) + '</div>' +
    '</div>' +
    '<div class="card"><h2>' + esc(t('Geräte')) + '</h2>' + (d.devices === null ? na() : '<div class="table-wrap"><table><thead><tr><th>' + esc(t('Name')) + '</th><th>' + esc(t('Typ')) + '</th><th class="num">' + esc(t('Größe')) +
      '</th><th>' + esc(t('Dateisystem')) + '</th><th>' + esc(t('Eingehängt')) + '</th><th>' + esc(t('Modell')) + '</th></tr></thead><tbody>' +
      d.devices.map((x) => '<tr><td style="padding-left:' + (10 + x.depth * 18) + 'px">' + (x.depth ? '└ ' : '') + esc(x.name) + '</td><td>' + esc(x.type) +
        (x.type === 'disk' ? ' <span class="muted small">' + esc(x.rota === true || x.rota === '1' ? 'HDD' : 'SSD') + (x.tran ? ' · ' + esc(x.tran) : '') + '</span>' : '') +
        '</td><td class="num">' + esc(fmtSize(x.size)) + '</td><td>' + esc(x.fstype || '') + (x.fstype === 'crypto_LUKS' ? ' <span class="badge ok">' + esc(t('verschlüsselt')) + '</span>' : '') + '</td><td>' + esc(x.mountpoint || '') + '</td><td class="muted">' + esc(x.model || '') + '</td></tr>').join('') +
      '</tbody></table></div>') + '</div>';
  bindCommon(el);
  const sb = $('#smart-btn');
  if (sb) sb.onclick = async () => {
    if (!await confirmDlg(t('SMART prüfen'), '<p>' + esc(t('Die Gesundheitswerte aller Laufwerke werden gelesen. Es wird nichts verändert.')) + '</p>' + adminNote(), t('Prüfen'))) return;
    await runJob('smart', {}, $('#smart-job'), () => setTimeout(() => go('disks'), 1200));
  };
};

PAGES.security = async (el) => {
  const d = await api('/api/security');
  el.innerHTML = '<div class="card"><h2>' + esc(t('Sicherheitsprüfung')) + '</h2>' + findingsList(d.findings, false) + '</div>' +
    '<div class="card"><h2>' + esc(t('Offene Ports (lauschende Dienste)')) + '</h2>' +
    '<p class="muted small">' + esc(t('"Netzwerk" heißt: von anderen Geräten erreichbar (sofern keine Firewall blockt). Ohne Administratorrechte sind nicht alle Programmnamen sichtbar.')) + '</p>' +
    (d.ports === null ? na() : '<div class="table-wrap"><table><thead><tr><th>' + esc(t('Port')) + '</th><th>' + esc(t('Protokoll')) + '</th><th>' + esc(t('Erreichbar')) + '</th><th>' + esc(t('Programm')) + '</th></tr></thead><tbody>' +
      d.ports.map((p) => '<tr><td><b>' + esc(p.port) + '</b> <span class="muted small">' + esc(p.name) + '</span></td><td>' + esc(p.proto.toUpperCase()) + '</td><td>' +
        (p.public ? '<span class="badge warn">' + esc(t('Netzwerk')) + '</span>' : '<span class="badge ok">' + esc(t('nur lokal')) + '</span>') + ' <span class="muted small">' + esc(p.addr) + '</span></td><td>' + esc(p.process || '–') + '</td></tr>').join('') +
      '</tbody></table></div>') + '</div>';
  bindCommon(el);
};

PAGES.netdiag = async (el) => {
  el.innerHTML = '<div class="card"><p class="muted">' + esc(t('Teste Verbindung …')) + '</p><div class="progress indet"><i></i></div></div>';
  const d = await api('/api/netdiag');
  const w = d.wifi;
  el.innerHTML = '<div class="card"><div class="row"><h2 style="margin:0">' + esc(t('Verbindungstest')) + '</h2><span class="spacer"></span><button class="btn" id="nd-again">' + esc(t('Erneut testen')) + '</button></div>' +
    '<ul class="findings" style="margin-top:8px">' + d.checks.map((c) => '<li class="sev-' + (c.ok ? 'ok' : 'crit') + '"><span class="dot"></span><div class="txt"><b>' + esc(c.title) + '</b><span class="muted">' + esc(c.detail) + '</span></div><span class="badge ' + (c.ok ? 'ok' : 'crit') + '">' + esc(c.ok ? t('OK') : t('Fehler')) + '</span></li>').join('') + '</ul></div>' +
    '<div class="grid"><div class="card"><h2>' + esc(t('Schnittstellen')) + '</h2>' + d.interfaces.map((i) => '<div style="margin-bottom:10px"><b>' + esc(i.name) + '</b> <span class="badge ' + (i.state === 'UP' ? 'ok' : '') + '">' + esc(i.state) + '</span>' +
      '<div class="muted small">' + esc(i.mac) + '</div>' + i.addrs.map((a) => '<div><code>' + esc(a.addr) + '/' + esc(a.prefix) + '</code></div>').join('') + '</div>').join('') + '</div>' +
    '<div class="card"><h2>' + esc(t('Router und DNS')) + '</h2><dl class="kv"><dt>' + esc(t('Gateway')) + '</dt><dd>' + esc(d.route.gateway || '–') + ' (' + esc(d.route.dev || '–') + ')</dd><dt>' + esc(t('DNS-Server')) + '</dt><dd>' + esc((d.dns_servers || []).join(', ') || '–') + '</dd></dl></div>' +
    '<div class="card"><h2>' + esc(t('WLAN')) + '</h2>' + (w === null ? '<p class="muted">' + esc(t('nmcli nicht verfügbar')) + '</p>' : (w && w.ssid !== undefined ? '<dl class="kv"><dt>SSID</dt><dd>' + esc(w.ssid) + '</dd><dt>' + esc(t('Signal')) + '</dt><dd>' + esc(w.signal) + ' %</dd><dt>' + esc(t('Kanal')) + '</dt><dd>' + esc(w.channel) + '</dd><dt>' + esc(t('Rate')) + '</dt><dd>' + esc(w.rate) + '</dd><dt>' + esc(t('Sicherheit')) + '</dt><dd>' + esc(w.security) + '</dd></dl>' : '<p class="muted">' + esc(t('Kein WLAN verbunden.')) + '</p>')) + '</div></div>';
  $('#nd-again').onclick = () => go('netdiag');
};

function scanTable(r) {
  return '<div class="card"><div class="row"><h2 style="margin:0">' + esc(t('{0} Geräte in {1}', r.devices.length, r.network)) + '</h2><span class="spacer"></span>' +
    '<button class="btn primary" id="nd-report">' + esc(t('Bericht öffnen / als PDF drucken')) + '</button></div>' +
    '<div class="table-wrap" style="margin-top:10px"><table><thead><tr><th>IP</th><th>' + esc(t('Name / Typ')) + '</th><th>' + esc(t('MAC / Hersteller')) + '</th><th>' + esc(t('Offene Ports')) + '</th><th>' + esc(t('Hinweise')) + '</th></tr></thead><tbody>' +
    r.devices.map((d) => '<tr><td><b>' + esc(d.ip) + '</b>' + (d.is_self ? ' <span class="badge info">' + esc(t('dieser PC')) + '</span>' : '') + (d.is_gateway ? ' <span class="badge info">' + esc(t('Router')) + '</span>' : '') +
      '</td><td>' + esc(d.hostname || '–') + '<div class="muted small">' + esc(d.type) + '</div></td><td><code>' + esc(d.mac || '–') + '</code><div class="muted small">' + esc(d.vendor) + '</div></td><td class="small">' + esc(d.ports.join(', ') || '–') +
      '</td><td>' + d.findings.map((f) => '<div class="small"><span class="dot ' + esc(f.severity === 'crit' ? 'crit' : f.severity) + '" style="display:inline-block;margin:0 6px 0 0"></span>' + esc(f.text) + '</div>').join('') + '</td></tr>').join('') +
    '</tbody></table></div></div>';
}

PAGES.netdoc = async (el) => {
  const d = await api('/api/netscan/info');
  const n = d.network;
  el.innerHTML = '<div class="notice warn"><b>' + esc(t('Nur im eigenen Netzwerk verwenden.')) + '</b> ' + esc(t('Das Scannen fremder Netze ist ohne Erlaubnis verboten.')) + '</div>' +
    '<div class="card"><h2>' + esc(t('Netzwerk dokumentieren')) + '</h2>' +
    (n ? '<p>' + esc(t('Gescannt wird nur das eigene Netz {0} über {1} (eigene IP {2}).', n.prefix < 24 ? n.ip.replace(/\.\d+$/, '.0') + '/24' : n.network, n.iface, n.ip)) + '</p>' +
      '<p class="muted small">' + esc(t('Ping, ARP-Tabelle und ca. 30 typische Ports je Gerät. Dauert meist 20–60 Sekunden. Keine Administratorrechte nötig.')) + '</p>' +
      '<button class="btn primary" id="scan-btn">' + esc(t('Scan starten')) + '</button>'
      : '<p class="muted">' + esc(t('Keine aktive IPv4-Verbindung gefunden.')) + '</p>') + '<div id="scan-job"></div></div><div id="scan-res"></div>';
  const show = (r) => {
    if (!r || !r.devices) return;
    $('#scan-res').innerHTML = scanTable(r);
    $('#nd-report').onclick = async () => {
      const rep = await api('/api/netscan/report');
      const url = URL.createObjectURL(new Blob([rep.html], { type: 'text/html' }));
      const w = window.open(url, '_blank');
      if (!w) toast(t('Bitte Pop-ups für PC-Tools erlauben.'));
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    };
  };
  show(d.last);
  const sb = $('#scan-btn');
  if (sb) sb.onclick = async () => {
    if (!await confirmDlg(t('Netzwerk scannen'), '<p>' + esc(t('Ich bestätige, dass dies mein eigenes Netzwerk ist oder ich die Erlaubnis zum Scannen habe.')) + '</p>', t('Scan starten'))) return;
    sb.disabled = true;
    await runJob('netscan', {}, $('#scan-job'), (r) => show(r));
    sb.disabled = false;
  };
};

// ------------------------------------------------------------------ KI-Assistent
const chatState = { msgs: [] };

function renderMarkdown(text) {
  // Kleine, sichere Markdown-Darstellung: zuerst maskieren, dann Formatierung.
  const blocks = String(text).split(/```/);
  return blocks.map((b, i) => {
    if (i % 2 === 1) return '<pre>' + esc(b.replace(/^[a-zA-Z]*\n/, '')) + '</pre>';
    const lines = esc(b).split('\n');
    let out = '', list = null;
    const inline = (s) => s.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/`([^`]+)`/g, '<code>$1</code>');
    for (const ln of lines) {
      const ul = ln.match(/^\s*[-*]\s+(.*)/), ol = ln.match(/^\s*\d+[.)]\s+(.*)/);
      const want = ul ? 'ul' : ol ? 'ol' : null;
      if (list && want !== list) { out += '</' + list + '>'; list = null; }
      if (want) { if (!list) { out += '<' + want + '>'; list = want; } out += '<li>' + inline((ul || ol)[1]) + '</li>'; continue; }
      const hd = ln.match(/^#{1,4}\s+(.*)/);
      if (hd) { out += '<p><b>' + inline(hd[1]) + '</b></p>'; continue; }
      if (ln.trim()) out += '<p>' + inline(ln) + '</p>';
    }
    if (list) out += '</' + list + '>';
    return out;
  }).join('');
}

function drawMsgs() {
  const box = $('#msgs');
  if (!box) return;
  if (!chatState.msgs.length) {
    const sugg = [t('Warum ist mein PC langsam?'), t('Ist mein PC sicher?'), t('Erkläre mir die Befunde der Übersicht.'), t('Wie mache ich ein Backup unter Linux?')];
    box.innerHTML = '<p class="muted">' + esc(t('Stell eine Frage zu deinem Linux-Rechner. Die KI erklärt in einfachen Worten – sie kann selbst nichts ausführen.')) + '</p>' +
      '<div class="suggest">' + sugg.map((s) => '<button class="btn small" data-sugg="' + esc(s) + '">' + esc(s) + '</button>').join('') + '</div>';
    $$('[data-sugg]', box).forEach((b) => b.addEventListener('click', () => sendChat(b.dataset.sugg)));
    return;
  }
  box.innerHTML = chatState.msgs.map((m) => '<div class="msg ' + esc(m.role) + (m.error ? ' err' : '') + '"><div class="bubble">' +
    (m.role === 'user' ? esc(m.content).replace(/\n/g, '<br>') : renderMarkdown(m.content)) + '</div></div>').join('') +
    (chatState.waiting ? '<div class="msg assistant"><div class="bubble muted">' + esc(t('Denkt nach …')) + '</div></div>' : '');
  box.scrollTop = box.scrollHeight;
}

async function sendChat(text) {
  text = (text || '').trim();
  if (!text || chatState.waiting) return;
  chatState.msgs.push({ role: 'user', content: text });
  chatState.waiting = true;
  drawMsgs();
  const sel = $('#ai-provider').value;
  const hist = chatState.msgs.filter((m) => !m.error).map((m) => ({ role: m.role, content: m.content }));
  let r;
  try {
    r = await api('/api/ai/chat', { provider: sel, model: $('#ai-model').value, messages: hist, context: $('#ai-ctx').checked });
  } catch (e) { r = { error: e.message }; }
  chatState.waiting = false;
  if (r.error) chatState.msgs.push({ role: 'assistant', content: r.error, error: true });
  else chatState.msgs.push({ role: 'assistant', content: r.text || t('(keine Antwort)') });
  drawMsgs();
}

PAGES.ai = async (el) => {
  const d = await api('/api/ai/providers');
  el.innerHTML = '<div class="chat-layout"><div class="card chat"><div class="msgs" id="msgs"></div><div class="composer">' +
    '<textarea id="ai-input" placeholder="' + esc(t('Frage eingeben … (Enter = senden, Umschalt+Enter = neue Zeile)')) + '"></textarea>' +
    '<div style="display:flex;flex-direction:column;gap:6px"><button class="btn primary" id="ai-send">' + esc(t('Senden')) + '</button><button class="btn small" id="ai-new">' + esc(t('Neues Gespräch')) + '</button></div></div></div>' +
    '<div><div class="card"><h2>' + esc(t('Verbindung zur KI')) + '</h2>' +
    '<label class="field"><span>' + esc(t('Anbieter')) + '</span><select id="ai-provider">' + d.providers.map((p) => '<option value="' + esc(p.id) + '"' + (p.id === d.selected ? ' selected' : '') + '>' + esc(p.label) + '</option>').join('') + '</select></label>' +
    '<label class="field"><span>' + esc(t('Modell')) + '</span><input type="text" id="ai-model" list="ai-models" spellcheck="false"><datalist id="ai-models"></datalist></label>' +
    '<div id="ai-custom" hidden><label class="field"><span>' + esc(t('Adresse (bis /chat/completions)')) + '</span><input type="url" id="ai-url" placeholder="http://localhost:1234/v1/chat/completions" value="' + esc(d.custom_url) + '"></label></div>' +
    '<div id="ai-keybox"><label class="field"><span id="ai-keylabel"></span><input type="password" id="ai-key" autocomplete="off" spellcheck="false"></label>' +
    '<div class="row"><button class="btn small" id="ai-keysave">' + esc(t('Schlüssel speichern')) + '</button><button class="btn small danger" id="ai-keydel">' + esc(t('Löschen')) + '</button><a id="ai-keyurl" class="small" target="_blank" rel="noopener noreferrer"></a></div></div>' +
    '<label class="check"><input type="checkbox" id="ai-ctx"' + (d.context ? ' checked' : '') + '><span>' + esc(t('Systemübersicht und Befunde mitsenden')) + ' <a href="#" id="ai-preview" class="small">' + esc(t('Vorschau')) + '</a></span></label>' +
    '<p class="muted small" id="ai-where"></p></div><div class="card" id="ollama-box" hidden></div></div></div>';
  const prov = () => d.providers.find((p) => p.id === $('#ai-provider').value);
  const save = async (extra) => {
    const p = prov();
    const nd = await api('/api/ai/settings', Object.assign({ provider: p.id, model: $('#ai-model').value, context: $('#ai-ctx').checked }, extra || {}));
    d.providers = nd.providers;
  };
  const refreshProv = () => {
    const p = prov();
    $('#ai-model').value = p.model || '';
    $('#ai-models').innerHTML = p.models.map((m) => '<option value="' + esc(m) + '">').join('');
    $('#ai-custom').hidden = p.id !== 'custom';
    $('#ai-keybox').hidden = p.id === 'ollama';
    $('#ai-keylabel').textContent = p.has_key ? t('API-Schlüssel (gespeichert – zum Ändern neu eingeben)') : (p.need_key ? t('API-Schlüssel') : t('API-Schlüssel (optional)'));
    $('#ai-key').value = '';
    const ku = $('#ai-keyurl');
    ku.textContent = p.key_url ? t('Schlüssel holen') : '';
    if (p.key_url) ku.href = p.key_url; else ku.removeAttribute('href');
    $('#ai-where').textContent = t('Deine Fragen gehen an: {0}', p.where);
    $('#ollama-box').hidden = p.id !== 'ollama';
    if (p.id === 'ollama') drawOllama();
  };
  const drawOllama = async () => {
    const box = $('#ollama-box');
    box.innerHTML = '<p class="muted">' + esc(t('Prüfe Ollama …')) + '</p>';
    const o = await api('/api/ai/ollama');
    const model = $('#ai-model').value || o.recommended;
    box.innerHTML = '<h2>' + esc(t('Ollama einrichten')) + '</h2>' +
      '<p><span class="dot ' + (o.installed ? 'ok' : 'warn') + '" style="display:inline-block;margin:0 6px 0 0"></span>' + esc(o.installed ? t('Ollama ist installiert.') : t('Ollama ist noch nicht installiert.')) + '<br>' +
      '<span class="dot ' + (o.running ? 'ok' : 'warn') + '" style="display:inline-block;margin:0 6px 0 0"></span>' + esc(o.running ? t('Ollama läuft.') : t('Ollama läuft nicht.')) + '</p>' +
      (!o.installed ? '<p class="small">' + esc(t('1. Terminal öffnen und diesen offiziellen Befehl selbst ausführen (PC-Tools führt ihn nicht automatisch aus):')) + '</p><pre class="log">' + esc(o.install_cmd) + '</pre>' +
        '<div class="row"><button class="btn small" id="ol-copy">' + esc(t('Befehl kopieren')) + '</button><a class="small" href="https://ollama.com/download/linux" target="_blank" rel="noopener noreferrer">ollama.com</a></div>' : '') +
      (o.running ? '<p class="small">' + esc(t('Geladene Modelle: {0}', o.models.join(', ') || t('keine'))) + '</p>' : '<p class="small muted">' + esc(t('Nach der Installation startet Ollama meist automatisch. Sonst im Terminal: ollama serve')) + '</p>') +
      '<p class="small">' + esc(t('Empfohlen für diesen PC: {0}. qwen3:4b braucht ca. 8 GB RAM (Download ca. 2,5 GB), qwen3:8b ca. 16 GB.', o.recommended)) + '</p>' +
      '<div class="row"><button class="btn primary small" id="ol-pull"' + (o.running ? '' : ' disabled') + '>' + esc(t('Modell {0} laden', model)) + '</button><button class="btn small" id="ol-re">' + esc(t('Erneut prüfen')) + '</button></div><div id="ol-job"></div>';
    const cp = $('#ol-copy');
    if (cp) cp.onclick = () => navigator.clipboard.writeText(o.install_cmd).then(() => toast(t('Kopiert.')), () => toast(t('Kopieren nicht möglich – bitte markieren und kopieren.')));
    $('#ol-re').onclick = drawOllama;
    $('#ol-pull').onclick = () => runJob('ollama-pull', { model }, $('#ol-job'), () => setTimeout(drawOllama, 800));
  };
  $('#ai-provider').onchange = async () => { refreshProv(); await save(); };
  $('#ai-model').onchange = () => save();
  $('#ai-ctx').onchange = () => save();
  $('#ai-url').onchange = () => save({ custom_url: $('#ai-url').value });
  $('#ai-keysave').onclick = async () => {
    const r = await api('/api/ai/key', { provider: prov().id, key: $('#ai-key').value });
    if (r.error) toast(r.error); else { toast(t('Schlüssel gespeichert (nur für deinen Benutzer lesbar).')); prov().has_key = !!$('#ai-key').value; refreshProv(); }
  };
  $('#ai-keydel').onclick = async () => {
    await api('/api/ai/key', { provider: prov().id, key: '' });
    prov().has_key = false; refreshProv(); toast(t('Schlüssel gelöscht.'));
  };
  $('#ai-preview').onclick = async (e) => {
    e.preventDefault();
    const c = await api('/api/ai/context');
    dialog(t('Diese Daten würden mitgesendet'), '<pre class="log">' + esc(c.text) + '</pre>');
  };
  const input = $('#ai-input');
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); const v = input.value; input.value = ''; sendChat(v); } });
  $('#ai-send').onclick = () => { const v = input.value; input.value = ''; sendChat(v); };
  $('#ai-new').onclick = () => { chatState.msgs = []; drawMsgs(); };
  refreshProv();
  drawMsgs();
};

// ------------------------------------------------------------------ Einstellungen
PAGES.settings = async (el) => {
  const s = INIT.settings;
  el.innerHTML = '<div class="grid">' +
    '<div class="card"><h2>' + esc(t('Darstellung')) + '</h2>' +
    '<label class="field"><span>' + esc(t('Sprache')) + '</span><select id="set-lang">' + INIT.languages.map((l) => '<option value="' + esc(l.code) + '"' + (l.code === INIT.lang ? ' selected' : '') + '>' + esc(l.name) + '</option>').join('') + '</select></label>' +
    '<label class="field"><span>' + esc(t('Design')) + '</span><select id="set-theme">' +
      [['auto', t('Wie das System')], ['light', t('Hell')], ['dark', t('Dunkel')]].map((o) => '<option value="' + o[0] + '"' + (s.theme === o[0] ? ' selected' : '') + '>' + esc(o[1]) + '</option>').join('') + '</select></label></div>' +
    '<div class="card"><h2>' + esc(t('Über PC-Tools')) + '</h2><dl class="kv"><dt>' + esc(t('Version')) + '</dt><dd>' + esc(INIT.version) + '</dd><dt>' + esc(t('Lizenz')) + '</dt><dd>Apache-2.0 (' + esc(t('kostenlos, Open Source')) + ')</dd>' +
      '<dt>GitHub</dt><dd><a href="' + esc(INIT.github) + '" target="_blank" rel="noopener noreferrer">' + esc(INIT.github.replace('https://', '')) + '</a></dd>' +
      '<dt>' + esc(t('Adminrechte über')) + '</dt><dd>' + esc(INIT.root_method || t('nicht verfügbar')) + '</dd><dt>' + esc(t('Einstellungen')) + '</dt><dd><code>' + esc(INIT.config_dir) + '</code></dd></dl></div>' +
    '</div><div class="card"><h2>' + esc(t('Datenschutz')) + '</h2><ul>' +
      '<li>' + esc(t('PC-Tools läuft nur auf deinem Rechner. Die Oberfläche ist eine lokale Webseite (127.0.0.1), die nur mit einem zufälligen Schlüssel erreichbar ist.')) + '</li>' +
      '<li>' + esc(t('Es gibt keine Telemetrie, keine Werbung und keine Konten. Die Oberfläche lädt nichts aus dem Internet.')) + '</li>' +
      '<li>' + esc(t('Internetzugriffe nur auf deinen Wunsch: Updates über die Paketverwaltung deiner Distribution, der Verbindungstest (1.1.1.1, 9.9.9.9, example.org, wikipedia.org) und der KI-Assistent.')) + '</li>' +
      '<li>' + esc(t('KI-Assistent: Mit Ollama bleibt alles auf diesem PC. Bei Online-Anbietern gehen deine Frage und – nur wenn angehakt – die Systemübersicht (ohne Rechner- und Benutzernamen) an den gewählten Anbieter.')) + '</li>' +
      '<li>' + esc(t('API-Schlüssel liegen in ~/.config/pc-tools/keys.json, nur für deinen Benutzer lesbar (Rechte 600), und werden nie protokolliert.')) + '</li>' +
      '<li>' + esc(t('Der Netzwerk-Scan bleibt im eigenen Netz; der Bericht wird nur lokal erzeugt.')) + '</li></ul></div>' +
    '<div class="card"><button class="btn danger" id="set-quit">' + esc(t('PC-Tools beenden')) + '</button></div>';
  $('#set-lang').onchange = async (e) => { await setLanguage(e.target.value); };
  $('#set-theme').onchange = async (e) => {
    const r = await api('/api/settings', { theme: e.target.value });
    INIT.settings = r.settings; applyTheme();
  };
  $('#set-quit').onclick = quit;
};

// ------------------------------------------------------------------ Navigation
const TITLES = {
  overview: 'Übersicht', updates: 'Updates', cleanup: 'Aufräumen', autostart: 'Autostart', services: 'Dienste',
  disks: 'Datenträger', security: 'Sicherheit', netdiag: 'Netzwerk-Diagnose', netdoc: 'Netzwerk dokumentieren',
  ai: 'KI-Assistent', settings: 'Einstellungen',
};

async function go(page) {
  if (!PAGES[page]) page = 'overview';
  currentPage = page;
  try { localStorage.setItem('pct-page', page); } catch (e) { /* egal */ }
  $$('.nav button[data-page]').forEach((b) => b.classList.toggle('active', b.dataset.page === page));
  $('#nav').classList.remove('open');
  $('#page-title').textContent = t(TITLES[page]);
  const seq = ++renderSeq;
  // Jede Seite rendert in einen eigenen Container; ein Seitenwechsel ersetzt ihn.
  const holder = document.createElement('div');
  holder.innerHTML = '<p class="muted">' + esc(t('Wird geladen …')) + '</p>';
  const el = $('#content');
  el.innerHTML = '';
  el.appendChild(holder);
  setBusy(true);
  try {
    await PAGES[page](holder);
  } catch (e) {
    if (seq === renderSeq) holder.innerHTML = '<div class="card"><p class="muted">' + esc(t('Fehler: {0}', e.message)) + '</p></div>';
  } finally {
    if (seq === renderSeq) setBusy(false);
  }
}

function applyStaticTexts() {
  $$('[data-t]').forEach((n) => { n.textContent = t(n.dataset.t); });
  document.documentElement.lang = (INIT && INIT.lang ? INIT.lang.slice(0, 2) : 'de');
}

function applyTheme() {
  const th = INIT.settings.theme || 'auto';
  if (th === 'auto') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.setAttribute('data-theme', th);
}

async function loadLang(code) {
  STR = {};
  if (!code || code === 'de-DE') return;
  try {
    const r = await fetch('/lang/' + encodeURIComponent(code) + '.json');
    const data = await r.json();
    Object.entries(data.strings || {}).forEach(([k, v]) => { if (v) STR[k] = v; });
  } catch (e) { /* fehlende Übersetzung -> Deutsch */ }
}

async function setLanguage(code) {
  const r = await api('/api/settings', { lang: code });
  INIT.settings = r.settings;
  INIT.lang = r.lang;
  await loadLang(r.lang);
  applyStaticTexts();
  go(currentPage);
}

async function chooseLanguage() {
  const html = '<p class="muted">Bitte wähle deine Sprache · Please choose your language</p><div class="lang-grid">' +
    INIT.languages.map((l) => '<button type="button" class="btn" data-lang="' + esc(l.code) + '">' + esc(l.name) + '</button>').join('') + '</div>';
  const p = dialog('PC-Tools', html, []);
  $$('[data-lang]', $('#dlg')).forEach((b) => b.addEventListener('click', () => { $('#dlg').close(); setLanguage(b.dataset.lang); }));
  return p;
}

async function quit() {
  if (!await confirmDlg(t('PC-Tools beenden'), '<p>' + esc(t('Das Programm wird beendet. Dieses Fenster kann danach geschlossen werden.')) + '</p>', t('Beenden'))) return;
  try { await api('/api/shutdown', {}); } catch (e) { /* Server ist schon weg */ }
  document.body.innerHTML = '<div style="padding:40px;font:16px system-ui">' + esc(t('PC-Tools wurde beendet. Du kannst dieses Fenster schließen.')) + '</div>';
}

async function start() {
  if (!TOKEN) {
    showBanner(t('Kein Zugriffsschlüssel. Bitte PC-Tools über das Startmenü oder den Befehl pc-tools öffnen.'), true);
    return;
  }
  INIT = await api('/api/init');
  await loadLang(INIT.lang);
  applyTheme();
  applyStaticTexts();
  $$('.nav button[data-page]').forEach((b) => b.addEventListener('click', () => go(b.dataset.page)));
  $('#quit-btn').addEventListener('click', quit);
  $('#menu-btn').addEventListener('click', () => $('#nav').classList.toggle('open'));
  window.addEventListener('pagehide', () => {
    try { navigator.sendBeacon('/api/bye', new Blob([TOKEN], { type: 'text/plain' })); } catch (e) { /* egal */ }
  });
  let page = 'overview';
  try { page = localStorage.getItem('pct-page') || 'overview'; } catch (e) { /* egal */ }
  go(page);
  if (INIT.first_run) chooseLanguage();
}

start();
