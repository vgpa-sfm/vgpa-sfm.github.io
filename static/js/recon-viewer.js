/* Interactive viewer for the .vgpa reconstruction files.
 *
 * Progressive: the markup ships a poster image and an animated WebP, and this
 * module upgrades a slot to a real 3D view when the reader asks for one. If
 * three.js cannot be reached the slot keeps the WebP, which is why the loop
 * exists at all.
 *
 * Reads the format written by tools/export_web.py — see its docstring.
 */
/* three.js is pulled in only when a reader actually opens a viewer, so the
 * page costs nothing extra to load.  The paths are plain relative URLs, not
 * bare specifiers: that needs no import map, which Safari did not support
 * before 16.4, and no CDN. */
let THREE = null;
let OrbitControls = null;

async function loadThree() {
  if (THREE) return;
  const [three, orbit] = await Promise.all([
    import("../vendor/three/three.module.js"),
    import("../vendor/three/OrbitControls.js"),
  ]);
  THREE = three;
  OrbitControls = orbit.OrbitControls;
}

const ELEVATION = 12 * Math.PI / 180;   // matches the rendered orbit
const DISTANCE = 2.35;                  // ... and its framing
const FOV = 42;

function parseVGPA(buf) {
  const dv = new DataView(buf);
  const magic = String.fromCharCode(dv.getUint8(0), dv.getUint8(1),
                                    dv.getUint8(2), dv.getUint8(3));
  if (magic !== "VGPA") throw new Error("not a VGPA file");
  const version = dv.getUint32(4, true);
  if (version !== 1) throw new Error("unsupported VGPA version " + version);

  const nPts = dv.getUint32(8, true);
  const nCams = dv.getUint32(12, true);
  const f = (o) => dv.getFloat32(o, true);
  const lo = [f(16), f(20), f(24)];
  const step = [f(28), f(32), f(36)];
  const centre = [f(40), f(44), f(48)];
  const radius = f(52);
  const up = [f(56), f(60), f(64)];
  const az0 = f(68);
  const fscale = f(72);

  let o = 76;
  const q = new Uint16Array(buf, o, nPts * 3); o += nPts * 6;
  const rgb = new Uint8Array(buf, o, nPts * 3); o += nPts * 3;
  // camera block is float32 and may not be 4-byte aligned in the file
  const cams = new Float32Array(buf.slice(o, o + nCams * 48));

  // Dequantise about the framing centre: the viewer orbits the origin, and
  // keeping coordinates small keeps float32 precision where the model is.
  const pos = new Float32Array(nPts * 3);
  for (let i = 0; i < nPts; i++) {
    for (let k = 0; k < 3; k++) {
      pos[i * 3 + k] = lo[k] + q[i * 3 + k] * step[k] - centre[k];
    }
  }
  const col = new Float32Array(nPts * 3);
  for (let i = 0; i < col.length; i++) col[i] = rgb[i] / 255;

  return { nPts, nCams, pos, col, cams, centre, radius, up, az0, fscale };
}

function frustaGeometry(s) {
  const d = s.fscale, w = d * 0.6 * 1.5, h = d * 0.6;
  const corner = [[-w, -h, d], [w, -h, d], [w, h, d], [-w, h, d]];
  const edges = [[0, 1], [0, 2], [0, 3], [0, 4],
                 [1, 2], [2, 3], [3, 4], [4, 1]];
  const out = new Float32Array(s.nCams * edges.length * 6);
  const v = new Array(5);
  let n = 0;
  for (let c = 0; c < s.nCams; c++) {
    const b = c * 12;
    const cen = [s.cams[b + 9] - s.centre[0], s.cams[b + 10] - s.centre[1],
                 s.cams[b + 11] - s.centre[2]];
    v[0] = cen;
    for (let k = 0; k < 4; k++) {
      const p = corner[k];
      // rows of the world-to-camera rotation are the camera axes in world
      v[k + 1] = [
        cen[0] + p[0] * s.cams[b + 0] + p[1] * s.cams[b + 3] + p[2] * s.cams[b + 6],
        cen[1] + p[0] * s.cams[b + 1] + p[1] * s.cams[b + 4] + p[2] * s.cams[b + 7],
        cen[2] + p[0] * s.cams[b + 2] + p[1] * s.cams[b + 5] + p[2] * s.cams[b + 8]];
    }
    for (const [a, z] of edges) {
      out[n++] = v[a][0]; out[n++] = v[a][1]; out[n++] = v[a][2];
      out[n++] = v[z][0]; out[n++] = v[z][1]; out[n++] = v[z][2];
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(out, 3));
  return g;
}

function cssVar(name, fallback) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name);
  return v && v.trim() ? v.trim() : fallback;
}

export async function mountViewer(container, url, opts = {}) {
  await loadThree();
  const scene = new THREE.Scene();
  const bg = new THREE.Color(cssVar("--figure-bg", "#ffffff"));
  scene.background = bg;

  const camera = new THREE.PerspectiveCamera(FOV, 1, 0.01, 5000);

  // Probe first: without this, a session with no WebGL (a remote desktop, a
  // locked-down browser) fails somewhere deep inside three.js instead of here.
  const probe = document.createElement("canvas");
  if (!(probe.getContext("webgl2") || probe.getContext("webgl"))) {
    throw new Error("this browser session has no WebGL");
  }
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  container.appendChild(renderer.domElement);
  renderer.domElement.style.display = "block";
  renderer.domElement.style.width = "100%";
  renderer.domElement.style.height = "100%";

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.autoRotate = opts.autoRotate !== false;
  controls.autoRotateSpeed = 0.9;

  let raf = 0, disposed = false, points = null, frusta = null;

  function resize() {
    const w = container.clientWidth || 1;
    const h = container.clientHeight || 1;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  const ro = new ResizeObserver(resize);
  ro.observe(container);

  const api = {
    setAutoRotate(v) { controls.autoRotate = v; },
    toggleCameras() {
      if (frusta) frusta.visible = !frusta.visible;
      return frusta ? frusta.visible : false;
    },
    reset() { controls.reset(); },
    dispose() {
      disposed = true;
      cancelAnimationFrame(raf);
      ro.disconnect();
      controls.dispose();
      scene.traverse((o) => {
        if (o.geometry) o.geometry.dispose();
        if (o.material) o.material.dispose();
      });
      renderer.dispose();
      if (renderer.domElement.parentNode) {
        renderer.domElement.parentNode.removeChild(renderer.domElement);
      }
    },
  };

  const ready = fetch(url).then((r) => {
    if (!r.ok) throw new Error("HTTP " + r.status + " for " + url);
    return r.arrayBuffer();
  }).then((buf) => {
    if (disposed) return api;
    const s = parseVGPA(buf);

    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(s.pos, 3));
    g.setAttribute("color", new THREE.BufferAttribute(s.col, 3));
    points = new THREE.Points(g, new THREE.PointsMaterial({
      size: s.radius * (opts.pointSize || 0.0035),
      vertexColors: true, sizeAttenuation: true,
    }));
    scene.add(points);

    frusta = new THREE.LineSegments(frustaGeometry(s), new THREE.LineBasicMaterial({
      color: new THREE.Color(cssVar("--accent", "#b8371f")),
      transparent: true, opacity: 0.55,
    }));
    scene.add(frusta);

    // Open on the view the collection was shot from, as the stills do.
    const up = new THREE.Vector3(...s.up).normalize();
    const fwd = new THREE.Vector3().crossVectors(
      up, new THREE.Vector3(s.up[1], s.up[2], s.up[0])).normalize();
    const side = new THREE.Vector3().crossVectors(up, fwd);
    const a = s.az0 * Math.PI / 180;
    const eye = fwd.clone().multiplyScalar(Math.cos(a) * Math.cos(ELEVATION))
      .add(side.clone().multiplyScalar(Math.sin(a) * Math.cos(ELEVATION)))
      .add(up.clone().multiplyScalar(Math.sin(ELEVATION)))
      .multiplyScalar(s.radius * DISTANCE);
    camera.up.copy(up);
    camera.position.copy(eye);
    camera.near = Math.max(s.radius * 0.002, 1e-3);
    camera.far = s.radius * 40;
    controls.target.set(0, 0, 0);
    controls.minDistance = s.radius * 0.15;
    controls.maxDistance = s.radius * 12;
    controls.saveState();
    resize();

    api.scene = s;
    // Start drawing on the next frame rather than here.  The first render
    // compiles shaders and uploads every buffer, which on a software renderer
    // takes seconds; doing it inside this promise left the button stuck on
    // "Loading..." for the whole of it with nothing on screen.
    raf = requestAnimationFrame(function loop() {
      if (disposed) return;
      raf = requestAnimationFrame(loop);
      controls.update();
      renderer.render(scene, camera);
    });
    return api;
  });

  api.ready = ready;
  return api;
}

/* ------------------------------------------------------------------ cards */
/* Wires up the reconstruction cards: each shows a still until the reader
 * presses the button, and only then does anything load. Nothing animates or
 * fetches on its own. */
export function initReconCards(root = document) {
  const cards = Array.from(root.querySelectorAll(".recon[data-key]"));
  if (!cards.length) return;

  for (const card of cards) {
    const stage = card.querySelector(".recon__stage");
    const button = card.querySelector(".recon__go");
    if (!stage || !button) continue;

    button.addEventListener("click", async () => {
      button.disabled = true;
      button.textContent = "Loading…";
      const holder = document.createElement("div");
      holder.className = "recon__canvas";
      stage.appendChild(holder);
      try {
        const viewer = await mountViewer(holder, card.dataset.src, {});
        holder.__viewer = viewer;
        let timer;
        await Promise.race([
          viewer.ready,
          new Promise((_, rej) => {
            timer = setTimeout(() => rej(new Error(
              "timed out after 20 s - the 3D context is probably being "
              + "rendered in software")), 20000);
          }),
        ]).finally(() => clearTimeout(timer));
        stage.classList.add("is-live");
        button.remove();
        stage.appendChild(buildControls(stage, viewer, card));
      } catch (err) {
        console.error("[vgpa] viewer failed for", card.dataset.src, err);
        if (holder.__viewer) holder.__viewer.dispose();
        holder.remove();
        button.disabled = false;
        button.textContent = "Explore in 3D";
        const old = stage.querySelector(".recon__error");
        if (old) old.remove();
        const msg = document.createElement("p");
        msg.className = "recon__error";
        msg.textContent = location.protocol === "file:"
          ? "The 3D viewer needs the page served over http:// — opened straight "
            + "from disk, the browser blocks it from reading " + card.dataset.src + "."
          : "Could not start the 3D viewer: " + err.message
            + " (" + card.dataset.src + ")";
        stage.appendChild(msg);
      }
    });
  }
}

function buildControls(stage, viewer, card) {
  const bar = document.createElement("div");
  bar.className = "recon__controls";
  const add = (label, fn) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    b.addEventListener("click", () => { const t = fn(); if (t) b.textContent = t; });
    bar.appendChild(b);
    return b;
  };
  let spinning = true;
  add("Pause", () => {
    spinning = !spinning;
    viewer.setAutoRotate(spinning);
    return spinning ? "Pause" : "Spin";
  });
  let cams = true;
  add("Hide cameras", () => {
    cams = viewer.toggleCameras();
    return cams ? "Hide cameras" : "Show cameras";
  });
  add("Reset", () => { viewer.reset(); return null; });
  add("Close", () => {
    viewer.dispose();
    stage.classList.remove("is-live");
    const holder = stage.querySelector(".recon__canvas");
    if (holder) holder.remove();
    bar.remove();
    const go = document.createElement("button");
    go.type = "button";
    go.className = "recon__go";
    go.textContent = "Explore in 3D";
    stage.appendChild(go);
    initReconCards(card.parentNode);
    return null;
  });
  return bar;
}
