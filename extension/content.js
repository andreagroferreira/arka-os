/**
 * ArkaOS Course Recorder (PoC) — content script.
 *
 * Runs in the G4 lesson page's ISOLATED world. It cannot touch the page's
 * `window.Vimeo` global directly, so it injects a tiny page-world bridge
 * (`page-bridge.js` text, built inline) that:
 *   - loads the official Vimeo Player API (player.js),
 *   - constructs `new Vimeo.Player(iframe)`,
 *   - reads title + duration, controls play(), and listens for 'ended'.
 *
 * The page-world bridge talks to this content script via `window.postMessage`.
 * This content script talks to the background service worker via
 * `chrome.runtime`. So the message path is:
 *
 *   page-world bridge  <-- window.postMessage -->  content.js  <-- chrome.runtime -->  background.js
 *
 * All bridge messages carry `{ source: 'arkaos-bridge', type, ... }` and all
 * content->bridge commands carry `{ source: 'arkaos-content', type, ... }`
 * so the two never confuse each other's traffic.
 */

(function () {
  'use strict';

  if (!chrome?.runtime?.id) {
    console.warn('[ArkaOS][content] chrome.runtime unavailable; aborting.');
    return;
  }
  // Guard against double-injection (SPA navigations can re-run scripts).
  if (window.__arkaosContentLoaded) {
    console.log('[ArkaOS][content] already loaded; skipping re-init.');
    return;
  }
  window.__arkaosContentLoaded = true;

  const PLAYER_JS_URL = 'https://player.vimeo.com/api/player.js';
  const pending = new Map(); // requestId -> { resolve, reject, timer }
  let reqSeq = 0;

  /**
   * The page-world bridge source. It is stringified and injected as a
   * <script> tag so it runs with access to the page's `window` (and thus
   * the Vimeo global once player.js loads). It is intentionally dependency
   * free and posts everything back via window.postMessage.
   */
  function pageBridgeSource(playerJsUrl) {
    const fn = function (PLAYER_JS_URL) {
      const TAG = '[ArkaOS][bridge]';
      let player = null;
      let playbackStartedPosted = false; // fire PLAYBACK_STARTED exactly once

      function post(msg) {
        window.postMessage(Object.assign({ source: 'arkaos-bridge' }, msg), window.location.origin);
      }

      function findIframe() {
        // Only attach to a genuine Vimeo iframe. No arbitrary fallback: if
        // there is no Vimeo player, return null and let the caller surface the
        // "No Vimeo player found" error rather than driving a random iframe.
        return document.querySelector('iframe[src*="vimeo.com"], iframe[src*="player.vimeo"]');
      }

      function loadPlayerJs() {
        return new Promise(function (resolve, reject) {
          if (window.Vimeo && window.Vimeo.Player) return resolve();
          const existing = document.querySelector('script[data-arkaos-vimeo]');
          if (existing) {
            existing.addEventListener('load', function () { resolve(); });
            existing.addEventListener('error', function () { reject(new Error('player.js failed to load')); });
            return;
          }
          const s = document.createElement('script');
          s.src = PLAYER_JS_URL;
          s.async = true;
          s.setAttribute('data-arkaos-vimeo', '1');
          s.addEventListener('load', function () { resolve(); });
          s.addEventListener('error', function () { reject(new Error('player.js failed to load')); });
          (document.head || document.documentElement).appendChild(s);
        });
      }

      function ensurePlayer() {
        return loadPlayerJs().then(function () {
          if (player) return player;
          const iframe = findIframe();
          if (!iframe) throw new Error('No Vimeo iframe found on this page.');
          player = new window.Vimeo.Player(iframe);
          // Forward the natural end-of-lesson event.
          player.on('ended', function () {
            console.log(TAG, "Vimeo 'ended' fired.");
            post({ type: 'ended' });
          });
          // AUTHORITATIVE PLAYBACK SIGNAL: the play() promise can resolve under
          // autoplay policy without media actually advancing, so we trust
          // currentTime instead. Once it first crosses ~0.5s we emit a one-time
          // PLAYBACK_STARTED. 'timeupdate' fires ~4x/sec during real playback.
          player.on('timeupdate', function (data) {
            if (playbackStartedPosted) return;
            var t = data && typeof data.seconds === 'number' ? data.seconds : 0;
            if (t > 0.5) {
              playbackStartedPosted = true;
              console.log(TAG, 'real playback detected at', t, 's; posting PLAYBACK_STARTED.');
              post({ type: 'playback-started', currentTime: t });
            }
          });
          return player;
        });
      }

      function handle(cmd, requestId) {
        const reply = function (ok, payload) {
          post({ type: 'reply', requestId: requestId, ok: ok, payload: payload });
        };
        ensurePlayer().then(function (p) {
          switch (cmd.type) {
            case 'info':
              return Promise.all([p.getVideoTitle(), p.getDuration()])
                .then(function (r) { reply(true, { title: r[0], duration: r[1] }); });
            case 'play': {
              // NEVER await play() unboundedly. The browser autoplay policy can
              // reject OR leave the promise pending when the click gesture did
              // not propagate through the message hops. Race play() against a
              // short timeout and report the outcome WITHOUT failing the flow:
              // authoritative "playing" comes from the timeupdate signal, not
              // from this promise.
              var PLAY_RACE_MS = 2500;
              var settled = false;
              var settle = function (outcome) {
                if (settled) return;
                settled = true;
                reply(true, { play: outcome });
              };
              var timer = setTimeout(function () {
                console.warn(TAG, 'play() did not resolve within', PLAY_RACE_MS, 'ms (autoplay policy?). Continuing.');
                settle('timeout');
              }, PLAY_RACE_MS);
              return p.play().then(function () {
                clearTimeout(timer);
                settle('resolved');
              }).catch(function (err) {
                clearTimeout(timer);
                console.warn(TAG, 'play() rejected (autoplay policy?):', err);
                settle('rejected');
              });
            }
            case 'pause':
              return p.pause().then(function () { reply(true, {}); });
            default:
              reply(false, { error: 'Unknown command: ' + cmd.type });
          }
        }).catch(function (err) {
          console.warn(TAG, 'command failed:', cmd.type, err);
          reply(false, { error: String(err && err.message ? err.message : err) });
        });
      }

      window.addEventListener('message', function (ev) {
        // Only trust messages from THIS window/origin (bridge and content
        // script share both). Rejects anything forwarded from cross-origin
        // frames or injected by other windows.
        if (ev.source !== window) return;
        if (ev.origin !== window.location.origin) return;
        const d = ev.data;
        if (!d || d.source !== 'arkaos-content') return;
        handle(d, d.requestId);
      });

      console.log(TAG, 'page-world bridge ready.');
      post({ type: 'bridge-ready' });
    };
    return '(' + fn.toString() + ')(' + JSON.stringify(playerJsUrl) + ');';
  }

  function injectBridge() {
    if (document.querySelector('script[data-arkaos-bridge]')) return;
    const s = document.createElement('script');
    s.setAttribute('data-arkaos-bridge', '1');
    s.textContent = pageBridgeSource(PLAYER_JS_URL);
    (document.head || document.documentElement).appendChild(s);
    s.remove(); // the code has already executed; tidy the DOM.
  }

  // content <- bridge replies / events
  window.addEventListener('message', function (ev) {
    // Only trust messages from THIS window/origin (bridge and content script
    // share both). Rejects forged signals posted from cross-origin frames.
    if (ev.source !== window) return;
    if (ev.origin !== window.location.origin) return;
    const d = ev.data;
    if (!d || d.source !== 'arkaos-bridge') return;

    if (d.type === 'reply') {
      const entry = pending.get(d.requestId);
      if (!entry) return;
      clearTimeout(entry.timer);
      pending.delete(d.requestId);
      if (d.ok) entry.resolve(d.payload);
      else entry.reject(new Error(d.payload && d.payload.error ? d.payload.error : 'bridge error'));
      return;
    }
    if (d.type === 'playback-started') {
      console.log('[ArkaOS][content] relaying PLAYBACK_STARTED -> background.');
      try { chrome.runtime.sendMessage({ type: 'PLAYBACK_STARTED', currentTime: d.currentTime }); } catch (e) { /* sw asleep ok */ }
      return;
    }
    if (d.type === 'ended') {
      console.log('[ArkaOS][content] relaying ended -> background.');
      try { chrome.runtime.sendMessage({ type: 'LESSON_ENDED' }); } catch (e) { /* sw asleep ok */ }
      return;
    }
    if (d.type === 'bridge-ready') {
      console.log('[ArkaOS][content] bridge ready.');
    }
  });

  /** Send a command to the page-world bridge and await its reply. */
  function callBridge(type, timeoutMs) {
    return new Promise(function (resolve, reject) {
      const requestId = 'r' + (++reqSeq);
      const timer = setTimeout(function () {
        pending.delete(requestId);
        reject(new Error('Vimeo bridge timed out for command: ' + type));
      }, timeoutMs || 8000);
      pending.set(requestId, { resolve: resolve, reject: reject, timer: timer });
      window.postMessage({ source: 'arkaos-content', type: type, requestId: requestId }, window.location.origin);
    });
  }

  // Background -> content commands.
  chrome.runtime.onMessage.addListener(function (msg, _sender, sendResponse) {
    if (!msg || !msg.type) return;

    if (msg.type === 'GET_LESSON_INFO') {
      callBridge('info').then(function (info) {
        sendResponse({ ok: true, info: info });
      }).catch(function (err) {
        sendResponse({ ok: false, error: String(err.message || err) });
      });
      return true; // async response
    }
    if (msg.type === 'PLAY_LESSON') {
      // The bridge races play() against a 2.5s timeout and ALWAYS replies ok
      // with a { play: 'resolved'|'rejected'|'timeout' } outcome, so this never
      // blocks. Forward the outcome; the background treats it as informational
      // only (authoritative "playing" is PLAYBACK_STARTED).
      callBridge('play', 6000).then(function (info) {
        sendResponse({ ok: true, info: info });
      }).catch(function (err) {
        sendResponse({ ok: false, error: String(err.message || err) });
      });
      return true;
    }
    if (msg.type === 'PAUSE_LESSON') {
      callBridge('pause').then(function () {
        sendResponse({ ok: true });
      }).catch(function (err) {
        sendResponse({ ok: false, error: String(err.message || err) });
      });
      return true;
    }
  });

  injectBridge();
  console.log('[ArkaOS][content] loaded on', location.href);
})();
