---
name: dev/animated-website
description: >
  Convert an MP4 video into a luxury scroll-animated single-file website:
  extracts frames to optimized WebP (desktop + mobile), then builds a
  scroll-driven canvas engine with cinematic dwell pacing, ambient particles,
  film grain, letter-split hero, glass morphism cards, and parallax gallery.
  TRIGGER: "animated website", "scroll animation", "video to website",
  "Apple-style page", "site com scroll do vídeo", "transforma este vídeo num
  site", "frame animation", "/dev animated-website". SKIP: embedding a plain
  video player -> just use <video>; regular animated site WITHOUT a video
  source -> frontend-design skill; video editing/production -> content/video-produce.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch]
metadata:
  origin: community
  source: https://github.com/nutlope/hallmark
  license: MIT
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Animated Website Generator

> **ArkaOS frontend mandate:** this is UI work under `excellence-mandate` —
> load the frontend design skills (frontend-design, ui-ux-pro-max, project
> design system) at maximum effort, emit the `[arka:design]` evidence marker
> before editing UI files, and pass visual review against a named benchmark
> (Apple product pages are the default bar for this skill).

Convert video files into scroll-animated websites with a luxury, cinematic aesthetic. The user provides an MP4 video and a concept brief. You extract frames, optimize for web delivery, and generate a complete website where scrolling plays the video frame-by-frame on a canvas element — with rich overlay text, ambient effects, and gallery sections that elevate it beyond a simple scroll player.

The design language draws from high-end real estate, product launches, and editorial showcases: warm dark palettes, serif/sans-serif type pairing, ambient particles, film grain texture, glass morphism cards, and a scroll-dwell engine that creates natural pacing through content sections.

---

## When This Skill Applies

**This skill IS for:**
- Converting an MP4 video into a scroll-driven animated website
- Luxury showcase pages (real estate, architecture, product, portfolio)
- Apple product page-style frame sequences (scroll to play)
- Any "video → interactive scroll experience" request

**This skill is NOT for:**
- Embedding a video player on a page (just use `<video>`)
- Converting video to GIF or animated WebP
- Building a regular website without video-based scroll animation
- CSS-only scroll animations (use the `frontend-design` skill instead)

**Redirect:** If the user wants a regular animated website WITHOUT a video source, use the `frontend-design` skill.

---

## Input: What You Need From the User

**Required:**
1. **An MP4 video file** — absolute path to the source video
2. **Website concept** — what the site is about (product, brand, property, portfolio, etc.)

**Optional (skill handles defaults if not provided):**
- Target frame count (default: auto-calculated from video duration)
- Brand colors (default: warm-dark luxury palette)
- Section copy (headlines, body text, CTAs)
- Brand name and tagline

If the user gives just a video path and a vague concept, ask ONE clarifying question about the content direction, then proceed.

---

## Process

### Step 1: Analyze the Video

Probe the video to understand what you're working with:

```bash
ffprobe -v quiet -print_format json -show_format -show_streams "/path/to/video.mp4"
```

Parse and present:

```
VIDEO ANALYSIS:
Duration:    12.4s
Resolution:  3840x2160 (4K)
Frame Rate:  30fps
Total Frames: 372
Codec:       H.264
```

Then recommend frame count:

| Video Duration | Recommended Frames | Scroll Height |
|---------------|-------------------|---------------|
| 0-5s          | 60-90             | 400vh         |
| 5-15s         | 100-150           | 650vh         |
| 15-30s        | 150-200           | 800vh         |
| 30s+          | Cap at 200        | 900vh         |

**Get user confirmation before extracting.** Say: "I recommend extracting {N} frames. Sound good, or want to adjust?"

### Step 2: Extract and Optimize Frames

Run the extraction script bundled with this skill (`scripts/extract_frames.py`, relative to this SKILL.md):

```bash
python3 scripts/extract_frames.py \
  --input "/path/to/video.mp4" \
  --output "animated-sites/{slug}/frames" \
  --frames {N} \
  --quality 80
```

Set `--output` to a folder inside the current working directory.

The script produces:
- `frames/desktop/` — 1920x1080 WebP frames
- `frames/mobile/` — 960x540 WebP frames
- `frames/manifest.json` — metadata (counts, sizes, scroll height)

Show the manifest summary to the user. If payload exceeds budget (>10MB desktop, >5MB mobile), recommend `--quality 60` or fewer frames.

### Step 3: Gather Content

Based on the user's concept, prepare content for 6 scroll-text sections. These overlay the video at different scroll positions, creating a narrative experience. The sections are:

1. **Hero** — Property/product name, tagline, key stats
2. **Vision** — A quote or aspirational statement about the subject
3. **Details** — Key specifications or features (with icon list)
4. **Grid** — 4-6 amenities/features in a glass grid layout
5. **Context** — Location, availability, or background info
6. **CTA** — Call to action with buttons and contact info

If the user provides copy, use it. If not, generate content that fits the concept. The content should feel editorial and refined — short sentences, evocative language.

### Step 4: Build the Website

Generate a complete single-file HTML page using the design system below. Save to: `animated-sites/{slug}/index.html`

**Adapt the content and branding to the concept** — the design patterns stay consistent but the palette, copy, and section content should fit the subject matter. A tech product might use cooler blues, a restaurant warmer golds, a real estate listing the warm-neutral default.

### Step 5: Serve and Preview

```bash
cd "animated-sites/{slug}"
python3 -m http.server 8080
```

Then open `http://localhost:8080/index.html` in the browser and take screenshots at different scroll positions to verify.

Common iteration requests:
- "Slower scroll" → increase animation-section height (650vh → 900vh)
- "Faster scroll" → decrease height (650vh → 400vh)
- "Smoother animation" → decrease LERP_FACTOR (0.09 → 0.05)
- "More responsive" → increase LERP_FACTOR (0.09 → 0.15)
- "Change text" → edit the scroll-text overlay content
- "Different colors" → update CSS custom properties in `:root`

---

## Design System

The visual language is warm, dark, and cinematic. Every element serves the animation — surrounding effects (grain, particles, vignette) add depth without competing with the video frames.

**Motion craft reference:** `references/motion-recipes.md` — timing/easing
mapped onto the doctrine-hub §4 tokens, 15 named interaction recipes, 20
motion tells, the exits-at-75% rule and the reduced-motion floor. This
skill's scroll-scrubbed canvas engine is the named exception to the
no-scroll-scrub rule; its reduced-motion fallback stays mandatory.

### Color Palette (CSS Custom Properties)

```css
:root {
  --concrete: #d4cfc8;       /* muted warm gray */
  --concrete-dim: #9e9890;   /* secondary text */
  --stone: #706050;          /* decorative accents */
  --charcoal: #1a1816;       /* card backgrounds */
  --ink: #0e0d0c;            /* page background */
  --warm-white: #f4f0ea;     /* primary text */
  --warm-white-dim: #c8c0b4; /* emphasized secondary */
  --accent-blue: #4a6aff;    /* accent color - adapt per brand */
  --accent-blue-glow: rgba(74, 106, 255, 0.35);
  --accent-blue-soft: rgba(74, 106, 255, 0.08);
  --sunset-pink: #d4a0b0;    /* secondary accent */
  --gold-warm: #c89848;      /* tertiary accent */
  --heading: 'Playfair Display', 'Georgia', serif;
  --body: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
}
```

Adapt the `--accent-blue` family for different brands. The warm-dark base (`--ink`, `--warm-white`) stays consistent — it makes the video frames pop and creates the luxury atmosphere.

### Typography

- **Headings:** Playfair Display — weight 300 for elegance, italic for emphasis
- **Body:** DM Sans — weight 300-500, generous letter-spacing
- **Labels:** DM Sans, 8-9px, weight 500, 0.25-0.35em letter-spacing, uppercase
- **Hero titles:** clamp(42px, 5.5vw, 76px) — big but light weight

Load from Google Fonts:
```html
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;1,300;1,400&family=Playfair+Display:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300;1,400&display=swap" rel="stylesheet">
```

### Layer Stack (z-index)

The site layers multiple visual effects. Here's the stacking order:

| Z-Index | Element | Purpose |
|---------|---------|---------|
| 9999 | Loader | Branded loading screen with progress bar |
| 9998 | Cursor dot | Custom cursor inner dot (mix-blend-mode: difference) |
| 9997 | Cursor ring | Custom cursor outer ring (expands on hover) |
| 100 | Film grain | SVG noise overlay at 3.5% opacity |
| 99 | Vignette | Radial gradient darkening edges |
| 50 | Chapter markers | Fixed right-side navigation dots |
| 15 | Particles | Ambient floating particles canvas |
| 10 | Scroll text | Content overlays during animation |
| 5 | Tint overlay | Dynamic color wash per section |
| 1 | Canvas overlays | Left gradient + bottom gradient for text readability |
| 0 | Video canvas | The scroll-driven frame animation |

### Ambient Effects

These create the cinematic atmosphere. All are pointer-events: none and purely decorative.

**Film Grain:** SVG feTurbulence fractalNoise, 256px tile, opacity 0.035. Gives the site a filmic texture.

**Vignette:** Radial gradient from transparent (center 50%) to rgba(14,13,12,0.45) at edges. Draws focus to center.

**Ambient Particles:** Fixed canvas, ~40 small dots (0.3-1.8px), slow random drift, warm-white at 5-35% opacity. Creates a living, breathing feel. Wrap at edges so they float continuously.

**Dynamic Tint:** Canvas overlay that shifts hue based on current scroll section. Subtle (6-4% opacity) gradient from accent-blue to sunset-pink. Makes each section feel distinct.

**Custom Cursor (desktop only):** Two-part cursor: a 6px dot with mix-blend-mode: difference (always visible against any background) and a 36px ring that trails the dot with LERP. Ring expands to 56px on hover over interactive elements and gains accent-blue glow. Hide on mobile.

### Scroll Dwell Engine

This is what makes the scroll feel magical instead of mechanical. Rather than mapping scroll position linearly to frames, the dwell engine creates "almost stops" at each content section — the scroll slows down there, giving users time to read, then speeds up between sections.

**How it works:**
1. Define dwell centers — the scroll positions where content appears (e.g., 0.065, 0.21, 0.365, 0.525, 0.685, 0.89)
2. At each center, a Gaussian density function peaks — meaning more scroll distance is consumed per unit of effective progress
3. Build a cumulative integral lookup table (forward mapping)
4. Invert it for the actual remap function (scroll position → effective progress)

The dwell centers should align with the `data-show-at` values of scroll-text sections. With 6 sections, space them roughly evenly across 0-1 but offset from the edges.

Parameters to tune:
- `DWELL_WIDTH` (0.045): How wide the slow zone is. Smaller = tighter pause.
- `DWELL_PEAK` (3.5): How much slower the scroll feels at dwell points. Higher = more dramatic pause.
- `REMAP_N` (2000): Resolution of the lookup table. 2000 is smooth enough.

### Scroll Text Overlays

Six sections that appear and disappear at specific scroll positions. Each has its own layout and style:

1. **Hero** (positioned left, 6% from edge): Property/product name with letter-split animation, tagline, price/key metric. Has a glass stat bar at bottom with 4-5 key numbers.

2. **Vision** (positioned left): Opening quotation mark as decorative element, italic serif quote, divider line, attribution.

3. **Details** (positioned left): Overline label, serif title, body text, feature list with icon items and subtle borders.

4. **Grid** (positioned left): Overline label, 2-column glass grid of 6 amenity/feature cells with icons and descriptions.

5. **Context** (positioned left): Overline label, serif title, body text, distance/detail list with dotted connecting lines.

6. **CTA** (centered): Large serif title with italic emphasis, subtitle, two buttons (primary filled, secondary outline), and agent/contact card.

Each section fades in with blur(6px→0) and translateX(-20px→0) transitions. The `.visible` class is toggled based on scroll progress matching the `data-show-at` / `data-hide-at` attributes.

### Glass Morphism Cards

Used for stat bars and amenity grids:
- Background: rgba(244, 240, 234, 0.03)
- backdrop-filter: blur(20px)
- Border: 1px solid rgba(244, 240, 234, 0.06)
- On hover: background brightens to 0.06, border gains accent-blue tint

### Chapter Markers

Fixed right-side vertical navigation showing 6 dots connected by lines. The active dot gets accent-blue glow and the connecting line fills with progress as you scroll through the section. Dots can have labels that appear on hover.

### Gallery Section

Below the scroll animation, a masonry-ish grid of frames from the video. Uses IntersectionObserver for reveal animations and requestAnimationFrame-based parallax transforms (data-parallax attribute with positive/negative px values).

Grid layout: `grid-template-columns: repeat(3, 1fr)` with some items spanning 2 rows via `.tall` class. Images have subtle hover zoom (scale 1.03) with overflow hidden.

Pick 6-7 evenly spaced frames from the video for gallery images.

### Branded Loader

Not just a progress bar — a branded experience:
- Centered brand mark in uppercase letter-spaced heading font
- Decorative lines above and below
- Thin 140px progress bar with gradient fill (accent-blue → sunset-pink)
- Percentage counter below
- Exits with opacity 0 + blur(8px) transition

### Footer

Minimal: brand name in heading font, legal line in small body text, dark background slightly lighter than ink.

---

## Code Architecture

The entire site is a single HTML file. Here's the structural order:

```
HTML:
  1. Google Fonts link
  2. <style> with all CSS
  3. Custom cursor divs (#cursor-dot, #cursor-ring)
  4. Film grain overlay div
  5. Vignette overlay div
  6. Particles canvas (fixed)
  7. Loader (fixed, z-9999)
  8. Chapter markers (fixed right)
  9. Animation section (relative, 650vh)
     - Canvas container (sticky)
       - Main canvas
       - Left gradient overlay
       - Bottom gradient overlay
       - Tint overlay
     - 6 scroll-text overlays (fixed, toggled by JS)
  10. Gallery section
  11. Footer
  12. <script> with all JS

JS order:
  1. Custom cursor tracking + ring LERP
  2. Particle system init + animation loop
  3. Letter-split animation (data-split attribute)
  4. Scroll dwell/remap engine (LUT construction)
  5. Frame loading (critical first, then batches)
  6. Scroll animation loop (remap → LERP → drawFrame)
  7. Scroll-text visibility toggling
  8. Chapter marker updates
  9. Tint overlay updates
  10. Gallery IntersectionObserver + parallax
  11. Stat counter animation
  12. Init: load frames → hide loader → start animation
```

### Key JavaScript Patterns

**Frame loading with progressive enhancement:**
```javascript
// Critical frames first (evenly spaced), then batches
// Use createImageBitmap for off-thread decode when available
// Show first frame immediately after critical load
```

**Scroll-to-frame with dwell remap:**
```javascript
function getScrollProgress() {
  const rect = section.getBoundingClientRect();
  return Math.max(0, Math.min(1, -rect.top / (rect.height - window.innerHeight)));
}

function animate() {
  const rawProgress = getScrollProgress();
  const remapped = remapProgress(rawProgress);  // dwell engine
  targetFrame = Math.floor(remapped * (FRAME_COUNT - 1));
  currentFrame += (targetFrame - currentFrame) * LERP_FACTOR;
  drawFrame(Math.round(currentFrame));
  // Also update scroll-text visibility, chapter markers, tint
  requestAnimationFrame(animate);
}
```

**Stat counter animation:**
```javascript
// When stat-bar becomes visible, animate numbers from 0 to target
// Use ease-out cubic easing over ~1.5s
// Parse target from data-target attribute, handle commas/units
```

---

## Adapting for Different Concepts

The design system is flexible. Here's how to adapt it:

**Real Estate:** Default palette works perfectly. Use property name as hero title, price and specs in stat bar, architecture details, amenity grid, location distances, viewing CTA.

**Tech Product:** Shift accent to cooler blue (#2563eb) or electric violet (#7c3aed). Hero has product name + tagline, stat bar shows key specs (battery, weight, price), Details lists tech specs, Grid shows features, CTA is "Pre-order" or "Learn More".

**Portfolio/Creative:** Use gold-warm (#c89848) as accent. Hero has creator name + discipline, Vision quotes an artistic statement, Details shows notable works, Grid shows services/capabilities, CTA is "Get in Touch".

**Restaurant/Hospitality:** Warm accent (#c89848 or deep burgundy). Hero is venue name, Vision is a chef quote, Details is cuisine philosophy, Grid is menu highlights or experiences, Context is location/hours.

**Automotive:** Keep accent-blue or shift to silver (#a8a8a8). Hero is vehicle name + starting price, stat bar shows 0-60/HP/range, Details is engineering highlights.

In all cases, the 6-section structure, ambient effects, scroll-dwell engine, and glass morphism cards remain the same — they create the luxury feel regardless of content.

---

## Quality Checklist

Before showing the site to the user, verify:

- [ ] **Smooth at 60fps** — no jank or frame drops during scroll
- [ ] **First frame visible in <1s** — progressive loading works
- [ ] **Loading bar accurate** — gradient fill, percentage counter updates
- [ ] **Desktop payload <10MB** — check manifest.json
- [ ] **Mobile payload <5MB** — check manifest.json
- [ ] **Reduced motion handled** — static first frame when prefers-reduced-motion
- [ ] **No blank frames** — nearest-neighbor fallback fills gaps
- [ ] **Responsive** — canvas scales on resize, mobile layout works
- [ ] **Custom cursor works on desktop** — dot tracks instantly, ring trails
- [ ] **Particles animate** — subtle floating dots visible against dark bg
- [ ] **Scroll text appears/disappears** — 6 sections at correct scroll positions
- [ ] **Letter-split hero animates** — characters appear sequentially
- [ ] **Glass stat bar readable** — blur backdrop works, numbers visible
- [ ] **Gallery loads** — images from frames directory, parallax on scroll
- [ ] **Dwell engine feels natural** — scroll slows at content, speeds between
- [ ] **Chapter markers update** — active dot highlighted, progress lines fill

---

## Output Format

```
animated-sites/{slug}/
├── frames/
│   ├── desktop/              # 1920x1080 WebP
│   │   ├── frame-0001.webp
│   │   └── ...
│   ├── mobile/               # 960x540 WebP
│   │   ├── frame-0001.webp
│   │   └── ...
│   └── manifest.json         # Frame metadata
└── index.html                # Complete luxury scroll site
```

To view: `cd` into the output directory and run `python3 -m http.server 8080`, then open `localhost:8080`.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| FFmpeg not found | `brew install ffmpeg` |
| No libwebp support | `brew reinstall ffmpeg` (includes libwebp by default) |
| Frames too large (>10MB) | Lower quality: `--quality 60`. Reduce count: `--frames 90` |
| Animation stutters | Reduce frame count. Check DPR cap is 2. Decrease particles. |
| White flash between frames | Nearest-frame fallback not finding frames. Check extraction. |
| Canvas blank on mobile | Verify mobile frames exist. Check FRAME_DIR path switch. |
| Loading bar stuck | A frame 404'd. Check browser console. Verify frame paths. |
| Scroll too fast/slow | Adjust animation-section height. 650vh = default. |
| Dwell feels too sticky | Decrease DWELL_PEAK (3.5 → 2.5) or increase DWELL_WIDTH |
| Particles too visible | Decrease particles-canvas opacity (0.4 → 0.2) |
| Custom cursor jittery | Increase ring LERP factor (0.15 → 0.2) |
| Glass blur not working | Safari needs -webkit-backdrop-filter. Already included in CSS. |
| CORS error locally | Serve with `python3 -m http.server 8080`. Don't double-click HTML. |
| Fonts not loading | Check Google Fonts link. Fallback fonts in CSS vars handle it. |
