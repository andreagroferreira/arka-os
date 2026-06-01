/**
 * ArkaOS Course Recorder (PoC) — popup UI.
 *
 * Provides the user gesture that authorizes tab capture, sends START_RECORDING
 * to the background service worker with the active tab id, and renders status
 * (idle -> recording mm:ss -> uploading -> done/failed). The mm:ss timer runs
 * locally in the popup; the actual recording lifecycle lives in background +
 * offscreen, so the timer is purely a display aid and resets on each session.
 *
 * Note: the popup is ephemeral (closes when it loses focus). Status is driven
 * by STATUS broadcasts from the background; when the popup reopens it queries
 * the current phase so the UI re-syncs.
 */

const TAG = '[ArkaOS][popup]';

const timerEl = document.getElementById('timer');
const lessonTitleEl = document.getElementById('lessonTitle');
const statusEl = document.getElementById('status');
const statusTextEl = document.getElementById('statusText');
const actionBtn = document.getElementById('actionBtn');

let phase = 'idle'; // idle | recording | uploading | done | failed
let elapsed = 0;
let timerHandle = null;

function fmt(total) {
  const mm = String(Math.floor(total / 60)).padStart(2, '0');
  const ss = String(total % 60).padStart(2, '0');
  return `${mm}:${ss}`;
}

function startTimer() {
  stopTimer();
  elapsed = 0;
  timerEl.textContent = fmt(elapsed);
  timerHandle = setInterval(() => {
    elapsed += 1;
    timerEl.textContent = fmt(elapsed);
  }, 1000);
}

function stopTimer() {
  if (timerHandle) {
    clearInterval(timerHandle);
    timerHandle = null;
  }
}

function setPhase(next, detail) {
  phase = next;
  statusEl.className = 'status ' + next;

  switch (next) {
    case 'idle':
      statusTextEl.textContent = detail || 'Idle — open a G4 lesson and press Start.';
      actionBtn.textContent = 'Start recording';
      actionBtn.classList.remove('stop');
      actionBtn.disabled = false;
      stopTimer();
      break;
    case 'starting':
      statusTextEl.textContent = detail || 'Preparing…';
      actionBtn.textContent = 'Starting…';
      actionBtn.disabled = true;
      break;
    case 'recording':
      // `detail` here is the status note (set by the STATUS handler below);
      // `lessonTitle` is updated separately so it isn't clobbered.
      statusTextEl.textContent = detail || 'Recording…';
      actionBtn.textContent = 'Stop & upload';
      actionBtn.classList.add('stop');
      actionBtn.disabled = false;
      if (!timerHandle) startTimer();
      break;
    case 'uploading':
      statusTextEl.textContent = 'Uploading to ArkaOS…';
      actionBtn.textContent = 'Uploading…';
      actionBtn.disabled = true;
      stopTimer();
      break;
    case 'done':
      statusTextEl.textContent = detail || 'Done — sent to ArkaOS.';
      actionBtn.textContent = 'Start recording';
      actionBtn.classList.remove('stop');
      actionBtn.disabled = false;
      stopTimer();
      break;
    case 'failed':
      statusTextEl.textContent = detail || 'Failed.';
      actionBtn.textContent = 'Start recording';
      actionBtn.classList.remove('stop');
      actionBtn.disabled = false;
      stopTimer();
      break;
  }
}

async function getActiveTab() {
  return new Promise((resolve) => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      resolve(tabs && tabs[0]);
    });
  });
}

async function onStart() {
  setPhase('starting', 'Reading lesson…');
  const tab = await getActiveTab();
  if (!tab || typeof tab.id !== 'number') {
    setPhase('failed', 'No active tab found.');
    return;
  }
  if (!/^https:\/\/plataforma\.g4business\.com\//.test(tab.url || '')) {
    setPhase('failed', 'Open a G4 lesson page in this tab first.');
    return;
  }
  chrome.runtime.sendMessage({ type: 'START_RECORDING', tabId: tab.id }, (resp) => {
    const err = chrome.runtime.lastError;
    if (err) {
      setPhase('failed', 'Could not reach the extension worker: ' + err.message);
      return;
    }
    if (!resp || !resp.ok) {
      setPhase('failed', (resp && resp.error) || 'Failed to start.');
    }
    // On success, the background drives further STATUS updates.
  });
}

function onStop() {
  // Disable the button to avoid double-sends; the authoritative next phase
  // (uploading, done, or failed/no-playback) arrives via STATUS broadcast.
  statusTextEl.textContent = 'Stopping…';
  actionBtn.disabled = true;
  chrome.runtime.sendMessage({ type: 'STOP_RECORDING' }, () => {
    void chrome.runtime.lastError; // ignore; STATUS will follow
  });
}

actionBtn.addEventListener('click', () => {
  if (phase === 'recording') onStop();
  else if (phase === 'idle' || phase === 'done' || phase === 'failed') onStart();
});

// Live status from the background service worker.
chrome.runtime.onMessage.addListener((msg) => {
  if (!msg || msg.type !== 'STATUS' || !msg.status) return;
  const s = msg.status;
  console.log(TAG, 'status:', s.phase, s.detail || '');
  if (s.phase === 'recording') {
    // Keep the lesson title in its own slot; show the play/playing note as the
    // status line. Until real playback is detected we prompt the user to press
    // Play; once currentTime advances the background flips `playing` to true.
    if (s.detail) lessonTitleEl.textContent = s.detail;
    const note = s.note || (s.playing
      ? 'Recording (playing).'
      : 'Recording — press Play on the video if it has not started.');
    setPhase('recording', note);
  }
  else if (s.phase === 'uploading') setPhase('uploading', s.detail);
  else if (s.phase === 'done') setPhase('done', s.jobId ? `Done — job ${s.jobId}` : s.detail);
  else if (s.phase === 'failed') setPhase('failed', s.detail);
  else if (s.phase === 'starting') setPhase('starting', s.detail);
});

setPhase('idle');
console.log(TAG, 'popup loaded.');
