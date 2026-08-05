---
name: dev/threejs
description: >
  Real-time 3D in the browser with three.js and React Three Fiber: modern
  setup (import maps, WebGL vs WebGPU renderer choice, TSL), scene/camera/
  renderer wiring, geometries, materials and lights, model loading,
  disposal discipline against GPU memory leaks, performance budgets — and
  the R3F layer (hooks, drei, postprocessing) for React projects.
  TRIGGER: "three.js", "threejs", "react three fiber", "r3f", "webgl",
  "webgpu", "shader", "GLSL", "cena 3D", "3D interativo no browser",
  "drei", "/dev threejs".
  SKIP: a pre-rendered 3D world scrubbed by scroll (no real-time engine)
  -> dev/scroll-world; generative 2D canvas -> dev/canvas-generative;
  generating a 3D asset (GLB mesh) from an image -> the higgsfield-generate
  skill; React motion without 3D -> dev/framer-motion.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob]
metadata:
  origin: community
  source: https://github.com/AThevon/genjutsu
  license: MIT
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Three.js — `/dev threejs`

> **Agent:** Diana (Frontend Dev) | **Framework:** three.js (MIT) + React Three Fiber
> Core authored from the three.js project's own LLM guidance
> (`docs/llms.txt`, MIT); the R3F layer derives from genjutsu (MIT) — see
> `references/`.

## Setup — the modern shape

Import maps, never legacy CDN script tags. Pin one version for `three`
and `three/addons/` together — mixing versions across the two specifiers
is the classic silent breaker:

```html
<script type="importmap">
{ "imports": {
    "three": "https://cdn.jsdelivr.net/npm/three@<version>/build/three.module.js",
    "three/addons/": "https://cdn.jsdelivr.net/npm/three@<version>/examples/jsm/" } }
</script>
```

In a bundled project, `npm i three` and import the same specifiers. Check
the installed version before writing code — the API moves, and the
project's lockfile outranks your memory of it.

**Renderer choice.** `WebGLRenderer` is the default and safe everywhere.
`WebGPURenderer` (with TSL node materials) is the forward path but needs
feature detection and a WebGL fallback; choose it only when the project
targets browsers you control or ships the fallback. Never mix GLSL
`ShaderMaterial` into a WebGPU pipeline — that renderer wants TSL
`NodeMaterial` classes.

## The irreducible core

Scene, camera, renderer, loop — everything else hangs off these:

```js
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, w / h, 0.1, 100);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(w, h);
renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); // cap DPR: 3x buys nothing visible and burns fill rate
renderer.setAnimationLoop(tick);                        // not a hand-rolled rAF: pauses correctly in XR and background tabs
```

On resize: update `camera.aspect`, call `camera.updateProjectionMatrix()`,
then `renderer.setSize`. Forgetting the middle step is why "resize
stretches everything".

**Animate with the clock, not the frame count.** `clock.getDelta()` keeps
speed identical at 30 and 144 fps; per-frame increments do not.

## Disposal — GPU memory does not garbage-collect

Removing a mesh from the scene frees nothing on the GPU. Every geometry,
material, texture and render target you create, you `dispose()` when its
life ends — and a material's textures are disposed separately from the
material. For a whole subtree:

```js
root.traverse((obj) => {
  obj.geometry?.dispose();
  const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
  mats.forEach((m) => {
    Object.values(m).forEach((v) => v?.isTexture && v.dispose());
    m?.dispose();
  });
});
```

A single-page app that mounts and unmounts scenes without this leaks
until the tab dies. This is the number-one three.js production bug.

## Performance budget

- **Draw calls first.** Hundreds of meshes sharing one geometry+material
  belong in an `InstancedMesh`; thousands of distinct static meshes merge
  via `BufferGeometryUtils.mergeGeometries`.
- Reuse geometries and materials across meshes; clone only when a
  property must diverge.
- Textures: power-of-two dimensions when mipmaps matter, compressed
  formats (KTX2/basis) for anything big, and never larger than the
  screen area they cover.
- Lights are per-fragment cost: prefer one directional + ambient or an
  environment map over a constellation of point lights. Bake what does
  not move.
- Shadows are a render pass per caster: tight `shadow.camera` frustum,
  modest map sizes, `castShadow` only where it is visible.

## Loading models

`GLTFLoader` (with `DRACOLoader` or `KTX2Loader` when the asset uses
them) from `three/addons/`. Load asynchronously, add a loading state,
and dispose the loader's intermediates. glTF is the format; converting
from anything else happens in the asset pipeline, not at runtime.

## React Three Fiber

For React projects, R3F replaces the imperative wiring: the component
tree IS the scene graph, `useFrame` is the loop, drei supplies the
controls/loaders/staging you would otherwise hand-write. The full layer —
hooks discipline, drei picks, postprocessing, and the three Do-Nots
(setState in useFrame, allocation in the loop, forgotten dispose) — lives
in [references/r3f.md](references/r3f.md), with canvas/scene wiring in
[references/scene-setup.md](references/scene-setup.md) and GLSL/TSL
patterns in [references/shaders.md](references/shaders.md).

## Output

A working scene module (or R3F component tree) with the render loop,
resize handling and disposal wired, a stated performance budget (draw
calls, texture memory, DPR cap), and the renderer choice justified in one
line. Anything WebGPU/TSL states its fallback.
