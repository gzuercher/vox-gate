  let instanceConfig = { name: 'VoxGate', color: '#c8ff00', lang: 'de-CH', langs: ['de-CH', 'fr-CH'], maxLength: 4000 };

  const I18N = {
    'de-CH': {
      langName: 'Deutsch',
      headerToggleLang: 'Sprache umschalten',
      headerToggleAuth: 'Zugangsschlüssel ändern',
      headerToggleMute: 'Sprachausgabe stummschalten',
      authTitle: 'Zugang',
      authIntro: 'Diese Instanz ist privat. Gib den Zugangsschlüssel ein, den du vom Betreiber erhalten hast.',
      authLabel: 'Zugangsschlüssel',
      authError: 'Zugang verweigert. Schlüssel prüfen.',
      authSubmit: 'Speichern',
      authHint: 'Wird nur lokal auf diesem Gerät gespeichert.',
      emptyTitle: 'Tippen und sprechen',
      emptyHint: 'Nochmal tippen = senden',
      transcriptReady: 'Bereit...',
      micAria: 'Aufnehmen und senden',
      discardAria: 'Aufnahme verwerfen',
      micRecord: 'Aufnehmen',
      micStop: 'Stop',
      micSend: 'Senden',
      newConv: 'Neues Gespräch',
      userLabel: 'Du',
      errorPrefix: 'Fehler: ',
      speechUnsupported: 'Web Speech API wird nicht unterstützt. Bitte Chrome verwenden.',
    },
    'fr-CH': {
      langName: 'Français',
      headerToggleLang: 'Changer de langue',
      headerToggleAuth: "Modifier la clé d'accès",
      headerToggleMute: 'Couper la synthèse vocale',
      authTitle: 'Accès',
      authIntro: "Cette instance est privée. Saisissez la clé d'accès reçue de l'exploitant.",
      authLabel: "Clé d'accès",
      authError: 'Accès refusé. Vérifiez la clé.',
      authSubmit: 'Enregistrer',
      authHint: 'Stocké uniquement sur cet appareil.',
      emptyTitle: 'Touchez et parlez',
      emptyHint: 'Touchez à nouveau pour envoyer',
      transcriptReady: 'Prêt...',
      micAria: 'Enregistrer et envoyer',
      discardAria: "Annuler l'enregistrement",
      micRecord: 'Enregistrer',
      micStop: 'Arrêter',
      micSend: 'Envoyer',
      newConv: 'Nouvelle conversation',
      userLabel: 'Moi',
      errorPrefix: 'Erreur : ',
      speechUnsupported: 'Web Speech API non supportée. Utilisez Chrome.',
    },
  };

  function t(key) {
    const dict = I18N[activeLang()] || I18N['de-CH'];
    return dict[key] !== undefined ? dict[key] : key;
  }
  let recognition = null;
  // 'idle': waiting for user. 'recording': SpeechRecognition active.
  // 'review': recording stopped, transcript editable, next tap sends.
  let state = 'idle';
  let currentTranscript = '';
  let finalTranscript = '';
  function supportedLangs() {
    return (instanceConfig.langs && instanceConfig.langs.length)
      ? instanceConfig.langs
      : [instanceConfig.lang];
  }
  let currentLang = localStorage.getItem('voxLang') || null;
  let muted = localStorage.getItem('voxMuted') === '1';
  let sessionId = sessionStorage.getItem('voxSession');
  if (!sessionId) {
    sessionId = (crypto.randomUUID ? crypto.randomUUID()
      : Date.now() + '-' + Math.random().toString(36).slice(2));
    sessionStorage.setItem('voxSession', sessionId);
  }

  function activeLang() {
    return currentLang || instanceConfig.lang;
  }

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('sw.js');
  }

  const micBtn = document.getElementById('micBtn');
  const micLabel = document.getElementById('micLabel');
  const transcriptBox = document.getElementById('transcriptBox');
  const messagesEl = document.getElementById('messages');
  const statusDot = document.getElementById('statusDot');
  const logo = document.getElementById('logo');
  const langBtn = document.getElementById('langBtn');
  const muteBtn = document.getElementById('muteBtn');
  const newConvBtn = document.getElementById('newConvBtn');
  const discardBtn = document.getElementById('discardBtn');
  const authOverlay = document.getElementById('authOverlay');
  const authForm = document.getElementById('authForm');
  const tokenInput = document.getElementById('tokenInput');
  const authError = document.getElementById('authError');

  function showAuthOverlay(withError) {
    authError.hidden = !withError;
    tokenInput.value = '';
    authOverlay.hidden = false;
    setTimeout(() => tokenInput.focus(), 50);
  }

  function hideAuthOverlay() {
    authOverlay.hidden = true;
    authError.hidden = true;
  }

  authForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const value = tokenInput.value.trim();
    if (!value) return;
    localStorage.setItem('apiToken', value);
    hideAuthOverlay();
  });

  logo.addEventListener('click', () => showAuthOverlay(false));

  if (!localStorage.getItem('apiToken')) {
    showAuthOverlay(false);
  }

  function applyLang() {
    const lang = activeLang();
    document.documentElement.lang = lang.split('-')[0];
    langBtn.textContent = t('langName');
    document.querySelectorAll('[data-i18n]').forEach(el => {
      el.textContent = t(el.dataset.i18n);
    });
    document.querySelectorAll('[data-i18n-aria]').forEach(el => {
      el.setAttribute('aria-label', t(el.dataset.i18nAria));
    });
    // Re-apply state-dependent labels.
    if (state === 'idle') {
      micLabel.textContent = t('micRecord');
      transcriptBox.textContent = t('transcriptReady');
    } else if (state === 'recording') {
      micLabel.textContent = t('micStop');
    } else if (state === 'review') {
      micLabel.textContent = t('micSend');
    }
  }

  function updateMuteBtn() {
    muteBtn.textContent = muted ? '🔇' : '🔊';
    muteBtn.classList.toggle('muted', muted);
  }

  langBtn.addEventListener('click', () => {
    const langs = supportedLangs();
    const lang = activeLang();
    const idx = langs.indexOf(lang);
    const next = langs[(idx + 1) % langs.length] || langs[0];
    currentLang = next;
    localStorage.setItem('voxLang', next);
    if (state !== 'idle') discardReview();
    applyLang();
  });

  muteBtn.addEventListener('click', () => {
    muted = !muted;
    localStorage.setItem('voxMuted', muted ? '1' : '0');
    if (muted && 'speechSynthesis' in window) speechSynthesis.cancel();
    updateMuteBtn();
  });

  newConvBtn.addEventListener('click', () => {
    if (state !== 'idle') discardReview();
    sessionId = (crypto.randomUUID ? crypto.randomUUID()
      : Date.now() + '-' + Math.random().toString(36).slice(2));
    sessionStorage.setItem('voxSession', sessionId);
    messagesEl.innerHTML = '';
    if ('speechSynthesis' in window) speechSynthesis.cancel();
  });

  discardBtn.addEventListener('click', () => discardReview());

  function speak(text) {
    if (muted || !('speechSynthesis' in window) || !text) return;
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = activeLang();
    speechSynthesis.speak(u);
  }

  async function loadConfig() {
    try {
      const res = await fetch('/config');
      if (res.ok) {
        instanceConfig = await res.json();
        document.title = instanceConfig.name;
        logo.textContent = instanceConfig.name;
        document.documentElement.style.setProperty('--accent', instanceConfig.color);
        const dimColor = instanceConfig.color + '1f';
        document.documentElement.style.setProperty('--accent-dim', dimColor);
        document.querySelector('meta[name="theme-color"]').content = '#0a0a0a';
      }
    } catch (e) {
      // use defaults
    }
  }

  function setStatus(state) {
    statusDot.className = 'status-dot ' + state;
  }

  function updateTranscript(text, active) {
    transcriptBox.textContent = text || t('transcriptReady');
    transcriptBox.className = 'transcript-box' + (active ? ' active' : '');
  }

  function addMessage(role, text) {
    const empty = document.getElementById('emptyState');
    if (empty) empty.remove();

    const div = document.createElement('div');
    div.className = 'message ' + role;
    const label = role === 'user' ? t('userLabel') : instanceConfig.name;
    div.innerHTML = `
      <div class="message-label">${escapeHtml(label)}</div>
      <div class="message-bubble">${escapeHtml(text)}</div>
    `;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  function escapeHtml(t) {
    return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  micBtn.addEventListener('click', () => handleTap());

  function handleTap() {
    if (state === 'idle') {
      startRecording();
    } else if (state === 'recording') {
      enterReview();
    } else if (state === 'review') {
      sendCurrent();
    }
  }

  function setState(next) {
    state = next;
    micBtn.classList.toggle('recording', next === 'recording');
    if (next === 'idle') {
      micLabel.textContent = t('micRecord');
      transcriptBox.removeAttribute('contenteditable');
      discardBtn.hidden = true;
      updateTranscript('', false);
    } else if (next === 'recording') {
      micLabel.textContent = t('micStop');
      transcriptBox.removeAttribute('contenteditable');
      discardBtn.hidden = true;
    } else if (next === 'review') {
      micLabel.textContent = t('micSend');
      transcriptBox.setAttribute('contenteditable', 'true');
      transcriptBox.classList.remove('active');
      discardBtn.hidden = false;
    }
  }

  function startRecording() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      alert(t('speechUnsupported'));
      return;
    }

    if ('speechSynthesis' in window) speechSynthesis.cancel();

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SR();
    recognition.lang = activeLang();
    recognition.continuous = true;
    recognition.interimResults = true;

    finalTranscript = '';
    currentTranscript = '';

    recognition.onstart = () => {
      setState('recording');
      updateTranscript('', true);
      setStatus('online');
    };

    recognition.onresult = (e) => {
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) {
          finalTranscript += t + ' ';
        } else {
          interim += t;
        }
      }
      currentTranscript = (finalTranscript + interim).trim();
      updateTranscript(currentTranscript, true);
    };

    recognition.onend = () => {
      // Continuous-mode workaround: some browsers fire onend mid-session.
      // Only restart if we are still recording.
      if (state === 'recording') {
        recognition.start();
      }
    };

    recognition.onerror = (e) => {
      if (e.error === 'no-speech') return;
      console.error(e.error);
      stopRecognition();
      setState('idle');
      setStatus('error');
    };

    recognition.start();
  }

  function stopRecognition() {
    if (recognition) {
      recognition.onend = null;
      try { recognition.stop(); } catch (_) {}
    }
  }

  function enterReview() {
    stopRecognition();
    const text = currentTranscript.trim();
    if (!text) {
      setState('idle');
      return;
    }
    setState('review');
    transcriptBox.textContent = text;
    setStatus('');
    setTimeout(() => {
      transcriptBox.focus();
      const range = document.createRange();
      range.selectNodeContents(transcriptBox);
      range.collapse(false);
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
    }, 50);
  }

  function discardReview() {
    stopRecognition();
    currentTranscript = '';
    finalTranscript = '';
    setState('idle');
    setStatus('');
  }

  async function sendCurrent() {
    const text = (transcriptBox.textContent || '').trim();
    setState('idle');
    currentTranscript = '';
    finalTranscript = '';
    if (!text) return;
    await sendText(text);
  }

  async function sendText(text) {
    addMessage('user', text);

    const typingDiv = addMessage('assistant', '');
    typingDiv.classList.add('typing');
    setStatus('sending');

    try {
      const headers = { 'Content-Type': 'application/json' };
      const token = localStorage.getItem('apiToken');
      if (token) headers['Authorization'] = 'Bearer ' + token;

      const res = await fetch('/claude', {
        method: 'POST',
        headers,
        body: JSON.stringify({ text, session_id: sessionId })
      });

      if (res.status === 401) {
        localStorage.removeItem('apiToken');
        typingDiv.remove();
        setStatus('error');
        showAuthOverlay(true);
        return;
      }
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      const reply = data.response || data.text || JSON.stringify(data);

      typingDiv.classList.remove('typing');
      typingDiv.querySelector('.message-bubble').textContent = reply;
      setStatus('online');
      speak(reply);
    } catch (err) {
      typingDiv.classList.remove('typing');
      typingDiv.querySelector('.message-bubble').textContent = t('errorPrefix') + err.message;
      setStatus('error');
    }

    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  applyLang();
  updateMuteBtn();
  loadConfig().then(applyLang);
  setStatus('');
