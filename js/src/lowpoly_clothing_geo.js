/**
 * Clothing geometry for the low-poly (realistic) body mesh.
 *
 * ALL zone boundaries are derived from the canonical skeleton bone positions
 * in skeleton.js rather than from fixed height percentages.  This makes
 * the clothing self-consistent with the rig regardless of character preset.
 *
 * Bone reference (from boneWorldPositions(H)):
 *   Foot.L/R   (15/18) → Y = H * 0.03   ankle
 *   LowerLeg   (14/17) → Y = H * 0.27   knee
 *   UpperLeg   (13/16) → Y = H * 0.50   hip joint
 *   Hips       (0)     → Y = H * 0.52   pelvis / waistband centre
 *   Chest      (2)     → Y = H * 0.68   chest
 *   Shoulder   (5)     → Y = H * 0.72   shirt armhole
 *   UpperArm   (6)     → X = ±H * 0.14  (lateral arm extent)
 *
 * Shirts:  face-extrusion from body-mesh triangles (good for torso).
 * Pants:   smooth tube geometry — one cylinder per leg + waistband.
 */

import { boneWorldPositions } from './skeleton.js';

// ── Geometry utilities ────────────────────────────────────────────────────────

function computeVertexNormals(positions, indices) {
  const nVerts = positions.length / 3;
  const normals = new Float32Array(nVerts * 3);
  for (let t = 0; t < indices.length / 3; t++) {
    const ia = indices[t*3], ib = indices[t*3+1], ic = indices[t*3+2];
    const ax=positions[ia*3],ay=positions[ia*3+1],az=positions[ia*3+2];
    const bx=positions[ib*3],by=positions[ib*3+1],bz=positions[ib*3+2];
    const cx=positions[ic*3],cy=positions[ic*3+1],cz=positions[ic*3+2];
    const ex=bx-ax,ey=by-ay,ez=bz-az, fx=cx-ax,fy=cy-ay,fz=cz-az;
    const nx=ey*fz-ez*fy, ny=ez*fx-ex*fz, nz=ex*fy-ey*fx;
    for (const i of [ia,ib,ic]) { normals[i*3]+=nx; normals[i*3+1]+=ny; normals[i*3+2]+=nz; }
  }
  for (let i = 0; i < nVerts; i++) {
    const nx=normals[i*3],ny=normals[i*3+1],nz=normals[i*3+2];
    const len=Math.sqrt(nx*nx+ny*ny+nz*nz)||1;
    normals[i*3]/=len; normals[i*3+1]/=len; normals[i*3+2]/=len;
  }
  return normals;
}

function mergeGeometries(geos) {
  const valid = geos.filter(Boolean);
  if (valid.length === 0) return null;
  if (valid.length === 1) return valid[0];
  let totalV=0,totalI=0;
  for (const g of valid) { totalV+=g.positions.length/3; totalI+=g.indices.length; }
  const mp=new Float32Array(totalV*3), mn=new Float32Array(totalV*3), mi=new Uint32Array(totalI);
  let vOff=0, iOff=0;
  for (const g of valid) {
    mp.set(g.positions,vOff*3); mn.set(g.normals,vOff*3);
    for (let i=0;i<g.indices.length;i++) mi[iOff+i]=g.indices[i]+vOff;
    vOff+=g.positions.length/3; iOff+=g.indices.length;
  }
  return { positions:mp, normals:mn, indices:mi };
}

/** Build a smooth tube from an array of { y, cx, cz, r } rings. */
function tubeFromRings(rings, numSegs) {
  if (rings.length < 2) return null;
  const positions=[], indices=[];
  for (const {y,cx,cz,r} of rings) {
    for (let s=0;s<numSegs;s++) {
      const a=(2*Math.PI*s)/numSegs;
      positions.push(cx+r*Math.cos(a), y, cz+r*Math.sin(a));
    }
  }
  // Winding (a,c,b)/(b,c,d) → outward normals on a CCW ring
  for (let ri=0;ri<rings.length-1;ri++) {
    for (let s=0;s<numSegs;s++) {
      const next=(s+1)%numSegs;
      const a=ri*numSegs+s, b=ri*numSegs+next;
      const c=(ri+1)*numSegs+s, d=(ri+1)*numSegs+next;
      indices.push(a,c,b, b,c,d);
    }
  }
  const pos=new Float32Array(positions), idx=new Uint32Array(indices);
  return { positions:pos, normals:computeVertexNormals(pos,idx), indices:idx };
}

// ── Pants geometry ────────────────────────────────────────────────────────────

/**
 * Build two leg tubes + a waistband.
 *
 * Leg tube centres come from the skeleton bone X positions (±H*0.09).
 * Leg tube radii are measured from the actual body mesh vertices relative
 * to those fixed centres; outliers beyond H*0.12 are ignored so that
 * crotch / inner-thigh vertices don't inflate the tube.
 *
 * @param {Float32Array} bPos
 * @param {number} yLo          bottom of zone (ankle / knee)
 * @param {number} yHi          top of zone (hip joint)
 * @param {number} H            character height
 * @param {number} minY         lowest Y in mesh (floor offset)
 * @param {number} baseOffset
 */
function buildPantsGeometry(bPos, yLo, yHi, H, minY, baseOffset) {
  const vCount   = bPos.length / 3;
  const numSlices = 14;
  const legSegs   = 16;
  const hipSegs   = 20;

  // Leg bone X centres (characters' left leg = +X side, right = −X side)
  const legCentreX = H * 0.09;  // magnitude; left = +legCentreX, right = −legCentreX
  const maxLegR    = H * 0.12;  // outlier cap — no leg is wider than this

  function buildLegTube(isLeftSide) {
    // "left side" in our coord system = positive X (UpperLeg.L bone is at +H*0.09)
    const boneX = isLeftSide ? +legCentreX : -legCentreX;
    const rings  = [];

    for (let si = 0; si <= numSlices; si++) {
      const y    = yLo + (yHi - yLo) * (si / numSlices);
      const yWin = (yHi - yLo) / numSlices * 0.70;

      // Collect vertices on this leg side
      const dists = [];
      let sumZ = 0, nZ = 0;
      for (let i = 0; i < vCount; i++) {
        const py=bPos[i*3+1], px=bPos[i*3];
        if (py < y-yWin || py > y+yWin) continue;
        // Side filter — use half the bone X as boundary to avoid crotch bleed
        if (isLeftSide ? px < legCentreX*0.5 : px > -legCentreX*0.5) continue;
        const dx=px-boneX, dz=bPos[i*3+2];
        const r=Math.sqrt(dx*dx+dz*dz);
        if (r > maxLegR) continue;   // ignore outliers
        dists.push(r);
        sumZ += bPos[i*3+2]; nZ++;
      }
      if (dists.length < 3) continue;

      // Use 85th-percentile radius so tube fits snugly without being over-inflated
      dists.sort((a,b)=>a-b);
      const r85 = dists[Math.floor(dists.length*0.85)];
      const cz  = nZ > 0 ? sumZ/nZ : 0;   // mean Z (leg may lean fwd/back slightly)

      rings.push({ y, cx: boneX, cz, r: r85 + baseOffset });
    }
    return tubeFromRings(rings, legSegs);
  }

  // Waistband — spans the full pelvis width, covers the open tube tops
  function buildWaistband() {
    const waistH  = H * 0.06;
    const wLo     = yHi - waistH * 0.3;
    const wHi     = yHi + waistH * 0.7;
    const wSlices = 5;
    const rings   = [];

    for (let si = 0; si <= wSlices; si++) {
      const y    = wLo + (wHi - wLo) * (si / wSlices);
      const yWin = waistH / wSlices;
      let sumX=0, sumZ=0, n=0;
      for (let i = 0; i < vCount; i++) {
        const py=bPos[i*3+1];
        if (py<y-yWin||py>y+yWin) continue;
        sumX+=bPos[i*3]; sumZ+=bPos[i*3+2]; n++;
      }
      if (n < 3) continue;
      const cx=sumX/n, cz=sumZ/n;
      let maxR=0;
      for (let i=0;i<vCount;i++) {
        const py=bPos[i*3+1];
        if (py<y-yWin||py>y+yWin) continue;
        const dx=bPos[i*3]-cx, dz=bPos[i*3+2]-cz;
        maxR=Math.max(maxR, Math.sqrt(dx*dx+dz*dz));
      }
      rings.push({ y, cx, cz, r: maxR + baseOffset*1.1 });
    }
    return tubeFromRings(rings, hipSegs);
  }

  return mergeGeometries([buildLegTube(true), buildLegTube(false), buildWaistband()]);
}

// ── Main export ───────────────────────────────────────────────────────────────

/**
 * @param {{ positions, normals, indices, height }} bodyData
 * @param {Object} cfg
 */
export function buildClothingGeometry(bodyData, cfg) {
  const { positions: bPos, normals: bNorm, indices: bIdx } = bodyData;
  const vCount   = bPos.length / 3;
  const triCount = bIdx.length / 3;

  // Body extents
  let minY=Infinity, maxY=-Infinity;
  for (let i=0;i<vCount;i++) {
    const y=bPos[i*3+1]; if(y<minY)minY=y; if(y>maxY)maxY=y;
  }
  const bodyH = maxY - minY;

  // ── Zone boundaries from skeleton bone positions ─────────────────────────
  // boneWorldPositions(H) returns positions for a character H-metres tall
  // with feet at Y=0.  Our normalised mesh has the same convention, so we
  // only need to add minY (≈0 after loadLowPolyMesh) as a floor offset.
  const H  = bodyData.height ?? bodyH;
  const bp = boneWorldPositions(H);
  const bY = (idx) => bp[idx][1] + minY;

  const ankleY    = bY(15);              // H*0.03  — Foot.L
  const kneeY     = bY(14);              // H*0.27  — LowerLeg.L
  const hipJointY = bY(13);             // H*0.50  — UpperLeg.L
  const waistY    = bY(0);              // H*0.52  — Hips
  const chestY    = bY(2);              // H*0.68  — Chest
  const shoulderY = bY(5);              // H*0.72  — Shoulder.L (shirt armhole)

  // X caps based on bone lateral positions (absolute, not % of maxAbsX)
  const X_TORSO_HALF    = Math.abs(bp[5][0]) * 1.15;  // slightly beyond shoulder bone
  const X_SLEEVE_HALF   = Math.abs(bp[6][0]) * 1.40;  // past upper-arm bone for sleeves

  const baseOffset   = 0.022;
  const clothingList = Array.isArray(cfg.clothing) ? cfg.clothing : [];
  const result       = {};

  for (const ctype of clothingList) {
    if (ctype === 'none') continue;

    // ── Pants / shorts — tube geometry ────────────────────────────────────
    if (ctype === 'jeans' || ctype === 'shorts') {
      const yLo = ctype === 'jeans' ? ankleY + H*0.01 : kneeY;
      const geo = buildPantsGeometry(bPos, yLo, waistY, H, minY, baseOffset);
      if (!geo) { console.warn(`[LP Clothing] No leg geometry for '${ctype}'`); continue; }
      result[ctype] = geo;
      console.log(`[LP Clothing] Built '${ctype}' (tube): ${geo.positions.length/3} verts`);
      continue;
    }

    // ── Shirts — face-extrusion ────────────────────────────────────────────
    // Zone: pelvis/waist to shoulder.  X cap keeps torso but trims far arm.
    const SHIRT_ZONES = {
      polo:         [waistY,  shoulderY, X_SLEEVE_HALF ],
      short_sleeve: [waistY,  shoulderY, X_SLEEVE_HALF ],
      long_sleeve:  [waistY,  shoulderY, Infinity       ],  // arms included
      v_neck:       [waistY,  chestY,    X_TORSO_HALF   ],
    };

    const zone = SHIRT_ZONES[ctype];
    if (!zone) continue;
    const [yLo, yHi, xCap] = zone;

    const verts=[], faces=[], vertMap=new Map();
    for (let t=0;t<triCount;t++) {
      const ia=bIdx[t*3], ib=bIdx[t*3+1], ic=bIdx[t*3+2];
      const vs=[ia,ib,ic].map(i=>({x:bPos[i*3],y:bPos[i*3+1],z:bPos[i*3+2],i}));
      if (!vs.some(v=>v.y>=yLo&&v.y<=yHi)) continue;
      const centX=(vs[0].x+vs[1].x+vs[2].x)/3;
      if (Math.abs(centX)>xCap) continue;
      const newIdxs=vs.map(v=>{
        if (!vertMap.has(v.i)) {
          const nx=bNorm?bNorm[v.i*3]:0, ny=bNorm?bNorm[v.i*3+1]:0, nz=bNorm?bNorm[v.i*3+2]:0;
          verts.push(v.x+nx*baseOffset, v.y+ny*baseOffset, v.z+nz*baseOffset);
          vertMap.set(v.i, verts.length/3-1);
        }
        return vertMap.get(v.i);
      });
      faces.push(...newIdxs);
    }

    if (verts.length===0) {
      console.warn(`[LP Clothing] No faces for '${ctype}' — yLo=${yLo.toFixed(3)}, yHi=${yHi.toFixed(3)}, xCap=${isFinite(xCap)?xCap.toFixed(3):'Inf'}`);
      continue;
    }
    const pos=new Float32Array(verts), idx=new Uint32Array(faces);
    result[ctype]={ positions:pos, normals:computeVertexNormals(pos,idx), indices:idx };
    console.log(`[LP Clothing] Built '${ctype}': ${verts.length/3} verts, ${faces.length/3} faces`);
  }
  return result;
}

// ── Collar and buttons ────────────────────────────────────────────────────────

export function buildCollarGeometry(bodyData, armY, bodyHeight, baseOffset) {
  const bPos   = bodyData.positions;
  const vCount = bPos.length / 3;
  const yWindow  = bodyHeight * 0.04;
  const neckXCap = bodyHeight * 0.05;
  let maxZ=-Infinity, minZ=Infinity, maxAbsX=0;
  for (let i=0;i<vCount;i++) {
    const y=bPos[i*3+1], ax=Math.abs(bPos[i*3]);
    if (Math.abs(y-armY)<yWindow&&ax<neckXCap) {
      const z=bPos[i*3+2];
      if(z>maxZ)maxZ=z; if(z<minZ)minZ=z; if(ax>maxAbsX)maxAbsX=ax;
    }
  }
  if (maxZ===-Infinity) return null;
  const collarH=bodyHeight*0.04, collarOff=baseOffset*1.8;
  const radiusX=maxAbsX+collarOff, radiusZ=(maxZ-minZ)/2+collarOff;
  const centerZ=(maxZ+minZ)/2, segs=16;
  const positions=[], indices=[];
  for (let i=0;i<segs;i++) {
    const a=(2*Math.PI*i)/segs;
    const x=radiusX*Math.cos(a), z=centerZ+radiusZ*Math.sin(a);
    positions.push(x, armY-collarH*0.25, z, x, armY+collarH*0.75, z);
  }
  for (let i=0;i<segs;i++) {
    const next=(i+1)%segs;
    const b0=i*2,b1=next*2,t0=b0+1,t1=b1+1;
    indices.push(b0,t0,b1, b1,t0,t1);
  }
  const pos=new Float32Array(positions), idx=new Uint32Array(indices);
  return { positions:pos, normals:computeVertexNormals(pos,idx), indices:idx };
}

export function buildButtonGeometry(bodyData, yLo, yHi, numButtons=4) {
  const bPos=bodyData.positions, vCount=bPos.length/3;
  let maxZ=-Infinity;
  for (let i=0;i<vCount;i++) {
    const y=bPos[i*3+1], ax=Math.abs(bPos[i*3]), z=bPos[i*3+2];
    if (y>=yLo&&y<=yHi&&ax<0.05&&z>maxZ) maxZ=z;
  }
  if (maxZ===-Infinity) return null;
  const buttonZ=maxZ+0.030, buttonR=0.018, segs=8;
  const yStart=yLo+(yHi-yLo)*0.15, yEnd=yHi-(yHi-yLo)*0.12;
  const yStep=numButtons>1?(yEnd-yStart)/(numButtons-1):0;
  const positions=[], indices=[];
  for (let b=0;b<numButtons;b++) {
    const by=yStart+b*yStep, center=positions.length/3;
    positions.push(0,by,buttonZ);
    for (let i=0;i<segs;i++) {
      const a=(2*Math.PI*i)/segs;
      positions.push(buttonR*Math.cos(a), by+buttonR*Math.sin(a), buttonZ);
    }
    for (let i=0;i<segs;i++) {
      const next=(i+1)%segs;
      indices.push(center, center+1+i, center+1+next);
    }
  }
  const pos=new Float32Array(positions), idx=new Uint32Array(indices);
  return { positions:pos, normals:computeVertexNormals(pos,idx), indices:idx };
}
