---
name: threejs
description: >
  Real-time 3D in the browser with three.js and React Three Fiber: modern
  setup (import maps, WebGL vs WebGPU renderer choice, TSL), the
  scene-camera-renderer wiring, geometries, materials and lights, loaders,
  disposal discipline against GPU memory leaks, performance budgets — and
  the R3F layer (hooks, drei, postprocessing) for React projects.
  TRIGGER: "three.js", "threejs", "react three fiber", "r3f", "webgl",
  "webgpu", "shader", "GLSL", "cena 3D", "3D interativo no browser",
  "drei", "/dev threejs".
  SKIP: a pre-rendered 3D world scrubbed by scroll (no real-time engine)
  -> dev/scroll-world; generative 2D canvas -> dev/canvas-generative;
  generating a 3D asset (GLB mesh) from an image -> the higgsfield-generate
  skill; React motion without 3D -> dev/framer-motion.
metadata:
  origin: community
  source: https://github.com/AThevon/genjutsu
  license: MIT
---

# Three.js

> **Agent:** Diana (Frontend Dev) | **Framework:** three.js (MIT) + React Three Fiber
> Core authored from the three.js project's own LLM guidance
> (`docs/llms.txt` in the three.js repo — not vendored here, MIT); the R3F
> layer derives from genjutsu (MIT) — see `references/`.

## Setup — the modern shape

Import maps, never legacy CDN script tags. Pin one version for `three`
and `three/addons/` together — mixing versions across the two specifiers
is the classic silent breaker:

```html
<script type="importmap">
{ "imports": {
    "three": "https://cdn.jsdelivr.net/npm/three@<version>/build/three.module.js",
    "three/webgpu": "https://cdn.jsdelivr.net/npm/three@<version>/build/three.webgpu.js",
    "three/tsl": "https://cdn.jsdelivr.net/npm/three@<version>/build/three.tsl.js",
    "three/addons/": "https://cdn.jsdelivr.net/npm/three@<version>/examples/jsm/" } }
</script>
```

`WebGPURenderer` is not exported from `three` — it lives in the
`three/webgpu` entry, and it is async: `await renderer.init()` before the
first frame. The TSL node functions live in `three/tsl`, not in
`three/webgpu`. Omit either entry and the import fails at runtime.

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
renderer.setAnimationLoop(tick);                        // not a hand-rolled rAF: in XR it swaps to the session's loop; outside XR it is rAF with correct teardown via setAnimationLoop(null)
```

On resize: update `camera.aspect`, call `camera.updateProjectionMatrix()`,
then `renderer.setSize`. Forgetting the middle step is why "resize
stretches everything".

**Animate with elapsed time, not the frame count.** A per-frame delta
keeps speed identical at 30 and 144 fps; per-frame increments do not.
Use `THREE.Timer` (`timer.update(); timer.getDelta()`) — `THREE.Clock`
is deprecated since r183 and warns at runtime.

## Disposal — GPU memory does not garbage-collect

Removing a mesh from the scene frees nothing on the GPU. Every geometry,
material, texture and render target you create, you `dispose()` when its
life ends — and a material's textures are disposed separately from the
material. For a whole subtree, collect first, dispose once: `traverse`
visits Groups and Lights that have no material, and shared resources must
not be disposed per-mesh:

```js
function disposeSubtree(root) {
  const geometries = new Set(), materials = new Set(), textures = new Set();
  root.traverse((obj) => {
    if (!obj.isMesh && !obj.isPoints && !obj.isLine && !obj.isSprite) return;
    // Sprites share one engine-owned quad geometry app-wide: never dispose it
    if (obj.geometry && !obj.isSprite) geometries.add(obj.geometry);
    const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
    for (const m of mats) {
      if (!m) continue;
      materials.add(m);
      for (const v of Object.values(m)) if (v?.isTexture) textures.add(v);
      // ShaderMaterial textures live in uniforms, not on the material —
      // and a uniform's value can be an ARRAY of textures (atlas shape)
      if (m.uniforms) for (const u of Object.values(m.uniforms)) {
        const vals = Array.isArray(u?.value) ? u.value : [u?.value];
        for (const v of vals) if (v?.isTexture) textures.add(v);
      }
    }
  });
  textures.forEach((t) => t.dispose());
  materials.forEach((m) => m.dispose());
  geometries.forEach((g) => g.dispose());
}
```

This covers the shapes meshes ordinarily carry — geometries, material
maps, scalar and array texture uniforms. When a resource is shared
with meshes OUTSIDE the subtree — a texture atlas, a cached material —
exclude it: ownership is yours to model, and dispose belongs to the owner.

A single-page app that mounts and unmounts scenes without this leaks
until the tab dies. This is the number-one three.js production bug.

## Performance budget

- **Draw calls first.** Hundreds of meshes sharing one geometry+material
  belong in an `InstancedMesh`; thousands of distinct static meshes merge
  via `BufferGeometryUtils.mergeGeometries`.
- Reuse geometries and materials across meshes; clone only when a
  property must diverge.
- Textures: compressed formats (KTX2/Basis) for anything big, and never
  larger than the screen area they cover; mipmaps come from the loader or
  `generateMipmaps`, with no power-of-two constraint in WebGL 2.
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
hooks discipline, drei picks, postprocessing, and the Do-Nots (from
setState in useFrame to forgotten dispose) — lives
in [references/r3f.md](references/r3f.md), with canvas/scene wiring in
[references/scene-setup.md](references/scene-setup.md) and GLSL/TSL
patterns in [references/shaders.md](references/shaders.md).

## Output

A working scene module (or R3F component tree) with the render loop,
resize handling and disposal wired, a stated performance budget (draw
calls, texture memory, DPR cap), and the renderer choice justified in one
line. Anything WebGPU/TSL states its fallback.
