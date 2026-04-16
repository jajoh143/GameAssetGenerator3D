#!/usr/bin/env node
/**
 * CLI entry point for generating bar scene assets.
 *
 * Usage:
 *   node src/generate.js <asset> [--output path] [--variant name]
 *   node src/generate.js scene   [--output path]
 *   node src/generate.js all     [--outdir path]
 *
 * Examples:
 *   node src/generate.js brick_wall --output ../assets/bar/brick_wall.glb
 *   node src/generate.js bottles --variant whiskey
 *   node src/generate.js scene --output ../assets/bar/queer_bar.glb
 *   node src/generate.js all --outdir ../assets/bar
 */

import { resolve, join } from 'path';
import { createScene, disposeEngine } from './utils/engine.js';
import { exportGLB } from './utils/export.js';

// Asset module registry — each maps to a create(scene, options) function
import { create as createBrickWall } from './assets/brick_wall.js';
import { create as createBarCounter } from './assets/bar_counter.js';
import { create as createBottles } from './assets/bottles.js';
import { create as createCups } from './assets/cups.js';
import { create as createPridePosters } from './assets/pride_posters.js';
import { create as createLeatherHat } from './assets/leather_hat.js';
import { create as createAviatorSunglasses } from './assets/aviator_sunglasses.js';
import { create as createCashRegister } from './assets/cash_register.js';
import { create as createDoors } from './assets/doors.js';
import { create as createBathroom } from './assets/bathroom.js';
import { create as createBarScene } from './bar_scene.js';

const ASSETS = {
  brick_wall:          { create: createBrickWall,          defaultFile: 'brick_wall.glb' },
  bar_counter:         { create: createBarCounter,         defaultFile: 'bar_counter.glb' },
  bottles:             { create: createBottles,            defaultFile: 'bottles.glb' },
  cups:                { create: createCups,               defaultFile: 'cups.glb' },
  pride_posters:       { create: createPridePosters,       defaultFile: 'pride_posters.glb' },
  leather_hat:         { create: createLeatherHat,         defaultFile: 'leather_hat.glb' },
  aviator_sunglasses:  { create: createAviatorSunglasses,  defaultFile: 'aviator_sunglasses.glb' },
  cash_register:       { create: createCashRegister,       defaultFile: 'cash_register.glb' },
  doors:               { create: createDoors,              defaultFile: 'doors.glb' },
  bathroom:            { create: createBathroom,           defaultFile: 'bathroom.glb' },
  scene:               { create: createBarScene,           defaultFile: 'queer_bar.glb' },
};

function parseArgs(argv) {
  const args = argv.slice(2);
  const opts = { asset: null, output: null, variant: null, outdir: null };

  if (args.length === 0 || args[0] === '--help' || args[0] === '-h') {
    printUsage();
    process.exit(0);
  }

  opts.asset = args[0];

  for (let i = 1; i < args.length; i++) {
    if ((args[i] === '--output' || args[i] === '-o') && args[i + 1]) {
      opts.output = args[++i];
    } else if (args[i] === '--variant' && args[i + 1]) {
      opts.variant = args[++i];
    } else if (args[i] === '--outdir' && args[i + 1]) {
      opts.outdir = args[++i];
    }
  }

  return opts;
}

function printUsage() {
  console.log(`
Bar Asset Generator (Babylon.js)

Usage:
  node src/generate.js <asset> [--output path] [--variant name]
  node src/generate.js all     [--outdir path]

Assets:
  ${Object.keys(ASSETS).join('\n  ')}

Options:
  --output, -o   Output GLB file path
  --variant      Asset variant (asset-specific)
  --outdir       Output directory for 'all' command
  `.trim());
}

async function generateOne(assetName, output, variant) {
  const entry = ASSETS[assetName];
  if (!entry) {
    console.error(`Unknown asset: ${assetName}`);
    console.error(`Available: ${Object.keys(ASSETS).join(', ')}`);
    process.exit(1);
  }

  const outPath = resolve(output || join('..', 'assets', 'bar', entry.defaultFile));
  const { scene } = createScene();

  console.log(`[generate] Creating ${assetName}${variant ? ` (variant: ${variant})` : ''}...`);
  entry.create(scene, { variant });

  await exportGLB(scene, outPath, assetName);
  scene.dispose();
}

async function generateAll(outdir) {
  const dir = resolve(outdir || join('..', 'assets', 'bar'));
  for (const [name, entry] of Object.entries(ASSETS)) {
    if (name === 'scene') continue; // scene is separate
    const outPath = join(dir, entry.defaultFile);
    const { scene } = createScene();
    console.log(`[generate] Creating ${name}...`);
    entry.create(scene);
    await exportGLB(scene, outPath, name);
    scene.dispose();
  }
  // Also generate composed scene
  const { scene } = createScene();
  console.log('[generate] Creating composed bar scene...');
  createBarScene(scene);
  await exportGLB(scene, join(dir, 'queer_bar.glb'), 'scene');
  scene.dispose();
}

async function main() {
  const opts = parseArgs(process.argv);

  try {
    if (opts.asset === 'all') {
      await generateAll(opts.outdir);
    } else {
      await generateOne(opts.asset, opts.output, opts.variant);
    }
    console.log('[generate] Done!');
  } finally {
    disposeEngine();
  }
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
