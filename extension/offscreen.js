/**
 * ArkaOS Course Recorder (PoC) — offscreen document.
 *
 * The only context in MV3 that can do all of: getUserMedia(streamId),
 * MediaRecorder, an AudioContext, and fetch() with FormData. The service
 * worker hands us a tab-capture streamId; we:
 *   1. resolve it to a MediaStream via getUserMedia with the legacy
 *      chromeMediaSource constraints (the documented tab-capture path),
 *   2. AUDIBLE PASSTHROUGH: tab capture mutes the tab by default, so we route
 *      the captured audio through an AudioContext to destination (speakers)
 *      so the user still hears the lesson while it records,
 *   3. run MediaRecorder to collect webm/opus chunks,
 *   4. on stop, build a Blob, wrap it in a File named from the lesson title,
 *      and POST it as multipart `file` to the dashboard upload endpoint,
 *   5. report the outcome back to the service worker.
 *
 * Mirrors the dashboard's proven helpers (pickRecorderMime / safeFilename /
 * FormData field name `file`) from dashboard/app/pages/knowledge/index.vue.
 */

const TAG = '[ArkaOS][offscreen]';

let mediaStream = null;
let mediaRecorder = null;
let audioContext = null;
let chunks = [];
let uploadParams = null; // { title, uploadUrl }

/** Choose a supported webm/opus mime, matching the dashboard's preference order. */
function pickRecorderMime() {
  if (typeof MediaRecorder === 'undefined') return undefined;
  const prefs = ['audio/webm;codecs=opus', 'audio/webm'];
  for (const m of prefs) {
    if (MediaRecorder.isTypeSupported(m)) return m;
  }
  return undefined;
}

/** Sanitize a title into a filename-safe stem (same rules as the dashboard). */
function safeFilename(title) {
  const stem = (title || 'lesson')
    .trim()
    .replace(/[^a-zA-Z0-9 _-]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 80);
  return stem || 'lesson';
}

/** Stop and release the stream tracks, recorder, and audio graph. */
function releaseAll() {
  try {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();
  } catch (e) { /* ignore */ }
  mediaRecorder = null;

  if (mediaStream) {
    mediaStream.getTracks().forEach((t) => t.stop());
    mediaStream = null;
  }
  if (audioContext) {
    audioContext.close().catch(() => {});
    audioContext = null;
  }
}

function reportError(message) {
  console.warn(TAG, 'error:', message);
  releaseAll();
  chunks = [];
  try {
    chrome.runtime.sendMessage({ type: 'CAPTURE_ERROR', error: message });
  } catch (e) { /* sw may be transient */ }
}

/** Build the blob, name the file, and upload it as multipart `file`. */
async function buildAndUpload() {
  const mime = (mediaRecorder && mediaRecorder.mimeType) || 'audio/webm';
  const blob = new Blob(chunks, { type: mime });
  chunks = [];

  if (!blob.size) {
    chrome.runtime.sendMessage({ type: 'UPLOAD_RESULT', ok: false, error: 'Recording was empty (0 bytes).' });
    return;
  }

  const stem = safeFilename(uploadParams?.title);
  const file = new File([blob], `${stem}.webm`, { type: mime });
  console.log(TAG, 'uploading', file.name, `(${blob.size} bytes, ${mime})`);

  try {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(uploadParams.uploadUrl, { method: 'POST', body: form });
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new Error(`HTTP ${res.status} ${res.statusText} ${text}`.trim());
    }
    let jobId;
    try {
      const json = await res.json();
      jobId = json && (json.job_id || json.jobId);
    } catch (e) { /* non-JSON body is acceptable */ }
    console.log(TAG, 'upload ok, job:', jobId);
    chrome.runtime.sendMessage({ type: 'UPLOAD_RESULT', ok: true, jobId });
  } catch (e) {
    chrome.runtime.sendMessage({ type: 'UPLOAD_RESULT', ok: false, error: 'Upload failed: ' + (e.message || e) });
  }
}

/** Resolve a tab-capture streamId into a MediaStream and start recording. */
async function startCapture(streamId, title, uploadUrl) {
  if (mediaRecorder) throw new Error('Already capturing.');
  uploadParams = { title, uploadUrl };
  chunks = [];

  // The documented MV3 tab-capture path: getUserMedia with the legacy
  // mandatory chromeMediaSource constraints keyed by the streamId.
  mediaStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      mandatory: {
        chromeMediaSource: 'tab',
        chromeMediaSourceId: streamId
      }
    },
    video: false
  });

  if (!mediaStream.getAudioTracks().length) {
    throw new Error('No audio track in the captured tab stream.');
  }

  // --- AUDIBLE PASSTHROUGH ---------------------------------------------------
  // Tab capture mutes the tab for the user. Pipe the captured audio to the
  // default output so the lesson is still heard while we record it. This does
  // not affect what MediaRecorder receives (it reads from mediaStream's track).
  try {
    audioContext = new AudioContext();
    const sourceNode = audioContext.createMediaStreamSource(mediaStream);
    sourceNode.connect(audioContext.destination);
    if (audioContext.state === 'suspended') {
      // A user gesture initiated this chain (popup click), so resume is allowed.
      await audioContext.resume().catch(() => {});
    }
    console.log(TAG, 'audible passthrough connected (state:', audioContext.state + ').');
  } catch (e) {
    // Passthrough is a UX nicety; recording can proceed without it.
    console.warn(TAG, 'passthrough setup failed (recording continues, tab may be silent):', e);
  }

  const mimeType = pickRecorderMime();
  mediaRecorder = mimeType ? new MediaRecorder(mediaStream, { mimeType }) : new MediaRecorder(mediaStream);

  mediaRecorder.ondataavailable = (ev) => {
    if (ev.data && ev.data.size > 0) chunks.push(ev.data);
  };
  mediaRecorder.onerror = (ev) => {
    reportError('MediaRecorder error: ' + (ev.error?.message || 'unknown'));
  };
  mediaRecorder.onstop = () => {
    console.log(TAG, 'recorder stopped; building blob.');
    // Release stream/audio graph BEFORE uploading; the data is already in chunks.
    if (mediaStream) {
      mediaStream.getTracks().forEach((t) => t.stop());
      mediaStream = null;
    }
    if (audioContext) {
      audioContext.close().catch(() => {});
      audioContext = null;
    }
    buildAndUpload();
  };

  // Timeslice so we get periodic chunks (resilience against a missed final flush).
  mediaRecorder.start(1000);
  console.log(TAG, 'recording started, mime:', mediaRecorder.mimeType);
}

/** Stop the recorder; onstop drives blob build + upload. */
function stopCapture() {
  if (!mediaRecorder) {
    console.warn(TAG, 'stopCapture with no active recorder.');
    return;
  }
  if (mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
  }
}

/**
 * Discard the capture WITHOUT uploading. Used when no real playback was ever
 * detected, so the buffer is silence/empty. Detach onstop first so the normal
 * build-and-upload path does not run, then release everything and drop chunks.
 */
function discardCapture() {
  if (mediaRecorder) {
    mediaRecorder.onstop = null; // prevent buildAndUpload
  }
  releaseAll();
  chunks = [];
  console.log(TAG, 'capture discarded (no upload).');
}

// --- Message router (service worker -> offscreen) ---------------------------

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (!msg || msg.target !== 'offscreen' || !msg.type) return;

  // SECURITY: only the service worker drives the offscreen document. Accept
  // ONLY same-extension messages with no sender.tab (a content script would
  // carry sender.tab; foreign senders fail the runtime.id check).
  if (!sender || sender.id !== chrome.runtime.id || sender.tab) {
    console.warn(TAG, 'rejected offscreen message from unexpected sender:', sender && sender.id);
    return;
  }

  if (msg.type === 'START_CAPTURE') {
    startCapture(msg.streamId, msg.title, msg.uploadUrl)
      .then(() => sendResponse({ ok: true }))
      .catch((err) => {
        releaseAll();
        sendResponse({ ok: false, error: String(err.message || err) });
      });
    return true; // async
  }

  if (msg.type === 'STOP_CAPTURE') {
    stopCapture();
    sendResponse({ ok: true });
    return;
  }

  if (msg.type === 'DISCARD_CAPTURE') {
    discardCapture();
    sendResponse({ ok: true });
    return;
  }
});

console.log(TAG, 'offscreen document loaded.');
