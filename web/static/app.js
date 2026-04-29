import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

// ─── Tab nav ─────────────────────────────────────────────────────────

const tabs = document.querySelectorAll("nav#tabs button");
const panes = document.querySelectorAll(".tab");
tabs.forEach(btn => {
  btn.addEventListener("click", () => {
    tabs.forEach(t => t.classList.toggle("active", t === btn));
    const target = btn.dataset.tab;
    panes.forEach(p => p.classList.toggle("active", p.id === `tab-${target}`));
    if (target === "library") refreshLibrary();
    if (target === "preview") viewer.onResize();
  });
});

// ─── Health ──────────────────────────────────────────────────────────

const healthEl = document.getElementById("health");
fetch("/api/health").then(r => r.json()).then(h => {
  const warns = [];
  if (!h.openai_configured) warns.push("OPENAI_API_KEY missing");
  if (!h.trellis2_configured) warns.push("TRELLIS2_PATH missing");
  if (warns.length) {
    healthEl.textContent = "⚠ " + warns.join(" · ");
    healthEl.classList.add("warn");
  } else {
    healthEl.textContent = "● ready";
    healthEl.classList.add("ok");
  }
});

// ─── Source toggle ───────────────────────────────────────────────────

document.querySelectorAll(".source-toggle button").forEach(btn => {
  btn.addEventListener("click", () => {
    const target = btn.dataset.source;
    document.querySelectorAll(".source-toggle button").forEach(b =>
      b.classList.toggle("active", b === btn));
    document.querySelectorAll(".source-pane").forEach(p =>
      p.classList.toggle("active", p.id === `source-${target}`));
  });
});

// Hide animations row for props.
const assetTypeSel = document.getElementById("asset_type");
const animRow = document.getElementById("anim-row");
assetTypeSel.addEventListener("change", () => {
  animRow.style.display = assetTypeSel.value === "humanoid" ? "" : "none";
});

// ─── Generate ────────────────────────────────────────────────────────

const form = document.getElementById("generate-form");
const generateBtn = document.getElementById("generate-btn");
const progress = document.getElementById("progress");
const jobIdEl = document.getElementById("job-id");
const jobStatusEl = document.getElementById("job-status");
const eventLog = document.getElementById("event-log");

form.addEventListener("submit", async ev => {
  ev.preventDefault();

  const fd = new FormData();
  fd.append("asset_type", form.asset_type.value);
  fd.append("resolution", form.resolution.value);
  fd.append("height", form.height.value);

  const activeSource = document.querySelector(".source-toggle button.active").dataset.source;
  if (activeSource === "prompt") {
    if (!form.prompt.value.trim()) {
      alert("Prompt is required.");
      return;
    }
    fd.append("prompt", form.prompt.value);
    if (form.style.value) fd.append("style", form.style.value);
  } else {
    if (!form.image.files[0]) {
      alert("Choose an image.");
      return;
    }
    fd.append("image", form.image.files[0]);
  }

  if (form.asset_type.value === "humanoid") {
    const anims = [...form.querySelectorAll("input[name=anim]:checked")].map(c => c.value);
    if (anims.length) fd.append("animations", anims.join(","));
  }

  generateBtn.disabled = true;
  progress.classList.remove("hidden");
  jobStatusEl.className = "";
  jobStatusEl.textContent = "submitting…";
  eventLog.innerHTML = "";

  try {
    const res = await fetch("/api/generate", { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    const { job_id } = await res.json();
    jobIdEl.textContent = job_id;
    streamJob(job_id);
  } catch (e) {
    jobStatusEl.textContent = "error";
    jobStatusEl.className = "error";
    eventLog.innerHTML = `<li class="stage-error">${e.message}</li>`;
    generateBtn.disabled = false;
  }
});

function streamJob(jobId) {
  jobStatusEl.textContent = "running";
  const es = new EventSource(`/api/jobs/${jobId}/events`);
  es.onmessage = ev => {
    const { stage, message } = JSON.parse(ev.data);
    const li = document.createElement("li");
    li.classList.add(`stage-${stage}`);
    li.innerHTML = `<span class="stage">${stage}</span> ${escapeHtml(message)}`;
    eventLog.appendChild(li);
    eventLog.scrollTop = eventLog.scrollHeight;

    if (stage === "complete") {
      jobStatusEl.textContent = "done";
      jobStatusEl.className = "done";
      generateBtn.disabled = false;
      es.close();
      // Auto-load into preview tab.
      loadJobIntoPreview(jobId);
    } else if (stage === "error") {
      jobStatusEl.textContent = "error";
      jobStatusEl.className = "error";
      generateBtn.disabled = false;
      es.close();
    }
  };
  es.onerror = () => {
    es.close();
    generateBtn.disabled = false;
  };
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

// ─── Preview viewer (three.js) ───────────────────────────────────────

class Viewer {
  constructor(container) {
    this.container = container;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x08090c);

    this.camera = new THREE.PerspectiveCamera(45, 1, 0.05, 100);
    this.camera.position.set(2.5, 1.7, 3.5);

    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.physicallyCorrectLights = true;
    container.appendChild(this.renderer.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.target.set(0, 0.9, 0);
    this.controls.update();

    // Lights
    this.scene.add(new THREE.HemisphereLight(0xa0b8d8, 0x141821, 0.6));
    const key = new THREE.DirectionalLight(0xffffff, 1.4);
    key.position.set(3, 5, 3);
    this.scene.add(key);
    const fill = new THREE.DirectionalLight(0xb0c8ff, 0.5);
    fill.position.set(-3, 2, -2);
    this.scene.add(fill);

    // Grid
    this.grid = new THREE.GridHelper(10, 20, 0x2a3142, 0x1d2230);
    this.scene.add(this.grid);

    this.loader = new GLTFLoader();
    this.mixer = null;
    this.actions = {};
    this.currentAction = null;
    this.skeletonHelpers = [];
    this.model = null;
    this.clock = new THREE.Clock();

    window.addEventListener("resize", () => this.onResize());
    this.onResize();
    this.animate();
  }

  onResize() {
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;
    if (w === 0 || h === 0) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  setGridVisible(v) { this.grid.visible = v; }

  setSkeletonVisible(v) {
    this.skeletonHelpers.forEach(h => h.visible = v);
  }

  speed = 1;
  setSpeed(v) {
    this.speed = v;
    if (this.mixer) this.mixer.timeScale = v;
  }

  play() { if (this.currentAction) { this.currentAction.paused = false; this.currentAction.play(); } }
  pause() { if (this.currentAction) this.currentAction.paused = true; }

  selectAnimation(name) {
    if (!this.actions[name]) return;
    if (this.currentAction) this.currentAction.fadeOut(0.2);
    const next = this.actions[name];
    next.reset().fadeIn(0.2).play();
    next.paused = false;
    this.currentAction = next;
  }

  clear() {
    if (this.model) {
      this.scene.remove(this.model);
      this.model = null;
    }
    this.skeletonHelpers.forEach(h => this.scene.remove(h));
    this.skeletonHelpers = [];
    this.mixer = null;
    this.actions = {};
    this.currentAction = null;
  }

  async loadGLB(url) {
    this.clear();
    const gltf = await this.loader.loadAsync(url);
    this.model = gltf.scene;
    this.scene.add(this.model);

    this.model.traverse(o => {
      if (o.isSkinnedMesh && o.skeleton) {
        const helper = new THREE.SkeletonHelper(o);
        helper.visible = document.getElementById("show-skeleton").checked;
        this.scene.add(helper);
        this.skeletonHelpers.push(helper);
      }
    });

    this.fitCamera();

    if (gltf.animations && gltf.animations.length) {
      this.mixer = new THREE.AnimationMixer(this.model);
      this.mixer.timeScale = this.speed;
      gltf.animations.forEach(clip => {
        this.actions[clip.name] = this.mixer.clipAction(clip);
      });
    }
    return gltf.animations.map(a => a.name);
  }

  fitCamera() {
    const box = new THREE.Box3().setFromObject(this.model);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);
    const dist = maxDim * 1.8;
    this.camera.position.set(center.x + dist * 0.6, center.y + dist * 0.5, center.z + dist);
    this.controls.target.copy(center);
    this.controls.update();
  }

  animate() {
    requestAnimationFrame(() => this.animate());
    const dt = this.clock.getDelta();
    if (this.mixer) this.mixer.update(dt);
    this.renderer.render(this.scene, this.camera);
  }
}

const viewer = new Viewer(document.getElementById("viewer"));

const animSelect = document.getElementById("anim-select");
const animPlay = document.getElementById("anim-play");
const animPause = document.getElementById("anim-pause");
const animSpeed = document.getElementById("anim-speed");
const speedReadout = document.getElementById("speed-readout");
const showSkeleton = document.getElementById("show-skeleton");
const showGrid = document.getElementById("show-grid");
const loadedInfo = document.getElementById("loaded-info");

animSelect.addEventListener("change", () => viewer.selectAnimation(animSelect.value));
animPlay.addEventListener("click", () => viewer.play());
animPause.addEventListener("click", () => viewer.pause());
animSpeed.addEventListener("input", () => {
  const v = parseFloat(animSpeed.value);
  viewer.setSpeed(v);
  speedReadout.textContent = `${v.toFixed(2)}×`;
});
showSkeleton.addEventListener("change", () => viewer.setSkeletonVisible(showSkeleton.checked));
showGrid.addEventListener("change", () => viewer.setGridVisible(showGrid.checked));

async function loadJobIntoPreview(jobId) {
  const url = `/api/files/${jobId}/final.glb`;
  loadedInfo.textContent = `Loading ${jobId}…`;
  try {
    const animNames = await viewer.loadGLB(url);
    animSelect.innerHTML = "";
    if (animNames.length === 0) {
      animSelect.innerHTML = "<option>(no animations)</option>";
      animSelect.disabled = true;
      animPlay.disabled = animPause.disabled = animSpeed.disabled = true;
    } else {
      animNames.forEach(n => {
        const opt = document.createElement("option");
        opt.value = opt.textContent = n;
        animSelect.appendChild(opt);
      });
      animSelect.disabled = false;
      animPlay.disabled = animPause.disabled = animSpeed.disabled = false;
      viewer.selectAnimation(animNames[0]);
    }
    loadedInfo.textContent = `${jobId} · ${animNames.length} animation${animNames.length === 1 ? "" : "s"}`;

    // Switch to preview tab.
    document.querySelector('nav#tabs button[data-tab="preview"]').click();
  } catch (e) {
    loadedInfo.textContent = `Failed: ${e.message}`;
  }
}

// ─── Library ─────────────────────────────────────────────────────────

const grid = document.getElementById("library-grid");
const libraryCount = document.getElementById("library-count");
document.getElementById("library-refresh").addEventListener("click", refreshLibrary);

async function refreshLibrary() {
  grid.innerHTML = "";
  const res = await fetch("/api/library");
  const { items } = await res.json();
  libraryCount.textContent = `${items.length} item${items.length === 1 ? "" : "s"}`;
  items.forEach(item => {
    const card = document.createElement("div");
    card.className = "card";
    const thumb = document.createElement("div");
    thumb.className = "thumb";
    if (item.image_url) thumb.style.backgroundImage = `url(${item.image_url})`;
    const info = document.createElement("div");
    info.className = "info";
    const title = item.meta?.prompt
      ? item.meta.prompt.slice(0, 50) + (item.meta.prompt.length > 50 ? "…" : "")
      : item.id;
    const sub = `${item.meta?.asset_type || "?"} · ${item.meta?.resolution || "?"}³`;
    info.innerHTML = `<div class="title">${escapeHtml(title)}</div><div class="meta">${sub}</div>`;
    card.append(thumb, info);
    card.addEventListener("click", () => loadJobIntoPreview(item.id));
    grid.appendChild(card);
  });
}

refreshLibrary();
