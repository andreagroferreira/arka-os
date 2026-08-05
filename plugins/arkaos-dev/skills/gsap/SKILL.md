---
name: gsap
description: >
  GSAP animation implementation from the official GreenSock skill pack:
  core tweens and easing, timelines, ScrollTrigger, the plugin family
  (Flip, Draggable, SplitText, MorphSVG…), utility helpers, framework
  wiring, React's useGSAP, and the performance review bar — one router
  with the eight official modules as progressive-disclosure references.
  TRIGGER: "gsap", "scrolltrigger", "anima com gsap", "scroll-driven
  animation em JS", "animate on scroll", "timeline animation", "pin/scrub
  section", "parallax em código", "useGSAP", "/dev gsap".
  SKIP: deciding WHAT should move and why (direction, easing families,
  choreography) -> brand/motion-design; the same effect in pure CSS
  (scroll timelines, view transitions) -> dev/css-native; React
  spring/gesture idioms without GSAP -> dev/framer-motion; an existing
  MP4 turned into a scroll site -> dev/animated-website; a pre-rendered
  3D world scrubbed by scroll -> dev/scroll-world; real-time 3D ->
  dev/threejs.
metadata:
  origin: community
  source: https://github.com/greensock/gsap-skills
  license: MIT
---

# GSAP

> **Agent:** Diana (Frontend Dev) | **Framework:** GSAP (official GreenSock skill pack)
> Direction comes first: when the motion language is not yet decided,
> `brand/motion-design` chooses what moves and why; this skill writes it.

## How to use this router

The eight official modules live under `references/`, upstream
near-verbatim. Load the one the task needs — never all eight:

| The task involves | Read |
|---|---|
| Basic tweens, easing, stagger, defaults, `matchMedia` (responsive, reduced-motion), vanilla-JS setup | `references/core.md` |
| Sequencing multiple steps, labels, position parameter | `references/timeline.md` |
| Scroll-linked animation, pin, scrub, snap, batching | `references/scrolltrigger.md` |
| Flip, Draggable, SplitText, MorphSVG, DrawSVG, MotionPath and the rest of the plugin family | `references/plugins.md` |
| Helpers — `clamp`, `mapRange`, `interpolate`, `snap`, `random` | `references/utils.md` |
| Vue, Nuxt or Svelte wiring — lifecycle-framework cleanup contracts | `references/frameworks.md` |
| React — `useGSAP`, scoping, SSR/Next.js | `references/react.md` |
| Review bar before shipping: what to measure, what always janks | `references/performance.md` |

Two rules that survive every module:

1. **Cleanup is not optional.** Every tween/trigger created in a
   component is killed on unmount — `gsap.context()` or `useGSAP` scope
   handles it; a bare `gsap.to` in a framework component is a leak.
2. **`references/performance.md` is the review bar**, not optional
   reading: run its checklist on any GSAP work before the Quality Gate
   sees it.

## Output

The working animation code with cleanup wired, the module(s) actually
loaded named in one line, and the performance checklist result — plus,
when direction came from `brand/motion-design`, the mapping from its
choices (durations, easing families, choreography order) to the
implemented tweens.
