<div align="center">

# GARGANTUA

**A relativistic black hole, raymarched in real time in your browser.**

### [▶  LAUNCH THE SIMULATION](https://hasnain7abbas.github.io/gargantua-blackhole/)

<sub>No install, no build step, no sign-in — it's one HTML file.</sub>

<br>

[![Launch](https://img.shields.io/badge/▶%20launch-live%20demo-ffb35c?style=for-the-badge&labelColor=0a0e16)](https://hasnain7abbas.github.io/gargantua-blackhole/)
[![WebGL2](https://img.shields.io/badge/render-WebGL2-7ad7ff?style=for-the-badge&labelColor=0a0e16)](#requirements)
[![three.js](https://img.shields.io/badge/three.js-r128-ffffff?style=for-the-badge&labelColor=0a0e16)](https://threejs.org)

<br>

[![GARGANTUA — lensed accretion disk around a spinning black hole](docs/preview.png)](https://hasnain7abbas.github.io/gargantua-blackhole/)

<sub>Actual output — 1280×720, default settings, no retouching.</sub>

</div>

---

## What you're looking at

Light doesn't travel in straight lines near a black hole, so you can't rasterize this — every pixel is a photon whose path has to be integrated through curved spacetime. That's what the shader does. The band arcing *over* the shadow is the far side of the accretion disk, bent up and around the event horizon; the band underneath is that same disk seen through the other side of the lens.

The left side is brighter than the right because the disk material there is rotating toward you at a large fraction of *c* — relativistic Doppler beaming, the effect that makes the *Interstellar* Gargantua lopsided.

## Try this first

Open the demo and drag the **Spin** slider from `0` to `0.98`. The photon ring tightens and the disk's inner edge falls inward as the ISCO moves closer to the horizon. Then run **Disk Temp** from cool to hot and watch the blackbody ramp go red → orange → blue-white.

| Input | Action |
| :-- | :-- |
| **Drag** | Orbit the camera |
| **Scroll** | Zoom in / out |
| **`H`** | Hide the UI (good for screenshots) |
| *idle* | Camera drifts into a slow cinematic orbit |

## What's in the renderer

**Geodesic lensing.** Photon paths are integrated per-ray in the fragment shader — Schwarzschild light bending plus a frame-dragging term scaled by spin. Background stars smear around the shadow; the disk wraps over and under it.

**Volumetric accretion disk.** Raymarched with 3D simplex-noise fbm for turbulence and dust lanes, Keplerian differential rotation, relativistic Doppler beaming, gravitational redshift, and a blackbody colour ramp.

**Cinematic post stack.** Bright-pass → multi-scale gaussian bloom → anamorphic streak → composite with gravity-centred chromatic aberration, lens-flare ghosts, ACES tonemapping, vignette and film grain.

**Live physics HUD.** Sliders for mass, spin (a/M), disk temperature and bloom, with derived readouts — Schwarzschild radius, ISCO orbit, plasma temperature, time dilation factor — recomputed as you drag.

**Adaptive quality.** Frame cost is smoothed and the renderer trades render scale and march steps (280 → 150) against framerate, with hysteresis so it doesn't oscillate.

## Requirements

A **WebGL2** browser with hardware acceleration enabled — current Chrome, Edge, Firefox, or Safari 15+. The scene pass is a GLSL3 shader, so WebGL1 won't do. If your browser can't run it, you get a readable message rather than a black screen.

It's a heavy fragment shader. Integrated graphics will run it at a lower internal resolution — that's the quality ladder doing its job. Discrete GPUs hold 60fps at full scale.

## Running it locally

```bash
git clone https://github.com/hasnain7abbas/gargantua-blackhole.git
cd gargantua-blackhole
npx serve .
```

Then open the URL it prints. Opening `index.html` straight off the filesystem works too — there are no module imports or fetches to trip CORS. Three.js is pulled from a CDN at runtime, so the first load needs a connection.

## How it's built

Everything lives in `index.html`. The geodesic raymarch runs as a GLSL3 full-screen pass into a half-float render target, followed by a chain of GLSL1 post passes.

One deliberate oddity: the march loop uses a *uniform* bound (`uSteps`) rather than a constant. A constant bound gets aggressively unrolled by ANGLE/D3D and compile time goes through the roof — a uniform keeps the loop rolled.

## Licence

MIT.
