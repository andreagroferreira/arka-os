/**
 * ArkaOS Course Recorder (PoC) — background service worker (MV3).
 *
 * Orchestrates one-lesson capture. The service worker CANNOT run
 * MediaRecorder or getUserMedia, so all media work lives in an offscreen
 * document. The worker's job is coordination:
 *
 *   popup --(START_RECORDING)--> background
 *      background --(GET_LESSON_INFO/PLAY_LESSON)--> content.js (Vimeo control)
 *      background --(chrome.tabCapture.getMediaStreamId)--> streamId
 *      background --(ensure offscreen doc + START_CAPTURE{streamId})--> offscreen.js
 *      content.js --(LESSON_ENDED)--> background --(STOP_CAPTURE)--> offscreen.js
 *      offscreen.js --(UPLOAD_RESULT)--> background --(status)--> popup
 *
 * Structured so a full-course loop can be added later: `recordLesson()`
 * resolves when one lesson is uploaded, so a caller could `await` it per
 * lesson in sequence. The PoC invokes it exactly once from the popup.
 */

const TAG = '[ArkaOS][bg]';
const OFFSCREEN_PATH = 'offscreen.html';
const DASHBOARD_UPLOAD_URL = 'http://localhost:3334/api/knowledge/upload-file';

/** Single in-flight session. PoC records one lesson at a time. */
let session = null; // { tabId, title, duration, safetyTimer, playbackDetected, capturing, resolve, reject }

/** Broadcast a status object to any listening popup. Popups may be closed; ignore errors. */
function emitStatus(status) {
  console.log(TAG, 'status:', status.phase, status.detail || '');
  try {
    chrome.runtime.sendMessage({ type: 'STATUS', status });
  } catch (e) {
    /* no popup open — fine */
  }
}

/** Promise wrapper for chrome.tabs.sendMessage. */
function sendToTab(tabId, message) {
  return new Promise((resolve, reject) => {
    try {
      chrome.tabs.sendMessage(tabId, message, (resp) => {
        const err = chrome.runtime.lastError;
        if (err) return reject(new Error(err.message));
        resolve(resp);
      });
    } catch (e) {
      reject(e);
    }
  });
}

/** Promise wrapper for chrome.tabCapture.getMediaStreamId. */
function getTabStreamId(tabId) {
  return new Promise((resolve, reject) => {
    if (!chrome.tabCapture || !chrome.tabCapture.getMediaStreamId) {
      return reject(new Error('chrome.tabCapture.getMediaStreamId is unavailable.'));
    }
    chrome.tabCapture.getMediaStreamId({ targetTabId: tabId }, (streamId) => {
      const err = chrome.runtime.lastError;
      if (err) return reject(new Error(err.message));
      if (!streamId) return reject(new Error('Empty streamId from tabCapture.'));
      resolve(streamId);
    });
  });
}

/** Create the offscreen document if it does not already exist. */
async function ensureOffscreen() {
  if (!chrome.offscreen) {
    throw new Error('chrome.offscreen API is unavailable (Chrome 109+ required).');
  }
  const has = await chrome.offscreen.hasDocument?.();
  if (has) return;
  await chrome.offscreen.createDocument({
    url: OFFSCREEN_PATH,
    reasons: ['USER_MEDIA'],
    justification: 'Record tab audio of a course lesson for transcription.'
  });
  console.log(TAG, 'offscreen document created.');
}

/** Tear down the offscreen document if present. */
async function closeOffscreen() {
  try {
    if (chrome.offscreen && (await chrome.offscreen.hasDocument?.())) {
      await chrome.offscreen.closeDocument();
      console.log(TAG, 'offscreen document closed.');
    }
  } catch (e) {
    console.warn(TAG, 'closeOffscreen failed:', e);
  }
}

/** Promise wrapper for messaging the offscreen doc (runtime-scoped). */
function sendToOffscreen(message) {
  return new Promise((resolve, reject) => {
    try {
      chrome.runtime.sendMessage(message, (resp) => {
        const err = chrome.runtime.lastError;
        if (err) return reject(new Error(err.message));
        resolve(resp);
      });
    } catch (e) {
      reject(e);
    }
  });
}

/** Stop everything: capture, timers, offscreen doc. Safe to call multiple times. */
async function cleanup() {
  if (session?.safetyTimer) {
    clearTimeout(session.safetyTimer);
    session.safetyTimer = null;
  }
  await closeOffscreen();
}

/**
 * Arm the fallback safety timer from the moment capture starts. If the natural
 * Vimeo 'ended' never fires (or playback never begins), this guarantees the
 * session terminates. Deadline = duration + 15s buffer; when duration is
 * unknown we still arm a generous fixed ceiling so the flow can't hang forever.
 *
 * On expiry:
 *   - if real playback WAS detected -> stop + upload what we captured;
 *   - if NO playback was ever detected -> abort with a clear message instead
 *     of uploading silence.
 */
function armSafetyTimer() {
  if (!session) return;
  if (session.safetyTimer) clearTimeout(session.safetyTimer);
  const FALLBACK_NO_DURATION_S = 30 * 60; // 30 min ceiling when duration unknown
  const deadlineS = session.duration > 0 ? session.duration + 15 : FALLBACK_NO_DURATION_S;
  session.safetyTimer = setTimeout(() => {
    if (!session) return;
    if (!session.playbackDetected) {
      console.warn(TAG, 'safety deadline reached with NO playback detected; aborting (no silent upload).');
      abortNoPlayback();
    } else {
      console.warn(TAG, 'safety deadline reached; stopping capture (fallback for missing "ended").');
      stopCapture('safety-timeout');
    }
  }, deadlineS * 1000);
  console.log(TAG, 'safety timer armed for', deadlineS, 's.');
}

/**
 * Record ONE lesson end-to-end. Resolves with the upload result, rejects on
 * any failure. Designed to be awaitable per-lesson for a future course loop.
 */
async function recordLesson(tabId) {
  if (session) throw new Error('A recording is already in progress.');

  emitStatus({ phase: 'starting', detail: 'Reading lesson info' });

  // 1) Read title + duration from the Vimeo player (via content script).
  let info;
  try {
    const resp = await sendToTab(tabId, { type: 'GET_LESSON_INFO' });
    if (!resp || !resp.ok) throw new Error(resp?.error || 'Could not read the Vimeo player.');
    info = resp.info;
  } catch (e) {
    throw new Error(
      'No Vimeo player found on this tab. Open a G4 lesson page and try again. (' + e.message + ')'
    );
  }
  const title = (info && info.title) || 'lesson';
  const duration = Number(info && info.duration) || 0;
  console.log(TAG, 'lesson:', title, 'duration:', duration, 's');

  session = { tabId, title, duration, safetyTimer: null, playbackDetected: false, capturing: false };

  // 2) Get a tab-capture stream id (must be on the active tab; user gesture
  //    originated in the popup which called START_RECORDING).
  emitStatus({ phase: 'starting', detail: 'Acquiring tab audio' });
  let streamId;
  try {
    streamId = await getTabStreamId(tabId);
  } catch (e) {
    session = null;
    throw new Error('Tab capture failed: ' + e.message);
  }

  // 3) Spin up the offscreen doc and hand it the streamId + upload params.
  try {
    await ensureOffscreen();
    const startResp = await sendToOffscreen({
      target: 'offscreen',
      type: 'START_CAPTURE',
      streamId,
      title,
      uploadUrl: DASHBOARD_UPLOAD_URL
    });
    if (!startResp || !startResp.ok) {
      throw new Error(startResp?.error || 'Offscreen failed to start capture.');
    }
  } catch (e) {
    session = null;
    await cleanup();
    throw new Error('Could not start audio capture: ' + e.message);
  }

  // Capture is live from this instant. ARM THE SAFETY TIMER NOW — before play()
  // — so a never-playing lesson still terminates deterministically. (Previously
  // the timer was armed only after play succeeded, so a blocked play() could
  // leave the session hanging forever.)
  session.capturing = true;
  armSafetyTimer();

  // The play() promise is NOT authoritative (autoplay policy can block it) and
  // must NOT gate "recording". Until the timeupdate-driven PLAYBACK_STARTED
  // arrives, ask the user to press Play manually.
  emitStatus({
    phase: 'recording',
    detail: title,
    duration,
    playing: false,
    note: 'Recording — press Play on the video if it has not started.'
  });

  // 4) Best-effort programmatic play. Fire-and-forget: PLAY_LESSON never
  //    rejects (the bridge races play() against a 2.5s timeout and always
  //    reports ok), but we still don't await it as a precondition for anything.
  sendToTab(tabId, { type: 'PLAY_LESSON' })
    .then((playResp) => {
      console.log(TAG, 'play() outcome:', playResp && playResp.info && playResp.info.play, '(non-authoritative)');
    })
    .catch((e) => {
      console.warn(TAG, 'PLAY_LESSON send failed (non-fatal):', e.message);
    });

  // 5) Wait for the upload to complete (driven by LESSON_ENDED or the safety
  //    timer -> STOP_CAPTURE -> offscreen MediaRecorder.onstop -> UPLOAD_RESULT;
  //    or an abort if no playback was ever detected).
  return new Promise((resolve, reject) => {
    session.resolve = resolve;
    session.reject = reject;
  });
}

/** Ask the offscreen doc to stop recording (which triggers blob build + upload). */
async function stopCapture(reason) {
  if (!session) return;
  // Don't upload silence: if no real playback was ever detected, discard.
  if (!session.playbackDetected) {
    console.warn(TAG, 'stop requested (', reason, ') but no playback detected; discarding.');
    await abortNoPlayback();
    return;
  }
  console.log(TAG, 'stopping capture, reason:', reason);
  emitStatus({ phase: 'uploading', detail: session.title });
  try {
    await sendToOffscreen({ target: 'offscreen', type: 'STOP_CAPTURE' });
  } catch (e) {
    console.warn(TAG, 'STOP_CAPTURE send failed:', e.message);
    failSession('Failed to signal stop: ' + e.message);
  }
}

/**
 * Abort the session because no real playback was ever detected. We discard the
 * (silent) capture rather than uploading it: tell the offscreen doc to drop,
 * tear everything down, and surface a clear status. Resolves the session
 * promise (it's a clean, expected outcome, not an error) with discarded:true.
 */
async function abortNoPlayback() {
  const s = session;
  try {
    await sendToOffscreen({ target: 'offscreen', type: 'DISCARD_CAPTURE' });
  } catch (e) {
    console.warn(TAG, 'DISCARD_CAPTURE send failed:', e.message);
  }
  await cleanup();
  session = null;
  emitStatus({ phase: 'failed', detail: 'No playback detected — nothing recorded. Press Play and try again.' });
  if (s?.resolve) s.resolve({ discarded: true, reason: 'no-playback' });
}

/** Finish the session successfully and clean up. */
async function finishSession(result) {
  const s = session;
  await cleanup();
  session = null;
  emitStatus({ phase: 'done', detail: result?.detail || 'Uploaded to ArkaOS', jobId: result?.jobId });
  if (s?.resolve) s.resolve(result);
}

/** Fail the session and clean up. */
async function failSession(message) {
  const s = session;
  await cleanup();
  session = null;
  emitStatus({ phase: 'failed', detail: message });
  if (s?.reject) s.reject(new Error(message));
}

// --- Message router ---------------------------------------------------------

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (!msg || !msg.type) return;

  // SECURITY: only ever act on messages originating from our own extension.
  // External pages/extensions cannot satisfy sender.id === chrome.runtime.id.
  if (!sender || sender.id !== chrome.runtime.id) {
    console.warn(TAG, 'rejected message from foreign sender:', sender && sender.id);
    return;
  }

  // From popup: begin a one-lesson recording on the given (active) tab.
  if (msg.type === 'START_RECORDING') {
    // Privileged: must come from the popup/extension page (no sender.tab).
    // A content script (which always carries sender.tab) must NOT start/stop.
    if (sender.tab) {
      console.warn(TAG, 'ignoring START_RECORDING from a tab/content script.');
      return;
    }
    const tabId = msg.tabId;
    if (typeof tabId !== 'number') {
      sendResponse({ ok: false, error: 'No active tab id provided.' });
      return;
    }
    recordLesson(tabId)
      .then(() => { /* status already emitted via finishSession */ })
      .catch((err) => failSession(err.message));
    sendResponse({ ok: true, accepted: true });
    return; // synchronous ack; progress flows via STATUS broadcasts
  }

  // From popup: manual stop. Privileged — reject tab/content-script senders.
  if (msg.type === 'STOP_RECORDING') {
    if (sender.tab) {
      console.warn(TAG, 'ignoring STOP_RECORDING from a tab/content script.');
      return;
    }
    stopCapture('manual');
    sendResponse({ ok: true });
    return;
  }

  // From content script: AUTHORITATIVE playback signal (currentTime advanced
  // past ~0.5s). This — not the play() promise — confirms the recording has
  // real content, and flips the popup to "Recording (playing)".
  if (msg.type === 'PLAYBACK_STARTED') {
    // Authoritative signal: accept ONLY from the tab we are actively
    // recording. No session or a mismatched tab id => forged/stale; ignore.
    if (!session || !sender.tab || sender.tab.id !== session.tabId) {
      console.warn(TAG, 'ignoring PLAYBACK_STARTED from non-recording tab:', sender.tab && sender.tab.id);
      return;
    }
    if (session && !session.playbackDetected) {
      session.playbackDetected = true;
      console.log(TAG, 'authoritative PLAYBACK_STARTED at', msg.currentTime, 's.');
      emitStatus({
        phase: 'recording',
        detail: session.title,
        duration: session.duration,
        playing: true,
        note: 'Recording (playing).'
      });
    }
    return;
  }

  // From content script: the lesson finished playing. Accept ONLY from the
  // tab we are actively recording.
  if (msg.type === 'LESSON_ENDED') {
    if (!session || !sender.tab || sender.tab.id !== session.tabId) {
      console.warn(TAG, 'ignoring LESSON_ENDED from non-recording tab:', sender.tab && sender.tab.id);
      return;
    }
    stopCapture('vimeo-ended');
    // No response needed.
    return;
  }

  // From offscreen: capture/upload outcome.
  if (msg.type === 'UPLOAD_RESULT') {
    if (msg.ok) finishSession({ detail: 'Uploaded to ArkaOS', jobId: msg.jobId });
    else failSession(msg.error || 'Upload failed.');
    return;
  }

  // From offscreen: a fatal capture error mid-stream.
  if (msg.type === 'CAPTURE_ERROR') {
    failSession(msg.error || 'Capture error.');
    return;
  }
});

console.log(TAG, 'service worker loaded.');
