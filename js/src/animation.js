/**
 * Animation keyframe builders.
 * Port of generators/humanoid/gltf_pipeline/anim_data.py
 */

import * as THREE from 'three';

// ── Animation parameters (same as Python ANIM_PARAMS) ─────────────────────────

const ANIM_PARAMS = {
  idle: {
    cycle_frames: 48,
    fps: 24,
    breath_chest: 1.5,
    breath_spine: 1.0,
    head_look: 2,
    hip_shift: 1.0,
    arm_breath: 0.8,
    shoulder_breath: 0.5,
  },
  walk: {
    cycle_frames: 24,
    fps: 24,
    upper_leg_swing: 30,
    lower_leg_bend: 40,
    foot_rock: 15,
    upper_arm_swing: 20,
    lower_arm_bend: 25,
    spine_twist: 3,
    spine_lean: 4,
    hip_bob: 0.02,
    hip_sway: 2,
  },
  run: {
    cycle_frames: 16,
    fps: 24,
    upper_leg_swing: 50,
    lower_leg_bend: 70,
    foot_rock: 20,
    upper_arm_swing: 40,
    lower_arm_bend: 55,
    spine_lean: 8,
    spine_twist: 5,
    hip_bob: 0.04,
    hip_sway: 3,
  },
  jump: {
    total_frames: 32,
    fps: 24,
    crouch_end: 8,
    launch_end: 12,
    apex: 20,
    land_end: 28,
    crouch_legs: 60,
    crouch_spine: -15,
    launch_legs: -20,
    launch_spine: 10,
    tuck_legs: 30,
    arm_raise: -40,
    land_absorb: 45,
    hip_height: 0.15,
  },
  attack: {
    total_frames: 20,
    fps: 24,
    windup_end: 6,
    strike_end: 10,
    follow_end: 14,
    windup_arm: -80,
    windup_forearm: -90,
    strike_arm: 60,
    strike_forearm: -20,
    torso_twist: 25,
    lunge_leg: 20,
    rear_leg: -15,
  },
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function eulerToQuat(xDeg, yDeg = 0, zDeg = 0) {
  const q = new THREE.Quaternion();
  q.setFromEuler(new THREE.Euler(
    THREE.MathUtils.degToRad(xDeg),
    THREE.MathUtils.degToRad(yDeg),
    THREE.MathUtils.degToRad(zDeg),
    'XYZ'
  ));
  return q;
}

// Helper: (time, bone, [rx,ry,rz]) rotation keyframe
function _rot(bone, frame, fps, rx = 0, ry = 0, rz = 0) {
  return [frame / fps, bone, [rx, ry, rz]];
}

// Helper: (time, bone, [x,y,z]) translation keyframe
function _trans(bone, frame, fps, x, y, z) {
  return [frame / fps, bone, [x, y, z]];
}

// Convert list of (time, boneName, euler-xyz-degrees) to QuaternionKeyframeTrack per bone
function buildRotTracks(rotKfs) {
  const byBone = new Map();
  for (const [t, bone, [rx, ry, rz]] of rotKfs) {
    if (!byBone.has(bone)) byBone.set(bone, []);
    byBone.get(bone).push({ t, q: eulerToQuat(rx, ry, rz) });
  }
  const tracks = [];
  for (const [bone, kfs] of byBone) {
    kfs.sort((a, b) => a.t - b.t);
    const times = kfs.map(k => k.t);
    const values = kfs.flatMap(k => [k.q.x, k.q.y, k.q.z, k.q.w]);
    tracks.push(new THREE.QuaternionKeyframeTrack(`${bone}.quaternion`, times, values));
  }
  return tracks;
}

function buildTransTracks(transKfs) {
  const byBone = new Map();
  for (const [t, bone, [x, y, z]] of transKfs) {
    if (!byBone.has(bone)) byBone.set(bone, []);
    byBone.get(bone).push({ t, x, y, z });
  }
  const tracks = [];
  for (const [bone, kfs] of byBone) {
    kfs.sort((a, b) => a.t - b.t);
    const times = kfs.map(k => k.t);
    const values = kfs.flatMap(k => [k.x, k.y, k.z]);
    tracks.push(new THREE.VectorKeyframeTrack(`${bone}.position`, times, values));
  }
  return tracks;
}

// ── Idle animation ─────────────────────────────────────────────────────────────

function idleKfs(_cfg) {
  const p = ANIM_PARAMS.idle;
  const f = p.cycle_frames;
  const fps = p.fps;
  const q = f / 4;

  const bc = p.breath_chest;
  const bs = p.breath_spine;
  const hl = p.head_look;
  const hs = p.hip_shift;
  const ab = p.arm_breath;
  const sb = p.shoulder_breath;

  const rotKfs = [];
  const transKfs = [];

  // Chest breathing
  for (const [frame, chestAngle, spineAngle] of [
    [0,     0,          0],
    [q,     bc,         bs],
    [q * 2, 0,          0],
    [q * 3, bc * 0.7,   bs * 0.7],
    [f,     0,          0],
  ]) {
    rotKfs.push(_rot('Chest', frame, fps, -chestAngle));
    rotKfs.push(_rot('Spine', frame, fps, -spineAngle));
  }

  // Head look left/right
  for (const [frame, angle] of [
    [0, 0], [q, hl], [q * 2, 0], [q * 3, -hl], [f, 0],
  ]) {
    rotKfs.push(_rot('Head', frame, fps, 0, 0, angle));
  }

  // Hip sway (Z rotation)
  for (const [frame, sway] of [
    [0, 0], [q, hs], [q * 2, 0], [q * 3, -hs], [f, 0],
  ]) {
    rotKfs.push(_rot('Hips', frame, fps, 0, 0, sway));
  }

  // Arm breathing
  for (const side of ['L', 'R']) {
    for (const [frame, angle] of [
      [0, 0], [q, ab], [q * 2, 0], [q * 3, ab * 0.7], [f, 0],
    ]) {
      rotKfs.push(_rot(`UpperArm.${side}`, frame, fps, angle));
    }
    for (const [frame, angle] of [
      [0, 0], [q, -sb], [q * 2, 0], [q * 3, -sb * 0.7], [f, 0],
    ]) {
      rotKfs.push(_rot(`Shoulder.${side}`, frame, fps, angle));
    }
  }

  return { rotKfs, transKfs };
}

// ── Walk animation ─────────────────────────────────────────────────────────────

function walkKfs(_cfg) {
  const wp = ANIM_PARAMS.walk;
  const frames = wp.cycle_frames;
  const fps = wp.fps;
  const half = frames / 2;
  const hh = half / 2;

  const uls = wp.upper_leg_swing;
  const llb = wp.lower_leg_bend;
  const fr = wp.foot_rock;
  const uas = wp.upper_arm_swing;
  const lab = wp.lower_arm_bend;

  const rotKfs = [];
  const transKfs = [];

  const leftLegData = [
    [0,          uls,         -llb * 0.3,  -fr],
    [hh,         0,           -llb,          0],
    [half,      -uls,         -llb * 0.1,   fr],
    [half + hh,  0,           -llb * 0.6,   0],
    [frames,     uls,         -llb * 0.3,  -fr],
  ];
  const rightLegData = [
    [0,         -uls,         -llb * 0.1,   fr],
    [hh,         0,           -llb * 0.6,   0],
    [half,       uls,         -llb * 0.3,  -fr],
    [half + hh,  0,           -llb,          0],
    [frames,    -uls,         -llb * 0.1,   fr],
  ];

  for (const [data, side] of [[leftLegData, 'L'], [rightLegData, 'R']]) {
    for (const [frame, ulA, llA, ftA] of data) {
      rotKfs.push(_rot(`UpperLeg.${side}`, frame, fps, ulA));
      rotKfs.push(_rot(`LowerLeg.${side}`, frame, fps, llA));
      rotKfs.push(_rot(`Foot.${side}`, frame, fps, ftA));
    }
  }

  const leftArmData = [
    [0,          -uas, -lab * 0.2],
    [hh,          0,   -lab * 0.1],
    [half,        uas, -lab],
    [half + hh,   0,   -lab * 0.1],
    [frames,     -uas, -lab * 0.2],
  ];
  const rightArmData = [
    [0,           uas, -lab],
    [hh,          0,   -lab * 0.1],
    [half,       -uas, -lab * 0.2],
    [half + hh,   0,   -lab * 0.1],
    [frames,      uas, -lab],
  ];

  for (const [data, side] of [[leftArmData, 'L'], [rightArmData, 'R']]) {
    for (const [frame, uaA, laA] of data) {
      rotKfs.push(_rot(`UpperArm.${side}`, frame, fps, uaA));
      rotKfs.push(_rot(`LowerArm.${side}`, frame, fps, laA));
    }
  }

  const bob = wp.hip_bob;
  const sway = wp.hip_sway;
  for (const [frame, b, s] of [
    [0,          0,    -sway],
    [hh,         bob,   0],
    [half,       0,     sway],
    [half + hh,  bob,   0],
    [frames,     0,    -sway],
  ]) {
    transKfs.push(_trans('Hips', frame, fps, 0, 0, b));
    rotKfs.push(_rot('Hips', frame, fps, 0, 0, s));
  }

  const st = wp.spine_twist;
  const sl = wp.spine_lean ?? 0;
  for (const [frame, twist, lean] of [
    [0,          st,   sl],
    [hh,         0,   -sl * 0.5],
    [half,      -st,   sl],
    [half + hh,  0,   -sl * 0.5],
    [frames,     st,   sl],
  ]) {
    rotKfs.push(_rot('Spine', frame, fps, lean, 0, twist));
  }

  return { rotKfs, transKfs };
}

// ── Run animation ──────────────────────────────────────────────────────────────

function runKfs(_cfg) {
  const rp = ANIM_PARAMS.run;
  const frames = rp.cycle_frames;
  const fps = rp.fps;
  const half = frames / 2;
  const hh = half / 2;

  const uls = rp.upper_leg_swing;
  const llb = rp.lower_leg_bend;
  const fr = rp.foot_rock;
  const uas = rp.upper_arm_swing;
  const lab = rp.lower_arm_bend;

  const rotKfs = [];
  const transKfs = [];

  const leftLeg = [
    [0,          uls,         -llb * 0.2,  -fr],
    [hh,         uls * 0.3,   -llb,          0],
    [half,      -uls,         -llb * 0.1,   fr],
    [half + hh,  0,           -llb * 0.5,   0],
    [frames,     uls,         -llb * 0.2,  -fr],
  ];
  const rightLeg = [
    [0,         -uls,         -llb * 0.1,   fr],
    [hh,         0,           -llb * 0.5,   0],
    [half,       uls,         -llb * 0.2,  -fr],
    [half + hh,  uls * 0.3,   -llb,          0],
    [frames,    -uls,         -llb * 0.1,   fr],
  ];

  for (const [data, side] of [[leftLeg, 'L'], [rightLeg, 'R']]) {
    for (const [frame, ulA, llA, ftA] of data) {
      rotKfs.push(_rot(`UpperLeg.${side}`, frame, fps, ulA));
      rotKfs.push(_rot(`LowerLeg.${side}`, frame, fps, llA));
      rotKfs.push(_rot(`Foot.${side}`, frame, fps, ftA));
    }
  }

  const leftArm = [
    [0,          -uas, -lab * 0.8],
    [hh,          0,   -lab * 0.5],
    [half,        uas, -lab],
    [half + hh,   0,   -lab * 0.5],
    [frames,     -uas, -lab * 0.8],
  ];
  const rightArm = [
    [0,           uas, -lab],
    [hh,          0,   -lab * 0.5],
    [half,       -uas, -lab * 0.8],
    [half + hh,   0,   -lab * 0.5],
    [frames,      uas, -lab],
  ];

  for (const [data, side] of [[leftArm, 'L'], [rightArm, 'R']]) {
    for (const [frame, uaA, laA] of data) {
      rotKfs.push(_rot(`UpperArm.${side}`, frame, fps, uaA));
      rotKfs.push(_rot(`LowerArm.${side}`, frame, fps, laA));
    }
  }

  const lean = rp.spine_lean;
  const twist = rp.spine_twist;
  for (const [frame, tw] of [
    [0,          twist],
    [hh,         0],
    [half,      -twist],
    [half + hh,  0],
    [frames,     twist],
  ]) {
    rotKfs.push(_rot('Spine', frame, fps, lean, 0, tw));
  }

  for (const frame of [0, hh, half, half + hh, frames]) {
    rotKfs.push(_rot('Chest', frame, fps, lean * 0.5));
  }

  const bob = rp.hip_bob;
  const sway = rp.hip_sway;
  for (const [frame, b, s] of [
    [0,          0,    -sway],
    [hh,         bob,   0],
    [half,       0,     sway],
    [half + hh,  bob,   0],
    [frames,     0,    -sway],
  ]) {
    transKfs.push(_trans('Hips', frame, fps, 0, 0, b));
    rotKfs.push(_rot('Hips', frame, fps, 0, 0, s));
  }

  return { rotKfs, transKfs };
}

// ── Jump animation ─────────────────────────────────────────────────────────────

function jumpKfs(_cfg) {
  const jp = ANIM_PARAMS.jump;
  const fTotal = jp.total_frames;
  const fps = jp.fps;
  const fCrouch = jp.crouch_end;
  const fLaunch = jp.launch_end;
  const fApex = jp.apex;
  const fLand = jp.land_end;

  const rotKfs = [];
  const transKfs = [];

  // Frame 0: neutral
  for (const bn of ['Spine', 'Chest', 'Hips']) {
    rotKfs.push(_rot(bn, 0, fps));
  }
  for (const side of ['L', 'R']) {
    for (const bn of [`UpperLeg.${side}`, `LowerLeg.${side}`, `Foot.${side}`,
                       `UpperArm.${side}`, `LowerArm.${side}`]) {
      rotKfs.push(_rot(bn, 0, fps));
    }
  }
  transKfs.push(_trans('Hips', 0, fps, 0, 0, 0));

  // Crouch
  const cl = jp.crouch_legs;
  const cs = jp.crouch_spine;
  for (const side of ['L', 'R']) {
    rotKfs.push(_rot(`UpperLeg.${side}`, fCrouch, fps, cl));
    rotKfs.push(_rot(`LowerLeg.${side}`, fCrouch, fps, -cl * 1.2));
    rotKfs.push(_rot(`Foot.${side}`, fCrouch, fps, cl * 0.3));
    rotKfs.push(_rot(`UpperArm.${side}`, fCrouch, fps, 25));
    rotKfs.push(_rot(`LowerArm.${side}`, fCrouch, fps, -40));
  }
  rotKfs.push(_rot('Spine', fCrouch, fps, cs));
  rotKfs.push(_rot('Chest', fCrouch, fps, cs * 0.6));
  transKfs.push(_trans('Hips', fCrouch, fps, 0, 0, -0.08));

  // Launch
  const llLaunch = jp.launch_legs;
  const ls = jp.launch_spine;
  const ar = jp.arm_raise;
  for (const side of ['L', 'R']) {
    rotKfs.push(_rot(`UpperLeg.${side}`, fLaunch, fps, llLaunch));
    rotKfs.push(_rot(`LowerLeg.${side}`, fLaunch, fps, -5));
    rotKfs.push(_rot(`Foot.${side}`, fLaunch, fps, -30));
    rotKfs.push(_rot(`UpperArm.${side}`, fLaunch, fps, ar));
    rotKfs.push(_rot(`LowerArm.${side}`, fLaunch, fps, -20));
  }
  rotKfs.push(_rot('Spine', fLaunch, fps, ls));
  rotKfs.push(_rot('Chest', fLaunch, fps, ls * 0.5));
  transKfs.push(_trans('Hips', fLaunch, fps, 0, 0, jp.hip_height));

  // Apex tuck
  const tl = jp.tuck_legs;
  for (const side of ['L', 'R']) {
    rotKfs.push(_rot(`UpperLeg.${side}`, fApex, fps, tl));
    rotKfs.push(_rot(`LowerLeg.${side}`, fApex, fps, -tl * 1.3));
    rotKfs.push(_rot(`UpperArm.${side}`, fApex, fps, -15));
  }
  rotKfs.push(_rot('Spine', fApex, fps, 5));
  rotKfs.push(_rot('Chest', fApex, fps, 3));
  transKfs.push(_trans('Hips', fApex, fps, 0, 0, jp.hip_height * 0.8));

  // Landing
  const la = jp.land_absorb;
  for (const side of ['L', 'R']) {
    rotKfs.push(_rot(`UpperLeg.${side}`, fLand, fps, la));
    rotKfs.push(_rot(`LowerLeg.${side}`, fLand, fps, -la * 1.1));
    rotKfs.push(_rot(`Foot.${side}`, fLand, fps, 10));
    rotKfs.push(_rot(`UpperArm.${side}`, fLand, fps, 15));
    rotKfs.push(_rot(`LowerArm.${side}`, fLand, fps, -25));
  }
  rotKfs.push(_rot('Spine', fLand, fps, -10));
  rotKfs.push(_rot('Chest', fLand, fps, -8));
  transKfs.push(_trans('Hips', fLand, fps, 0, 0, -0.06));

  // Return to neutral
  for (const bn of ['Spine', 'Chest']) {
    rotKfs.push(_rot(bn, fTotal, fps));
  }
  for (const side of ['L', 'R']) {
    for (const bn of [`UpperLeg.${side}`, `LowerLeg.${side}`, `Foot.${side}`,
                       `UpperArm.${side}`, `LowerArm.${side}`]) {
      rotKfs.push(_rot(bn, fTotal, fps));
    }
  }
  transKfs.push(_trans('Hips', fTotal, fps, 0, 0, 0));

  return { rotKfs, transKfs };
}

// ── Attack animation ───────────────────────────────────────────────────────────

function attackKfs(_cfg) {
  const ap = ANIM_PARAMS.attack;
  const fTotal = ap.total_frames;
  const fps = ap.fps;
  const fWindup = ap.windup_end;
  const fStrike = ap.strike_end;
  const fFollow = ap.follow_end;

  const rotKfs = [];
  const transKfs = [];

  // Frame 0: neutral
  for (const bn of ['Spine', 'Chest']) {
    rotKfs.push(_rot(bn, 0, fps));
  }
  for (const side of ['L', 'R']) {
    for (const bn of [`UpperArm.${side}`, `LowerArm.${side}`,
                       `UpperLeg.${side}`, `LowerLeg.${side}`]) {
      rotKfs.push(_rot(bn, 0, fps));
    }
  }

  // Windup
  const tt = ap.torso_twist;
  rotKfs.push(_rot('Spine', fWindup, fps, -5, 0, -tt));
  rotKfs.push(_rot('Chest', fWindup, fps, 0, 0, -tt * 0.6));
  rotKfs.push(_rot('UpperArm.R', fWindup, fps, ap.windup_arm));
  rotKfs.push(_rot('LowerArm.R', fWindup, fps, ap.windup_forearm));
  rotKfs.push(_rot('UpperArm.L', fWindup, fps, -15));
  rotKfs.push(_rot('LowerArm.L', fWindup, fps, -45));
  rotKfs.push(_rot('UpperLeg.R', fWindup, fps, ap.rear_leg));
  rotKfs.push(_rot('UpperLeg.L', fWindup, fps, ap.lunge_leg * 0.5));

  // Strike
  rotKfs.push(_rot('Spine', fStrike, fps, 8, 0, tt * 0.8));
  rotKfs.push(_rot('Chest', fStrike, fps, 0, 0, tt * 0.5));
  rotKfs.push(_rot('UpperArm.R', fStrike, fps, ap.strike_arm));
  rotKfs.push(_rot('LowerArm.R', fStrike, fps, ap.strike_forearm));
  rotKfs.push(_rot('UpperArm.L', fStrike, fps, -20));
  rotKfs.push(_rot('LowerArm.L', fStrike, fps, -35));
  rotKfs.push(_rot('UpperLeg.L', fStrike, fps, ap.lunge_leg));
  rotKfs.push(_rot('LowerLeg.L', fStrike, fps, -ap.lunge_leg * 0.5));
  rotKfs.push(_rot('UpperLeg.R', fStrike, fps, ap.rear_leg));

  // Follow-through
  rotKfs.push(_rot('Spine', fFollow, fps, 3, 0, tt * 0.3));
  rotKfs.push(_rot('Chest', fFollow, fps, 0, 0, tt * 0.2));
  rotKfs.push(_rot('UpperArm.R', fFollow, fps, ap.strike_arm + 15));
  rotKfs.push(_rot('LowerArm.R', fFollow, fps, ap.strike_forearm - 10));

  // Return to neutral
  for (const bn of ['Spine', 'Chest']) {
    rotKfs.push(_rot(bn, fTotal, fps));
  }
  for (const side of ['L', 'R']) {
    for (const bn of [`UpperArm.${side}`, `LowerArm.${side}`,
                       `UpperLeg.${side}`, `LowerLeg.${side}`]) {
      rotKfs.push(_rot(bn, fTotal, fps));
    }
  }

  return { rotKfs, transKfs };
}

// ── Public API ────────────────────────────────────────────────────────────────

const BUILDERS = {
  idle: idleKfs,
  walk: walkKfs,
  run: runKfs,
  jump: jumpKfs,
  attack: attackKfs,
};

const DURATIONS = {
  idle:   48 / 24,
  walk:   24 / 24,
  run:    16 / 24,
  jump:   32 / 24,
  attack: 20 / 24,
};

/**
 * Build THREE.AnimationClip array for the requested animations.
 * @param {Object} cfg - config with .animations ('all' or string[])
 * @returns {THREE.AnimationClip[]}
 */
export function buildAnimations(cfg) {
  const requested = cfg.animations === 'all'
    ? ['idle', 'walk', 'run', 'jump', 'attack']
    : (cfg.animations ?? []);

  return requested.map(name => {
    const builder = BUILDERS[name];
    if (!builder) throw new Error(`Unknown animation '${name}'`);
    const { rotKfs, transKfs } = builder(cfg);
    const tracks = [...buildRotTracks(rotKfs), ...buildTransTracks(transKfs)];
    return new THREE.AnimationClip(name, DURATIONS[name], tracks);
  });
}
