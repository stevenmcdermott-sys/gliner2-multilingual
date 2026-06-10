/* =============================================
   Ikigai — app.js
   Vanilla JS state machine
   ============================================= */

'use strict';

// ---- State ----
const state = {
  lang: 'en',
  answers: Array(8).fill(''),
  currentQ: 0,
  result: null
};

// Domain mapping: question index to domain key
const DOMAIN_MAP = [
  'love',        // Q0
  'love',        // Q1
  'good_at',     // Q2
  'good_at',     // Q3
  'world_needs', // Q4
  'world_needs', // Q5
  'paid_for',    // Q6
  'paid_for'     // Q7
];

// ---- Screen Management ----
function showScreen(id) {
  document.querySelectorAll('.screen').forEach(function(s) {
    s.classList.remove('active', 'fade-in');
  });
  var el = document.getElementById('screen-' + id);
  if (!el) return;
  el.classList.add('active');
  // Trigger reflow so fadeIn restarts each time
  void el.offsetWidth;
  el.classList.add('fade-in');
}

// ---- Language Selection ----
function selectLang(code) {
  state.lang = code;
  applyI18n();
  showScreen('intro');
}

// ---- Apply i18n ----
function applyI18n() {
  var t = window.I18N[state.lang];
  if (!t) return;

  // HTML lang + dir
  document.documentElement.lang = t.lang;
  document.documentElement.dir  = t.dir || 'ltr';

  // Intro screen
  var introTitle   = document.getElementById('intro-title');
  var introTagline = document.getElementById('intro-tagline');
  var btnBegin     = document.getElementById('btn-begin');
  if (introTitle)   introTitle.textContent   = t.title;
  if (introTagline) introTagline.textContent = t.tagline;
  if (btnBegin)     btnBegin.textContent     = t.begin;

  // Nav buttons (only update if not on last question showing submit label)
  var btnBack = document.getElementById('btn-back');
  var btnNext = document.getElementById('btn-next');
  if (btnBack) btnBack.textContent = t.back;
  if (btnNext && state.currentQ < 7) btnNext.textContent = t.next;

  // Loading text
  var loadingText = document.getElementById('loading-text');
  if (loadingText) loadingText.textContent = t.loading;

  // Restart button
  var btnRestart = document.getElementById('btn-restart');
  if (btnRestart) btnRestart.textContent = t.restart;

  // Lang picker label
  var selectLangLabel = document.getElementById('select-lang-label');
  if (selectLangLabel) selectLangLabel.textContent = t.selectLang;

  // Venn labels
  var d = t.domains;
  var vlLove  = document.getElementById('vl-love');
  var vlGood  = document.getElementById('vl-good');
  var vlWorld = document.getElementById('vl-world');
  var vlPaid  = document.getElementById('vl-paid');
  if (vlLove)  vlLove.textContent  = d.love;
  if (vlGood)  vlGood.textContent  = d.good_at;
  if (vlWorld) vlWorld.textContent = d.world_needs;
  if (vlPaid)  vlPaid.textContent  = d.paid_for;
}

// ---- Show Question ----
function showQuestion(n) {
  state.currentQ = n;
  var t = window.I18N[state.lang];

  // Progress bar: advances as questions are answered
  var fill = document.getElementById('progress-fill');
  if (fill) fill.style.width = ((n / 8) * 100) + '%';

  // Domain label
  var domainKey   = DOMAIN_MAP[n];
  var domainLabel = document.getElementById('domain-label');
  if (domainLabel) domainLabel.textContent = t.domains[domainKey] || '';

  // Question counter
  var qCounter = document.getElementById('q-counter');
  if (qCounter) qCounter.textContent = (n + 1) + ' / 8';

  // Question text
  var qText = document.getElementById('question-text');
  if (qText) qText.textContent = t.questions[n] || '';

  // Pre-fill textarea if answer exists
  var textarea = document.getElementById('answer-input');
  if (textarea) {
    textarea.value = state.answers[n] || '';
    autoResizeTextarea(textarea);
    setTimeout(function() { textarea.focus(); }, 50);
  }

  // Back button: hide on Q0
  var btnBack = document.getElementById('btn-back');
  if (btnBack) {
    btnBack.style.visibility = (n === 0) ? 'hidden' : 'visible';
  }

  // Next button: show a forward arrow on last question
  var btnNext = document.getElementById('btn-next');
  if (btnNext) {
    if (n === 7) {
      // Use locale submit label if present, else a unicode right arrow
      btnNext.textContent = t.submit || '→';
    } else {
      btnNext.textContent = t.next;
    }
  }
}

// ---- Navigation ----
function goNext() {
  var textarea = document.getElementById('answer-input');
  if (textarea) {
    state.answers[state.currentQ] = textarea.value.trim();
  }
  if (state.currentQ < 7) {
    showQuestion(state.currentQ + 1);
  } else {
    submit();
  }
}

function goBack() {
  // Save current answer before going back
  var textarea = document.getElementById('answer-input');
  if (textarea) {
    state.answers[state.currentQ] = textarea.value.trim();
  }
  if (state.currentQ > 0) {
    showQuestion(state.currentQ - 1);
  } else {
    showScreen('intro');
  }
}

// ---- Start Questions ----
function startQuestions() {
  state.answers  = Array(8).fill('');
  state.currentQ = 0;
  state.result   = null;
  showScreen('question');
  showQuestion(0);
}

// ---- Restart ----
function restart() {
  state.lang     = 'en';
  state.answers  = Array(8).fill('');
  state.currentQ = 0;
  state.result   = null;
  showScreen('lang');
}

// ---- Submit Answers to API ----
async function submit() {
  showScreen('loading');
  try {
    var base = window.IKIGAI_API_BASE || '';
    var resp = await fetch(base + '/api/ikigai', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answers: state.answers, lang: state.lang })
    });
    if (!resp.ok) throw new Error('API error ' + resp.status);
    state.result = await resp.json();
  } catch (_) {
    // Fall back to local prose generation
    state.result = buildLocalFallback(state.answers, state.lang);
  }
  showResult();
}

// ---- Local Fallback ----
function buildLocalFallback(answers, lang) {
  var t  = window.I18N[lang];
  var fb = t.fallback;
  var d  = t.domains;

  function fill(template) {
    return template.replace(/\{(\d+)\}/g, function(_, i) {
      return answers[parseInt(i, 10)] || '…';
    });
  }

  return {
    eyebrow:      fb.eyebrow,
    centre_intro: fb.centre_intro,
    centre:       fill(fb.centre),
    sections: [
      { domain: 'love',        title: d.love,        body: fill(fb.sections[0]) },
      { domain: 'good_at',     title: d.good_at,     body: fill(fb.sections[1]) },
      { domain: 'world_needs', title: d.world_needs, body: fill(fb.sections[2]) },
      { domain: 'paid_for',    title: d.paid_for,    body: fill(fb.sections[3]) }
    ],
    closing: fb.closing
  };
}

// ---- Render Result ----
function showResult() {
  var r = state.result;
  if (!r) return;

  // Eyebrow
  var eyebrow = document.getElementById('result-eyebrow');
  if (eyebrow) eyebrow.textContent = r.eyebrow || '';

  // Centre intro
  var centreIntro = document.getElementById('result-centre-intro');
  if (centreIntro) centreIntro.textContent = r.centre_intro || '';

  // Centre paragraph
  var centre = document.getElementById('result-centre');
  if (centre) centre.textContent = r.centre || '';

  // Section cards
  var sectionsEl = document.getElementById('result-sections');
  if (sectionsEl && Array.isArray(r.sections)) {
    sectionsEl.innerHTML = r.sections.map(function(s) {
      return '<div class="section-card fade-in" data-domain="' + escapeAttr(s.domain) + '">'
        + '<p class="section-card-title">' + escapeHtml(s.title) + '</p>'
        + '<p class="section-card-body">'  + escapeHtml(s.body)  + '</p>'
        + '</div>';
    }).join('');
  }

  // Closing
  var closing = document.getElementById('result-closing');
  if (closing) closing.textContent = r.closing || '';

  // Update venn labels with current locale
  applyI18n();

  showScreen('result');

  // Scroll to top of result
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ---- Utility: HTML escaping ----
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escapeAttr(str) {
  return String(str).replace(/"/g, '&quot;');
}

// ---- Textarea Auto-resize ----
function autoResizeTextarea(el) {
  el.style.height = 'auto';
  el.style.height = el.scrollHeight + 'px';
}

// ---- Init ----
document.addEventListener('DOMContentLoaded', function() {
  // Show language screen first
  showScreen('lang');

  // Textarea auto-resize on input
  var textarea = document.getElementById('answer-input');
  if (textarea) {
    textarea.addEventListener('input', function() {
      autoResizeTextarea(this);
    });
  }

  // Keyboard: Enter (without Shift) on textarea advances to next question
  document.addEventListener('keydown', function(e) {
    var activeScreen = document.querySelector('.screen.active');
    if (!activeScreen || activeScreen.id !== 'screen-question') return;

    if (e.key === 'Enter' && !e.shiftKey) {
      var focused = document.activeElement;
      if (focused && focused.id === 'answer-input') {
        e.preventDefault();
        goNext();
      }
    }
  });
});

// ---- Expose globals for inline onclick handlers ----
window.selectLang     = selectLang;
window.startQuestions = startQuestions;
window.goNext         = goNext;
window.goBack         = goBack;
window.restart        = restart;
