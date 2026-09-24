const messages = document.querySelector('#messages');
const form = document.querySelector('#composer');
const fields = document.querySelector('#fields');
const send = document.querySelector('#send');
const restart = document.querySelector('#restart');
const voiceSelect = document.querySelector('#voice-select');
const autoSpeakToggle = document.querySelector('#auto-speak-toggle');
const autoplayBanner = document.querySelector('#autoplay-banner');
const enableAudioBtn = document.querySelector('#enable-audio-btn');
const voiceUnavailableBanner = document.querySelector('#voice-unavailable-banner');
const telemetryDrawer = document.querySelector('#telemetry-drawer');
const toggleTelemetryBtn = document.querySelector('#toggle-telemetry');
const closeTelemetryBtn = document.querySelector('#close-telemetry');
const telemetryContent = document.querySelector('#telemetry-content');

const urlParams = new URLSearchParams(window.location.search);
const isDebugMode = (urlParams.get('debug') === '1');

// Only display diagnostics button if ?debug=1 is present
if (toggleTelemetryBtn) {
  toggleTelemetryBtn.hidden = !isDebugMode;
}

const initialAttribution = {
  source: urlParams.get('source') || 'direct',
  platform: urlParams.get('platform') || 'web',
  content_id: urlParams.get('content_id') || '',
  campaign_id: urlParams.get('campaign_id') || '',
  cta_id: urlParams.get('cta_id') || 'CTA-ASK-BUDLY-001',
  product_or_topic: urlParams.get('product_or_topic') || 'UNKNOWN',
  published_post_id: urlParams.get('published_post_id') || ''
};

const state = {
  step: 'conversation',
  sessionId: null,
  journeyId: null,
  attribution: initialAttribution,
  customerId: null,
  goal: '',
  journey: null,
  journeyAnswers: [],
  questionIndex: 0,
  details: {},
  turnCounter: 0,
  autoSpeak: false, // Default = OFF
  selectedVoice: 'builtin-default',
  activeAudio: null,
  activeAudioTurnId: null,
  voiceEngineAvailable: true,
  audioUnlocked: false,
  telemetryLog: []
};

const esc = s => String(s ?? '').replace(/[&<>'"]/g, c => ({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  "'": '&#39;',
  '"': '&quot;'
}[c]));

async function api(path, payload) {
  send.disabled = true;
  try {
    const r = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || 'Please try again.');
    return data;
  } finally {
    send.disabled = false;
  }
}

async function loadVoiceOptions() {
  try {
    const r = await fetch('/api/vibe/voices');
    if (!r.ok) throw new Error('Voice API not ready');
    const data = await r.json();
    if (data.voices && data.voices.length > 0) {
      voiceSelect.innerHTML = data.voices.map(v => 
        `<option value="${esc(v.voice_id)}">${esc(v.display_name)} (${esc(v.status)})</option>`
      ).join('');
      state.selectedVoice = data.fallback_voice_id || data.voices[0].voice_id;
      voiceSelect.value = state.selectedVoice;
    }
    state.voiceEngineAvailable = data.voice_engine_available !== false;
    if (voiceUnavailableBanner) {
      voiceUnavailableBanner.hidden = state.voiceEngineAvailable;
    }
  } catch (e) {
    console.warn('[VIBE] Voice engine check:', e);
    state.voiceEngineAvailable = false;
    if (voiceUnavailableBanner) voiceUnavailableBanner.hidden = false;
  }
}

voiceSelect.addEventListener('change', e => {
  state.selectedVoice = e.target.value;
});

autoSpeakToggle.addEventListener('click', () => {
  state.autoSpeak = !state.autoSpeak;
  autoSpeakToggle.setAttribute('aria-pressed', String(state.autoSpeak));
  autoSpeakToggle.querySelector('.toggle-icon').textContent = state.autoSpeak ? '🔊' : '🔇';
  autoSpeakToggle.querySelector('.toggle-label').innerHTML = `Auto-Speak: <strong>${state.autoSpeak ? 'ON' : 'OFF'}</strong>`;
});

function bubble(text, who = 'bot', label = '', turnId = null, turnTimings = null, customerInput = '') {
  const el = document.createElement('div');
  el.className = `message ${who}`;
  el.innerHTML = (label ? `<div class="journey">${esc(label)}</div>` : '') + esc(text);
  
  if (who === 'bot') {
    state.turnCounter++;
    const currentTurnId = turnId || `turn_${state.turnCounter}_${Date.now()}`;
    el.dataset.turnId = currentTurnId;
    el.dataset.exactText = text; // Exact immutable payload
    
    // Render clean, minimal voice control strip
    const voiceStrip = document.createElement('div');
    voiceStrip.className = 'voice-strip';
    voiceStrip.innerHTML = `
      <button class="btn-play-voice" type="button" data-turn-id="${esc(currentTurnId)}">
        <span class="btn-icon">🔊</span>
        <span class="btn-text">Play Voice</span>
      </button>
      <span class="voice-status-pill" data-status-turn="${esc(currentTurnId)}">Ready</span>
      <span class="voice-tag">[${esc(state.selectedVoice)}]</span>
    `;
    el.appendChild(voiceStrip);

    const playBtn = voiceStrip.querySelector('.btn-play-voice');
    playBtn.addEventListener('click', () => handlePlayVoice(currentTurnId, text, playBtn, voiceStrip, turnTimings, customerInput));

    // Handle Auto-Speak if enabled
    if (state.autoSpeak) {
      setTimeout(() => {
        handlePlayVoice(currentTurnId, text, playBtn, voiceStrip, turnTimings, customerInput);
      }, 100);
    }
  }

  messages.append(el);
  messages.scrollTop = messages.scrollHeight;
  return el;
}

class StreamingVoicePlayer {
  constructor() {
    this.currentTurnId = null;
    this.audioElements = [];
    this.currentIndex = 0;
    this.isPlaying = false;
    this.isPaused = false;
    this.onEnded = null;
  }

  stop() {
    this.audioElements.forEach(a => {
      a.pause();
      a.currentTime = 0;
    });
    this.audioElements = [];
    this.currentIndex = 0;
    this.isPlaying = false;
    this.isPaused = false;
    this.currentTurnId = null;
  }

  pause() {
    if (this.audioElements[this.currentIndex]) {
      this.audioElements[this.currentIndex].pause();
      this.isPaused = true;
    }
  }

  resume() {
    if (this.audioElements[this.currentIndex]) {
      this.audioElements[this.currentIndex].play();
      this.isPaused = false;
    }
  }
}

const voicePlayer = new StreamingVoicePlayer();

async function handlePlayVoice(turnId, exactText, playBtn, voiceStrip, turnTimings = null, customerInput = '') {
  const statusPill = voiceStrip.querySelector(`[data-status-turn="${turnId}"]`);
  const voiceTag = voiceStrip.querySelector('.voice-tag');
  
  // If this turn is already active, toggle Pause / Resume
  if (voicePlayer.currentTurnId === turnId && voicePlayer.isPlaying) {
    if (!voicePlayer.isPaused) {
      voicePlayer.pause();
      playBtn.classList.remove('playing');
      playBtn.querySelector('.btn-icon').textContent = '▶';
      playBtn.querySelector('.btn-text').textContent = 'Resume';
      statusPill.className = 'voice-status-pill';
      statusPill.textContent = 'Paused';
      return;
    } else {
      voicePlayer.resume();
      playBtn.classList.add('playing');
      playBtn.querySelector('.btn-icon').textContent = '⏸';
      playBtn.querySelector('.btn-text').textContent = 'Pause';
      statusPill.className = 'voice-status-pill playing';
      statusPill.textContent = 'Playing…';
      return;
    }
  }

  // Stop any other active playback
  voicePlayer.stop();
  const oldBtn = document.querySelector(`.btn-play-voice.playing`);
  if (oldBtn) {
    oldBtn.classList.remove('playing');
    oldBtn.querySelector('.btn-icon').textContent = '🔁';
    oldBtn.querySelector('.btn-text').textContent = 'Replay';
  }

  const chosenVoice = state.selectedVoice;
  voiceTag.textContent = `[${chosenVoice}]`;

  // UI State: Generating voice...
  playBtn.disabled = true;
  playBtn.querySelector('.btn-icon').textContent = '⏳';
  playBtn.querySelector('.btn-text').textContent = 'Generating…';
  statusPill.className = 'voice-status-pill generating';
  statusPill.textContent = 'Generating voice…';

  const t4 = performance.now(); // Synthesis request start

  try {
    // 1. Split text into sentence chunks
    const splitRes = await fetch('/api/vibe/synthesize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: exactText,
        split_sentences: true
      })
    });
    const splitData = await splitRes.json();
    const sentences = (splitData.sentences && splitData.sentences.length > 0) ? splitData.sentences : [exactText];

    // 2. Synthesize Chunk 1 first for immediate Time-to-First-Audio
    const chunk1Res = await fetch('/api/vibe/synthesize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: state.sessionId || 'anon',
        turn_id: turnId,
        text: sentences[0],
        voice_id: chosenVoice,
        chunk_index: 1
      })
    });
    const chunk1Data = await chunk1Res.json();
    const t5 = performance.now(); // Chunk 1 synthesis complete

    if (!chunk1Res.ok || !chunk1Data.available) {
      throw new Error(chunk1Data.details || chunk1Data.error || 'Voice temporarily unavailable');
    }

    voicePlayer.currentTurnId = turnId;
    voicePlayer.isPlaying = true;
    voicePlayer.isPaused = false;
    voicePlayer.currentIndex = 0;
    voicePlayer.audioElements = [];

    const audio1 = new Audio(chunk1Data.audio_url);
    voicePlayer.audioElements.push(audio1);

    // Audio delivery (T6) and playback (T7)
    audio1.addEventListener('canplaythrough', () => {
      const t6 = performance.now();
      playBtn.disabled = false;
      playBtn.classList.add('playing');
      playBtn.querySelector('.btn-icon').textContent = '⏸';
      playBtn.querySelector('.btn-text').textContent = 'Pause';
      statusPill.className = 'voice-status-pill playing';
      statusPill.textContent = 'Playing…';

      const playPromise = audio1.play();
      if (playPromise !== undefined) {
        playPromise.then(() => {
          const t7 = performance.now();
          recordTelemetry({
            turn_id: turnId,
            voice_id: chosenVoice,
            customer_input: customerInput,
            exact_text: exactText,
            exact_text_match: true,
            voice_status: 'PLAYING',
            turnTimings,
            t4, t5, t6, t7,
            audio_url: chunk1Data.audio_url,
            success: true
          });
        }).catch(err => {
          console.warn('[VIBE] Autoplay policy prevented playback:', err);
          if (autoplayBanner) autoplayBanner.hidden = false;
          playBtn.classList.remove('playing');
          playBtn.querySelector('.btn-icon').textContent = '▶';
          playBtn.querySelector('.btn-text').textContent = 'Play Voice';
          statusPill.className = 'voice-status-pill';
          statusPill.textContent = 'Ready';
        });
      }
    }, { once: true });

    // When audio finishes, advance to next chunk
    function attachEndedListener(audioEl, idx) {
      audioEl.addEventListener('ended', () => {
        const nextIdx = idx + 1;
        if (nextIdx < voicePlayer.audioElements.length && voicePlayer.audioElements[nextIdx]) {
          voicePlayer.currentIndex = nextIdx;
          voicePlayer.audioElements[nextIdx].play().catch(e => console.warn('Next chunk play notice:', e));
        } else if (nextIdx >= sentences.length) {
          // All sentence chunks completed
          playBtn.classList.remove('playing');
          playBtn.querySelector('.btn-icon').textContent = '🔁';
          playBtn.querySelector('.btn-text').textContent = 'Replay';
          statusPill.className = 'voice-status-pill';
          statusPill.textContent = 'Ready';
          voicePlayer.stop();
        }
      });
    }

    attachEndedListener(audio1, 0);

    // 3. Concurrently synthesize remaining sentence chunks in background
    if (sentences.length > 1) {
      (async () => {
        for (let i = 1; i < sentences.length; i++) {
          if (voicePlayer.currentTurnId !== turnId) break; // If user stopped or started new turn
          try {
            const nextRes = await fetch('/api/vibe/synthesize', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                session_id: state.sessionId || 'anon',
                turn_id: turnId,
                text: sentences[i],
                voice_id: chosenVoice,
                chunk_index: i + 1
              })
            });
            const nextData = await nextRes.json();
            if (nextRes.ok && nextData.audio_url) {
              const nextAudio = new Audio(nextData.audio_url);
              voicePlayer.audioElements.push(nextAudio);
              attachEndedListener(nextAudio, i);
            }
          } catch (bgErr) {
            console.warn(`[VIBE] Background synth notice for chunk ${i + 1}:`, bgErr);
          }
        }
      })();
    }

  } catch (err) {
    console.error('[VIBE Synthesis Error]', err);
    playBtn.disabled = false;
    playBtn.classList.remove('playing');
    playBtn.querySelector('.btn-icon').textContent = '⚠️';
    playBtn.querySelector('.btn-text').textContent = 'Unavailable';
    statusPill.className = 'voice-status-pill error';
    statusPill.textContent = 'Voice unavailable';

    recordTelemetry({
      turn_id: turnId,
      voice_id: chosenVoice,
      customer_input: customerInput,
      exact_text: exactText,
      exact_text_match: false,
      voice_status: 'UNAVAILABLE',
      error_code: err.message,
      turnTimings,
      t4, t5: performance.now(), t6: performance.now(), t7: performance.now(),
      success: false
    });
  }
}

function recordTelemetry(item) {
  const timings = item.turnTimings || {};
  const t0 = timings.t0 || item.t4;
  const t1 = timings.t1 || t0;
  const t2 = timings.t2 || t1;
  const t3 = timings.t3 || t2;
  const t4 = item.t4;
  const t5 = item.t5;
  const t6 = item.t6;
  const t7 = item.t7;

  const record = {
    timestamp: new Date().toISOString(),
    session_id: state.sessionId || 'anon',
    turn_id: item.turn_id,
    customer_input: item.customer_input || '',
    budly_response_latency_ms: Math.round(t2 - t1),
    text_render_latency_ms: Math.round(t3 - t2),
    voice_generation_latency_ms: Math.round(t5 - t4),
    time_to_first_audio_ms: Math.round(t7 - t0),
    selected_voice_id: item.voice_id,
    exact_text_match: Boolean(item.exact_text_match),
    voice_status: item.voice_status || 'READY',
    error_code: item.error_code || null,
    success: Boolean(item.success)
  };

  state.telemetryLog.push(record);
  if (isDebugMode) {
    renderTelemetry();
  }

  // Silently post to background live jsonl file
  fetch('/api/vibe/telemetry', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(record)
  }).catch(() => {});
}

function renderTelemetry() {
  if (!telemetryContent) return;
  if (state.telemetryLog.length === 0) {
    telemetryContent.innerHTML = '<p class="telemetry-empty">No conversation turns recorded yet.</p>';
    return;
  }

  telemetryContent.innerHTML = state.telemetryLog.map((t, idx) => `
    <div class="telemetry-card">
      <h4>Turn ${idx + 1} (${esc(t.selected_voice_id)})</h4>
      <div class="telemetry-metric"><span>Budly Latency:</span> <strong>${(t.budly_response_latency_ms / 1000).toFixed(2)}s</strong></div>
      <div class="telemetry-metric"><span>Voice Gen:</span> <strong>${(t.voice_generation_latency_ms / 1000).toFixed(2)}s</strong></div>
      <div class="telemetry-metric"><span>Time to First Audio:</span> <strong>${(t.time_to_first_audio_ms / 1000).toFixed(2)}s</strong></div>
      <div class="telemetry-fidelity ${t.exact_text_match ? 'pass' : 'fail'}">
        Exact Match: ${t.exact_text_match ? '✓ TRUE' : '✗ FAILED'}
      </div>
    </div>
  `).join('');
}

if (toggleTelemetryBtn) {
  toggleTelemetryBtn.addEventListener('click', () => {
    if (telemetryDrawer) telemetryDrawer.hidden = !telemetryDrawer.hidden;
  });
}

if (closeTelemetryBtn) {
  closeTelemetryBtn.addEventListener('click', () => {
    if (telemetryDrawer) telemetryDrawer.hidden = true;
  });
}

if (enableAudioBtn) {
  enableAudioBtn.addEventListener('click', () => {
    if (autoplayBanner) autoplayBanner.hidden = true;
    state.audioUnlocked = true;
    const dummyAudio = new Audio();
    dummyAudio.play().catch(() => {});
  });
}

function inputs(html, button = 'Continue') {
  fields.innerHTML = html;
  send.textContent = button;
  setTimeout(() => fields.querySelector('input,select')?.focus(), 50);
}

function showProductCard(data) {
  if (!data.recommended_destination) return;
  const el = document.createElement('div');
  el.className = 'product-card';
  el.innerHTML = `
    <div class="journey">Recommended Next Step</div>
    <h3>${esc(data.bot_message ? 'Recommended Link' : 'Explore Product')}</h3>
    <p><a href="${esc(data.recommended_destination)}" target="_blank" rel="noopener">Explore Details ↗</a></p>
  `;
  messages.append(el);
  messages.scrollTop = messages.scrollHeight;
}

async function begin() {
  messages.innerHTML = '';
  Object.assign(state, {
    step: 'conversation',
    customerId: null,
    goal: '',
    journey: null,
    journeyAnswers: [],
    questionIndex: 0,
    details: {},
    turnCounter: 0
  });
  if (restart) restart.hidden = true;
  
  await loadVoiceOptions();

  try {
    const intakeRes = await api('/api/intake', {
      landing_input: initialAttribution,
      landing_route: window.location.href
    });
    state.sessionId = intakeRes.session_id;
    state.journeyId = intakeRes.journey_id;
  } catch (e) {}

  bubble("Hi, I’m Budly! I can help you compare current Wake'n'Bake Lounge products and answer questions without pressure. What are you looking for today?");
  inputs('<input name="message" id="chat-input" placeholder="Ask Budly anything..." autocomplete="off" required>', 'Send');
}

form.addEventListener('submit', async e => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(form));
  const t0 = performance.now(); // T0 = Customer presses Send
  
  try {
    if (state.step === 'conversation') {
      const msg = data.message || data.answer;
      bubble(msg, 'user');
      
      const t1 = performance.now(); // T1 = Request begins
      const out = await api('/api/turn', { session_id: state.sessionId, message: msg });
      const t2 = performance.now(); // T2 = Text response received
      
      const turnId = `turn_${state.turnCounter + 1}_${Date.now()}`;
      const turnTimings = { t0, t1, t2, t3: 0 };
      
      // T3 = Visibly rendered in browser
      bubble(out.bot_message, 'bot', '', turnId, turnTimings, msg);
      turnTimings.t3 = performance.now();

      if (out.recommended_destination && out.resulting_action === 'legacy_guided_flow') {
        showProductCard(out);
      }
      if (restart) restart.hidden = false;
      inputs('<input name="message" id="chat-input" placeholder="Ask another question..." autocomplete="off" required>', 'Send');
    }
  } catch (err) {
    bubble("I’m sorry, I ran into an issue processing that. Please ask again or refresh.", 'bot');
  }
});

if (restart) {
  restart.addEventListener('click', () => begin());
}

begin();
