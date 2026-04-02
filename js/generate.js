#!/usr/bin/env node
/**
 * CLI entry point: node js/generate.js --output foo.glb [options]
 */

import { parseArgs } from 'node:util';
import { resolveConfig } from './src/presets.js';
import { buildHumanoid, exportGLB } from './src/builder.js';

const { values } = parseArgs({
  options: {
    output:        { type: 'string',  short: 'o', default: 'assets/humanoid.glb' },
    preset:        { type: 'string',  default: 'average' },
    build:         { type: 'string',  default: 'average' },
    gender:        { type: 'string',  default: 'neutral' },
    'skin-tone':   { type: 'string',  default: 'tan' },
    'hair-style':  { type: 'string',  default: 'short' },
    'hair-color':  { type: 'string',  default: 'brown' },
    clothing:      { type: 'string',  default: 'short_sleeve,jeans' },
    animations:    { type: 'string',  default: 'all' },
    lod:           { type: 'string',  default: 'mid' },
  },
  allowPositionals: true,
});

const cfg = resolveConfig({
  preset:       values.preset,
  build:        values.build,
  gender:       values.gender,
  skinTone:     values['skin-tone'],
  hairStyle:    values['hair-style'],
  hairColor:    values['hair-color'],
  clothing:     values.clothing.split(',').filter(Boolean),
  animations:   values.animations === 'all' ? 'all' : values.animations.split(','),
  lod:          values.lod,
});

const { scene, clips } = await buildHumanoid(cfg);
await exportGLB(scene, clips, values.output);
