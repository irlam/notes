/**
 * File: app/static/js/m10.js
 * Purpose: Milestone 10 UI handlers (Email PDF + Batch Export) without inline scripts.
 *
 * Why this exists:
 * - The dashboard uses a strict CSP (script-src 'self'), so inline scripts are blocked.
 * - This module reads feature flags from #app-config data attributes and wires up buttons.
 *
 * Last reviewed (UK date): 03/03/2026
 */

(function () {
  'use strict';

  function getEmailEnabled() {
    var el = document.getElementById('app-config');
    if (!el) return false;
    return el.getAttribute('data-enable-email-export') === '1';
  }

  function showToast(msg, color) {
    color = color || '#444';

    var existing = document.getElementById('m10-toast');
    if (existing) existing.remove();

    var banner = document.createElement('div');
    banner.id = 'm10-toast';
    banner.setAttribute('role', 'status');
    banner.setAttribute('aria-live', 'polite');
    banner.style.cssText = [
      'position:fixed', 'bottom:16px', 'left:50%',
      'transform:translateX(-50%)',
      'background:' + color, 'color:#fff',
      'padding:10px 20px', 'border-radius:6px',
      'font-size:14px', 'z-index:9999',
      'box-shadow:0 2px 8px rgba(0,0,0,.4)'
    ].join(';');

    banner.textContent = msg;
    document.body.appendChild(banner);

    setTimeout(function () {
      if (banner.parentNode) banner.remove();
    }, 4000);
  }

  function wireComingSoon(id) {
    var btn = document.getElementById(id);
    if (!btn) return;
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      showToast('⏳ Coming soon — this feature is planned for Milestone 10.');
    });
  }

  function wireEmailPdf() {
    var emailBtn = document.getElementById('btn-email-pdf');
    if (!emailBtn) return;

    emailBtn.addEventListener('click', function () {
      var noteId = window.currentNoteId;
      if (!noteId) return;

      emailBtn.disabled = true;
      emailBtn.title = 'Sending…';

      fetch('/api/notes/' + noteId + '/email-pdf', { method: 'POST' })
        .then(function (r) {
          return r.json().then(function (d) {
            return { status: r.status, data: d };
          });
        })
        .then(function (res) {
          if (res.status === 200) {
            showToast('✉️ PDF sent to ' + (res.data.to || 'your email') + '.', '#2a7a4b');
          } else if (res.status === 400) {
            showToast('⚠️ ' + (res.data.error || 'No email address set. Add one in Settings.'), '#b05010');
          } else if (res.status === 429) {
            showToast('⏳ Rate limit reached. Try again later.', '#b05010');
          } else {
            showToast('❌ ' + (res.data.error || 'Failed to send email.'), '#b05010');
          }
        })
        .catch(function () {
          showToast('❌ Network error.', '#b05010');
        })
        .finally(function () {
          emailBtn.disabled = false;
          emailBtn.title = 'Email PDF';
        });
    });
  }

  function wireBatchExport() {
    var batchBtn = document.getElementById('btn-batch-export');
    if (!batchBtn) return;

    batchBtn.addEventListener('click', function () {
      var noteId = window.currentNoteId;
      if (!noteId) return;

      var fmt = prompt('Export format: zip or pdf?', 'zip');
      if (!fmt) return;

      fmt = fmt.trim().toLowerCase();
      if (fmt !== 'zip' && fmt !== 'pdf') {
        showToast('Format must be zip or pdf.', '#b05010');
        return;
      }

      fetch('/api/batch-export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note_ids: [noteId], format: fmt })
      })
        .then(function (r) {
          if (!r.ok) {
            return r.json().then(function (d) {
              throw new Error(d.error || 'Export failed.');
            });
          }
          return r.blob();
        })
        .then(function (blob) {
          var url = URL.createObjectURL(blob);
          var a = document.createElement('a');
          a.href = url;
          a.download = 'notes_export.' + fmt;
          document.body.appendChild(a);
          a.click();
          a.remove();
          URL.revokeObjectURL(url);
          showToast('✅ Export downloaded.', '#2a7a4b');
        })
        .catch(function (err) {
          showToast('❌ ' + err.message, '#b05010');
        });
    });
  }

  // Init
  var emailEnabled = getEmailEnabled();

  if (!emailEnabled) {
    wireComingSoon('btn-email-pdf');
    wireComingSoon('btn-batch-export');
    return;
  }

  wireEmailPdf();
  wireBatchExport();
})();