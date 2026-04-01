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
import { buildHumanoid, exportGLB } from './src/builder.js';

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
    const { scene, clips } = await buildHumanoid(cfg);
    await exportGLB(scene, clips, outputPath);
    log.push(`[job] Done: ${outputPath}`);
    jobs.set(jobId, { status: 'done', log, output: outputPath });
  } catch (err) {
    log.push(`ERROR: ${err.message}`, err.stack ?? '');
    jobs.set(jobId, { status: 'error', log, output: null });
  }
}

function cfgFromBody(data, animations = 'all') {
  const top    = data.clothing_top    ?? 'short_sleeve';
  const bottom = data.clothing_bottom ?? 'jeans';
  const clothing = [top, bottom].filter(c => c && c !== 'none');

  const clothingColor = {};
  if (data.top_color    && top    !== 'none') clothingColor[top]    = data.top_color;
  if (data.bottom_color && bottom !== 'none') clothingColor[bottom] = data.bottom_color;

  return resolveConfig({
    preset:       data.preset       ?? 'average',
    build:        data.build        ?? 'average',
    gender:       data.gender       ?? 'neutral',
    skinTone:     data.skin_tone    ?? 'tan',
    hairStyle:    data.hair_style   ?? 'short',
    hairColor:    data.hair_color   ?? 'brown',
    clothing,
    clothingColor,
    animations,
    lod:          data.lod          ?? 'mid',
  });
}

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
