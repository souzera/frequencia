'use strict';
const $ = id => document.getElementById(id);
let api, state, selected = new Set(), signature = '', busy = false, classifyVersion = 0;
const phases = new Set(['inspecting', 'downloading', 'cancelling']);
function notice(message, error = false) { $('notice').textContent = message || ''; $('notice').hidden = !message; $('notice').className = error ? 'error' : ''; }
async function call(method, ...args) { try { const result = await api[method](...args); if (result?.ok === false) notice(result.error, true); return result; } catch (e) { notice('Não foi possível concluir a operação. ' + e.message, true); return null; } }
const breadcrumbs = { downloads: 'Biblioteca / Downloads', settings: 'Biblioteca / Configurações', about: 'Biblioteca / Nota técnica' };
function navigate(page) { for (const name of ['downloads', 'settings', 'about']) $(name).hidden = name !== page; document.querySelectorAll('.nav').forEach(b => b.classList.toggle('active', b.dataset.page === page)); $('breadcrumb').textContent = breadcrumbs[page]; }
document.querySelectorAll('.nav').forEach(b => b.onclick = () => navigate(b.dataset.page));
document.querySelector('.brand').onclick = e => { e.preventDefault(); navigate('downloads'); };
function duration(n) { return Number.isFinite(n) ? `${Math.floor(n / 60)}:${String(Math.floor(n % 60)).padStart(2, '0')}` : '—'; }
function updateSelection() { const eligible = state.tracks.filter(t => t.status !== 'done'); const count = eligible.filter(t => selected.has(t.id)).length; $('selected-count').textContent = `${count} ${count === 1 ? 'música selecionada' : 'músicas selecionadas'}`; $('select-all').checked = !!eligible.length && count === eligible.length; $('select-all').indeterminate = count > 0 && count < eligible.length; $('select-all').disabled = busy; $('download').disabled = busy || !count; }
function buildTracks() {
  const fragment = document.createDocumentFragment();
  for (const track of state.tracks) {
    const row = document.createElement('div'); row.className = 'track'; row.dataset.id = track.id;
    const check = document.createElement('input'); check.type = 'checkbox'; check.checked = selected.has(track.id); check.setAttribute('aria-label', 'Selecionar ' + track.title); check.onchange = () => { check.checked ? selected.add(track.id) : selected.delete(track.id); updateSelection(); };
    const icon = document.createElement('span'); icon.className = 'track-icon'; icon.textContent = '♪'; icon.setAttribute('aria-hidden', 'true');
    const text = document.createElement('div'); text.className = 'track-text';
    const title = document.createElement('span'); title.className = 'track-title'; title.textContent = track.title; title.title = track.title;
    const artist = document.createElement('span'); artist.className = 'track-artist'; artist.textContent = track.artist;
    const match = document.createElement('div'); match.className = 'matched';
    const error = document.createElement('div'); error.className = 'track-error';
    text.append(title, artist, match, error);
    const status = document.createElement('span'); status.className = 'track-status';
    row.append(check, icon, text, status); fragment.append(row);
  }
  $('tracks').replaceChildren(fragment);
}
function render(next) {
  state = next; busy = phases.has(state.phase);
  const nextSignature = JSON.stringify(state.tracks.map(t => [t.id, t.url, t.title]));
  if (nextSignature !== signature) { signature = nextSignature; selected = new Set(state.tracks.map(t => t.id)); buildTracks(); }
  $('inspect').disabled = busy; $('url').disabled = busy; $('include-playlist').disabled = busy;
  $('cancel').hidden = !busy; $('cancel').disabled = state.phase === 'cancelling';
  $('loading').hidden = state.phase !== 'inspecting'; $('empty').hidden = state.tracks.length > 0 || state.phase === 'inspecting'; $('selection').hidden = !state.tracks.length;
  $('list-title').textContent = state.title || 'Sua seleção'; $('count').textContent = `${state.tracks.length} ${state.tracks.length === 1 ? 'música' : 'músicas'}`;
  $('destination').textContent = state.settings.directory; $('destination').title = state.settings.directory; $('quality-label').textContent = state.settings.quality + ' kbps';
  const names = { queued: 'Na fila', downloading: 'Baixando', converting: 'Convertendo…', done: '✓ Salvo', error: 'Falhou', cancelled: 'Cancelado' };
  [...$('tracks').children].forEach((row, i) => {
    const t = state.tracks[i]; row.querySelector('input').disabled = busy || t.status === 'done'; if (t.status === 'done') { selected.delete(t.id); row.querySelector('input').checked = false; }
    const status = row.querySelector('.track-status'); status.className = 'track-status ' + (t.status || ''); status.textContent = t.status === 'downloading' ? `Baixando ${t.percent || 0}%` : (names[t.status] || duration(t.duration));
    row.querySelector('.track-error').textContent = t.error || ''; row.querySelector('.matched').textContent = t.matched_title ? 'Áudio encontrado: ' + t.matched_title : '';
  });
  const done = state.tracks.filter(t => t.status === 'done').length, errors = state.tracks.filter(t => t.status === 'error').length;
  $('progress-label').textContent = busy ? `Processando ${state.current || 0} de ${state.total || state.tracks.length} · ${done} salvas` : state.phase === 'complete' ? `${done} salvas${errors ? ` · ${errors} com falha. Tente baixar novamente.` : ' · Tudo pronto para ouvir.'}` : state.phase === 'cancelled' ? 'Cancelado. As músicas já salvas foram mantidas.' : 'Tudo pronto para baixar.';
  if (state.error) notice(state.error, true);
  updateSelection();
}
async function refresh() { if (api) { const next = await call('get_state'); if (next) render(next); } setTimeout(refresh, 650); }
$('url').addEventListener('input', async () => {
  const version = ++classifyVersion; $('playlist-choice').hidden = true; $('include-playlist').checked = false; $('link-type').textContent = ''; if (!api || !$('url').value.trim()) return;
  const link = await api.classify_link($('url').value); if (version !== classifyVersion) return;
  if (link.ok) { $('link-type').textContent = `${link.source === 'spotify' ? 'Spotify' : 'YouTube'} · ${link.kind === 'playlist' ? 'Playlist' : 'Individual'}`; $('playlist-choice').hidden = !link.playlist_url; }
});
$('link-form').onsubmit = async e => { e.preventDefault(); notice(''); $('inspect').disabled = true; await call('inspect_link', $('url').value, $('include-playlist').checked); const next = await call('get_state'); if (next) render(next); };
$('select-all').onchange = () => { state.tracks.forEach(t => { if (t.status !== 'done') $('select-all').checked ? selected.add(t.id) : selected.delete(t.id); }); [...$('tracks').children].forEach(row => row.querySelector('input').checked = selected.has(row.dataset.id)); updateSelection(); };
$('download').onclick = async () => { notice(''); $('download').disabled = true; await call('download_selected', [...selected]); const next = await call('get_state'); if (next) render(next); };
$('cancel').onclick = async () => { $('cancel').disabled = true; await call('cancel'); };
$('open-folder').onclick = () => call('open_directory');
$('choose-folder').onclick = async () => { const path = await call('choose_directory'); if (path) $('directory').value = path; };
$('settings-form').onsubmit = async e => { e.preventDefault(); const result = await call('save_settings', $('directory').value, $('quality').value); $('settings-message').textContent = result?.ok ? 'Configurações salvas.' : (result?.error || 'Não foi possível salvar.'); };
window.addEventListener('pywebviewready', async () => {
  api = window.pywebview.api; const initial = await call('get_state'); if (!initial) return; render(initial); $('directory').value = state.settings.directory; $('quality').value = state.settings.quality;
  for (const [name, found] of Object.entries(state.dependencies)) { const tag = document.createElement('span'); tag.textContent = `${found ? '✓' : '×'} ${name === 'node' ? 'JavaScript' : name.toUpperCase()}${found ? ' disponível' : ' ausente'}`; tag.className = found ? 'dependency-ok' : 'dependency-error'; $('dependencies').append(tag); }
  refresh();
});
$('inspect').disabled = true;
(function () {
  const lights = document.querySelector('.traffic-lights');
  lights.addEventListener('mousedown', e => e.stopPropagation());
  $('tl-close').onclick = () => api && call('window_close');
  $('tl-minimize').onclick = () => api && call('window_minimize');
  $('tl-maximize').onclick = () => api && call('window_toggle_maximize');
  $('titlebar').addEventListener('dblclick', e => { if (!e.target.closest('.traffic-lights') && api) call('window_toggle_maximize'); });

  const MIN_W = 860, MIN_H = 640;
  let raf = null, pending = null;
  function sendResize(width, height, fixPoint) {
    pending = { width, height, fixPoint };
    if (raf) return;
    raf = requestAnimationFrame(() => { raf = null; if (api && pending) api.window_resize(pending.width, pending.height, pending.fixPoint); });
  }
  function startResize(dirs) {
    return e => {
      e.preventDefault();
      const startX = e.screenX, startY = e.screenY;
      const startW = document.documentElement.clientWidth, startH = document.documentElement.clientHeight;
      function onMove(ev) {
        const dx = ev.screenX - startX, dy = ev.screenY - startY;
        let width = startW, height = startH, fix = 0;
        if (dirs.includes('e')) width = startW + dx;
        if (dirs.includes('w')) { width = startW - dx; fix |= 4; }
        if (dirs.includes('s')) height = startH + dy;
        if (dirs.includes('n')) { height = startH - dy; fix |= 8; }
        sendResize(Math.max(MIN_W, width), Math.max(MIN_H, height), fix);
      }
      function onUp() { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); }
      window.addEventListener('mousemove', onMove);
      window.addEventListener('mouseup', onUp);
    };
  }
  document.querySelectorAll('.resize-handle').forEach(handle => handle.addEventListener('mousedown', startResize(handle.dataset.edges)));
})();
