// Consent notice and usage logging for the trial site. Nothing is sent unless the visitor agrees.
// One function, one job. Last edited: 2026-11-18: exposed as window.SCLOG (window.SC is the query engine now);
// endpoint '/' means the Worker that serves the site.
(function () {
  const cfg = window.SC_CONFIG || {};
  const KEY_CONSENT = 'sc-consent', KEY_SESSION = 'sc-session';
  let memory = {};

  /** Read a stored value; falls back to memory when storage is unavailable. */
  function load(key) { try { return localStorage.getItem(key) || memory[key] || null; } catch (e) { return memory[key] || null; } }
  /** Store a value; keeps it in memory when storage is unavailable. */
  function save(key, value) { memory[key] = value; try { localStorage.setItem(key, value); } catch (e) {} }

  /** Random 20-character id that identifies this browser, not the person. */
  function sessionId() {
    let id = load(KEY_SESSION);
    if (!id) { const bytes = crypto.getRandomValues(new Uint8Array(20)); id = [...bytes].map(b => 'abcdefghijklmnopqrstuvwxyz0123456789'[b % 36]).join(''); save(KEY_SESSION, id); }
    return id;
  }

  /** Trial group code from the ?g= link, e.g. a club or a bookshop. */
  function groupCode() { const g = new URLSearchParams(location.search).get('g') || ''; return /^[A-Za-z0-9_-]{1,24}$/.test(g) ? g : ''; }

  /** Send one event when logging is configured and the visitor agreed. */
  function log(type, data) {
    if (!cfg.endpoint || load(KEY_CONSENT) !== 'yes') return;
    const body = JSON.stringify(Object.assign({ type, session: sessionId(), group: groupCode() }, data || {}));
    try { fetch(cfg.endpoint.replace(/\/$/, '') + '/log', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body, keepalive: true }).catch(() => {}); } catch (e) {}
  }

  /** Record the visitor's choice and remove the notice. */
  function decide(choice, box) { save(KEY_CONSENT, choice); box.remove(); if (choice === 'yes') log('consent', {}); }

  /** Show the consent notice once, only when logging is configured. */
  function showNotice() {
    if (!cfg.endpoint || load(KEY_CONSENT)) return;
    const box = document.createElement('div'); box.id = 'sc-consent';
    box.style.cssText = 'position:fixed;left:16px;right:16px;bottom:16px;max-width:720px;margin:0 auto;z-index:50;background:var(--card,#fff);color:var(--ink,#111);border:1.5px solid var(--ink,#111);border-radius:12px;padding:16px 18px;font-size:14px;line-height:1.6;box-shadow:6px 6px 0 var(--ink,#111)';
    box.innerHTML = '<b>使用紀錄說明</b><br>本網站為測試版。若你同意，我們會記錄你輸入的問句、點選的來源連結與使用時間，用於改善系統。'
      + '不會記錄姓名、信箱或 IP 位址；請勿在問句中輸入個人資料。線上紀錄保存至 ' + (cfg.retention || '測試結束') + '，之後刪除。不同意仍可正常使用。'
      + '<div style="margin-top:10px;display:flex;gap:10px;flex-wrap:wrap"><button id="sc-yes" style="font:inherit;font-weight:700;padding:7px 16px;border-radius:8px;border:1.5px solid var(--ink,#111);background:var(--ink,#111);color:var(--bg,#fff);cursor:pointer">同意並開始</button>'
      + '<button id="sc-no" style="font:inherit;padding:7px 16px;border-radius:8px;border:1.5px solid var(--ink,#111);background:transparent;color:inherit;cursor:pointer">不同意，仍要使用</button></div>';
    document.body.appendChild(box);
    box.querySelector('#sc-yes').onclick = () => decide('yes', box);
    box.querySelector('#sc-no').onclick = () => decide('no', box);
  }

  /** Add the feedback button to the top bar when a form link is configured. */
  function addFeedbackButton() {
    if (!cfg.formUrl) return;
    const top = document.querySelector('.top'); if (!top) return;
    const a = document.createElement('a'); a.href = cfg.formUrl; a.target = '_blank'; a.rel = 'noopener'; a.textContent = '填寫回饋';
    a.className = 'icon-btn'; a.style.cssText = 'width:auto;padding:0 12px;font-size:13px;font-weight:700;text-decoration:none;display:inline-flex;align-items:center';
    top.insertBefore(a, document.getElementById('theme'));
  }

  /** Log clicks on source links inside answers. */
  function watchSourceClicks() {
    document.addEventListener('click', e => { const a = e.target.closest && e.target.closest('#thread a[href^="http"]'); if (a) log('click', { target: a.href.slice(0, 300) }); });
  }

  window.SCLOG = { log };
  document.addEventListener('DOMContentLoaded', () => { showNotice(); addFeedbackButton(); watchSourceClicks(); });
})();
