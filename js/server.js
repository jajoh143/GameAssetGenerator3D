/**
 * Express server replacing frontend/app.py
 * Serves the character builder UI and handles generation jobs.
 */

import express from 'express';
import { randomUUID } from 'crypto';
import { mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { resolveConfig } from './src/presets.js';
import { buildHumanoid, buildRiggedFromGLB, exportGLB } from './src/builder.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = join(__dirname, '..');
const PREVIEW_DIR = join(PROJECT_ROOT, 'assets', 'previews');
const OUTPUT_DIR = join(PROJECT_ROOT, 'assets');
mkdirSync(PREVIEW_DIR, { recursive: true });

const app = express();
app.use(express.json());
app.use(express.static(join(__dirname, 'public')));

const jobs = new Map();

async function runJob(jobId, cfgFn, outputPath) {
  jobs.set(jobId, { status: 'running', log: [], output: outputPath });
  const log = [];
  try {
    const cfg = cfgFn();
    log.push(`[job] Building humanoid: ${JSON.stringify({ skinTone: cfg.skinTone, hairStyle: cfg.hairStyle })}`);
    const { scene, engine } = await buildHumanoid(cfg);
    await exportGLB(scene, engine, outputPath);
    log.push(`[job] Done: ${outputPath}`);
    jobs.set(jobId, { status: 'done', log, output: outputPath });
  } catch (err) {
    log.push(`ERROR: ${err.message}`, err.stack ?? '');
    jobs.set(jobId, { status: 'error', log, output: null });
  }
}

function cfgFromBody(data, animations = 'all') {
  const top    = data.clothing_top    ?? 'none';
  const bottom = data.clothing_bottom ?? 'none';
  const clothing = [top, bottom].filter(c => c && c !== 'none');

  const clothingColor = {};
  if (data.top_color    && top    !== 'none') clothingColor[top]    = data.top_color;
  if (data.bottom_color && bottom !== 'none') clothingColor[bottom] = data.bottom_color;

  const buttons   = data.buttons === 'true' || data.buttons === '1' || data.buttons === true;
  const belt      = data.belt    === 'true' || data.belt    === '1' || data.belt    === true;
  const beltColor = data.belt_color ?? 'brown';

  const cfg = resolveConfig({
    preset:       data.preset       ?? 'average',
    build:        data.build        ?? 'average',
    gender:       data.gender       ?? 'neutral',
    skinTone:     data.skin_tone    ?? 'tan',
    hairStyle:    data.hair_style   ?? 'short',
    hairColor:    data.hair_color   ?? 'brown',
    clothing,
    clothingColor,
    buttons,
    animations,
    lod:          data.lod          ?? 'mid',
  });

  cfg.belt      = belt;
  cfg.beltColor = beltColor;

  const ft = (val, def) => { const n = parseFloat(val); return isNaN(n) ? def : n; };
  cfg.faceTweaks = {
    hairY:     ft(data.face_hair_y,     0.05),
    eyeHeight: ft(data.face_eye_height, 0.20),
    eyeSpread: ft(data.face_eye_spread, 0.45),
    eyeRx:     ft(data.face_eye_rx,     0.10),
    eyeRy:     ft(data.face_eye_ry,     0.08),
    mouthY:    ft(data.face_mouth_y,   -0.10),
  };

  return cfg;
}

// ── GLB import-rig endpoint ───────────────────────────────────────────────────
// Accepts a raw GLB binary body (Content-Type: application/octet-stream).
// Optional query params:
//   animations  comma-separated list, e.g. "idle,walk,run"  (default: all five)
//   height      target height in metres                       (default: 1.75)
app.post('/import-rig',
  express.raw({ type: '*/*', limit: '100mb' }),
  (req, res) => {
    const glbBuffer = req.body;
    if (!glbBuffer || !glbBuffer.length) {
      return res.status(400).json({ error: 'No GLB data received.' });
    }

    const animParam = req.query.animations;
    const animations = animParam
      ? animParam.split(',').map(s => s.trim()).filter(Boolean)
      : 'all';
    const height = parseFloat(req.query.height) || 1.75;

    const jobId      = randomUUID();
    const outputPath = join(OUTPUT_DIR, `imported_${jobId.slice(0, 8)}.glb`);
    jobs.set(jobId, { status: 'queued', log: [], output: outputPath });

    // Run async, respond immediately with job ID
    (async () => {
      const log = [];
      try {
        jobs.set(jobId, { status: 'running', log, output: outputPath });
        log.push(`[import] Rigging imported GLB (${glbBuffer.length} bytes, height=${height}m)`);
        log.push(`[import] Animations: ${JSON.stringify(animations)}`);
        const { scene, engine } = await buildRiggedFromGLB(glbBuffer, { height, animations });
        await exportGLB(scene, engine, outputPath);
        log.push(`[import] Done: ${outputPath}`);
        jobs.set(jobId, { status: 'done', log, output: outputPath });
      } catch (err) {
        log.push(`ERROR: ${err.message}`, err.stack ?? '');
        jobs.set(jobId, { status: 'error', log, output: null });
      }
    })();

    res.json({ job_id: jobId });
  }
);

app.post('/preview', (req, res) => {
  const jobId = randomUUID();
  const outputPath = join(PREVIEW_DIR, `${jobId}.glb`);
  jobs.set(jobId, { status: 'queued', log: [], output: outputPath });
  runJob(jobId, () => cfgFromBody(req.body, []), outputPath);
  res.json({ job_id: jobId });
});

app.post('/generate', (req, res) => {
  const jobId = randomUUID();
  const outputPath = join(OUTPUT_DIR, `humanoid_${jobId.slice(0, 8)}.glb`);
  jobs.set(jobId, { status: 'queued', log: [], output: outputPath });
  runJob(jobId, () => cfgFromBody(req.body, 'all'), outputPath);
  res.json({ job_id: jobId });
});

app.get('/job/:id', (req, res) => {
  const job = jobs.get(req.params.id);
  if (!job) return res.status(404).json({ error: 'not found' });
  const result = { ...job };
  if (result.status === 'done') result.download_url = `/download/${req.params.id}`;
  res.json(result);
});

app.get('/model/:id', (req, res) => {
  const job = jobs.get(req.params.id);
  if (!job?.output) return res.status(404).send('Not found');
  res.type('model/gltf-binary').sendFile(job.output);
});

app.get('/download/:id', (req, res) => {
  const job = jobs.get(req.params.id);
  if (!job?.output) return res.status(404).send('Not found');
  res.download(job.output);
});

const PORT = process.env.PORT ?? 5000;
app.listen(PORT, () => console.log(`Character builder at http://localhost:${PORT}`));
