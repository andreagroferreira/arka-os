# ArkaOS Course Recorder (PoC)

A Chrome MV3 extension that records the audio of **one** currently-open
G4/Vimeo course lesson and sends it to the local ArkaOS dashboard, where the
existing pipeline transcribes it with Whisper.

This is a **proof of concept**: it proves the hardest mechanics (MV3 tab
capture via an offscreen document, audible passthrough, cross-origin Vimeo
control, and the multipart upload). The full course-by-course loop is a later
phase — `background.js` is structured so `recordLesson()` can be called per
lesson in sequence.

## What it does

1. You open a G4 lesson page and click the extension's **Start recording**.
2. The extension attaches to the Vimeo player, reads the lesson **title** and
   **duration**, starts capturing the **tab's audio**, and presses play.
3. It detects the lesson end via the Vimeo `ended` event (primary) with a
   duration + 15s safety timeout as a fallback.
4. It builds a `.webm` (Opus) Blob, names it from the sanitized lesson title,
   and POSTs it to `http://localhost:3334/api/knowledge/upload-file` as
   multipart field `file`.
5. The popup shows status: idle → recording mm:ss → uploading → done/failed.

## Load it unpacked

1. Open `chrome://extensions`.
2. Enable **Developer mode** (top-right toggle).
3. Click **Load unpacked**.
4. Select this `extension/` directory.
5. Pin the extension, open a G4 lesson, click the icon, press **Start**.

> The ArkaOS dashboard must be running on `http://localhost:3334` and its CORS
> must allow the `chrome-extension://…` origin for the upload to succeed
> (being added in parallel).

## How the three contexts communicate

```
                 window.postMessage                 chrome.runtime
 page-world  <───────────────────────►  content.js  ◄──────────────►  background.js  (service worker)
 Vimeo bridge   (Vimeo Player API)                                          │
 (player.js)                                                  chrome.runtime │ chrome.offscreen
                                                                            ▼
                                                                       offscreen.js  (offscreen doc)
                                                                       getUserMedia + MediaRecorder
                                                                       + audible passthrough + upload
```

- **content.js** runs in the page's isolated world. It injects a tiny
  page-world bridge that loads Vimeo's `player.js`, builds
  `new Vimeo.Player(iframe)`, and reads title/duration, plays, and forwards the
  `ended` event. Content ↔ bridge use `window.postMessage`; content ↔
  background use `chrome.runtime`.
- **background.js** (service worker) orchestrates: reads lesson info, gets a
  tab-capture `streamId` via `chrome.tabCapture.getMediaStreamId`, creates the
  offscreen document, relays start/stop, and resolves on upload.
- **offscreen.js** (offscreen document) does the media work the service worker
  cannot: `getUserMedia` from the streamId, `MediaRecorder`, audible
  passthrough, blob build, and the multipart `fetch` upload.

## Audible passthrough (the mute gotcha)

Chrome **mutes the tab** when you tab-capture it. So in `offscreen.js` we route
the captured stream back to the speakers:

```js
audioContext = new AudioContext();
const sourceNode = audioContext.createMediaStreamSource(mediaStream);
sourceNode.connect(audioContext.destination); // user hears the lesson
```

`MediaRecorder` still reads the same `mediaStream`, so recording is unaffected.

## Permissions (least privilege)

- `permissions`: `tabCapture`, `offscreen`, `scripting`, `activeTab`
- `host_permissions`: `https://plataforma.g4business.com/*`,
  `http://localhost:3334/*`

No `<all_urls>`. No analytics. No secrets in code.

## Known limitations / caveats

- **PoC scope**: records one lesson per Start click. The full course loop is
  the next phase.
- The lesson must use a **Vimeo iframe**; otherwise the popup shows a clear
  "No Vimeo player found" error.
- The dashboard must be up at `localhost:3334` with CORS allowing the extension
  origin.
- **Terms of Service**: only record content you are licensed to access. This
  records the audio your machine legitimately plays (the "analog hole"), the
  same category as a meeting recorder; it never touches DRM/encrypted streams.
  Use responsibly and in line with the platform's ToS.
