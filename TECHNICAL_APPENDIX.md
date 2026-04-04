# TECHNICAL APPENDIX
## Detailed Code Comparisons & Algorithms

---

## A. HAIR SYSTEM - DETAILED ARCHITECTURE

### A.1 Ring Creation Algorithm

**Blender (hair.py, lines 69–90):**
```python
def _ring(bm, cx, cy, cz, rx, ry, n=8):
    """Create an n-vertex elliptical ring in the XY plane at height cz.
    
    Vertex order for n=8:
      i=0  front      (y most negative — faces forward)
      i=1  front-right (+x, -y)
      i=2  right       (+x)
      i=3  back-right  (+x, +y)
      i=4  back        (y most positive)
      i=5  back-left   (-x, +y)
      i=6  left        (-x)
      i=7  front-left  (-x, -y)
    """
    verts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        verts.append(bm.verts.new((
            cx + rx * math.sin(a),
            cy - ry * math.cos(a),
            cz,
        )))
    return verts
```

**Three.js (hair_geo.js, lines 34–44):**
```javascript
function createRing(cx, cy, cz, rx, ry, n = CAP_RING_N) {
  const verts = [];
  for (let i = 0; i < n; i++) {
    const a = (2 * Math.PI * i) / n;
    verts.push(new THREE.Vector3(
      cx + rx * Math.sin(a),
      cy - ry * Math.cos(a),
      cz
    ));
  }
  return verts;
}
```

**Analysis:**
- Identical loop structure and trigonometry
- Both use `sin(a)` for X, `-cos(a)` for Y
- Allows elliptical scaling via `rx`, `ry` multipliers
- Ring vertex 0 always faces forward (minimum Y)

### A.2 Ring Bridging (Quad Strips)

**Blender (hair.py, lines 93–101):**
```python
def _bridge(bm, ring_a, ring_b):
    """Connect two equal-length rings with a quad strip."""
    n = len(ring_a)
    for i in range(n):
        j = (i + 1) % n
        try:
            bm.faces.new([ring_a[i], ring_a[j], ring_b[j], ring_b[i]])
        except ValueError:
            pass
```

**Three.js (hair_geo.js, lines 51–57):**
```javascript
function bridgeRings(geometry, ringA, ringB) {
  const n = ringA.length;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    addFace(geometry, ringA[i], ringA[j], ringB[j], ringB[i]);
  }
}
```

**Geometry Result:**
```
Ring A:  v0 — v1 — v2 — ... — vn-1 — (wrap to v0)
         |    |    |          |
         |    |    |          |
Ring B:  w0 — w1 — w2 — ... — wn-1 — (wrap to w0)

Each quad (vi, vi+1, wi+1, wi) becomes 2 triangles:
  Triangle 1: (vi, vi+1, wi+1)
  Triangle 2: (vi, wi+1, wi)
```

**Face Count:** N rings × (N-1 quads × 2 triangles) = 2N² - 2N triangles

### A.3 Cap Level Specifications

**Constants (Both Systems Identical):**

```python
_CAP_LEVELS = [
    (0.00, 0.97, 0.90),   # θ=0°   (hairline / equator)
    (0.50, 0.84, 0.77),   # θ≈30°  (upper forehead)
    (0.86, 0.52, 0.48),   # θ≈60°  (upper cranium)
    (0.97, 0.14, 0.13),   # θ≈80°  (crown apex)
]
```

**Interpretation:**
- `z_offset`: Height as fraction of head radius (for spherical dome)
- `rx_scale`: X-radius scale relative to horizontal head radius
- `ry_scale`: Y-radius scale relative to head radius (front-to-back)

**Spherical Dome Math:**
```
For elevation angle θ (0° = equator, 90° = pole):
  height     = sin(θ)
  x-radius   ≈ cos(θ)
  y-radius   ≈ cos(θ) × 0.9  (head narrower front-to-back)

θ=0°:   height=0.00, cos=1.00 → levels[0] = (0.00, 0.97, 0.90) ✓
θ=30°:  height=0.50, cos=0.87 → levels[1] = (0.50, 0.84, 0.77) ✓
θ=60°:  height=0.86, cos=0.50 → levels[2] = (0.86, 0.52, 0.48) ✓
θ=80°:  height=0.97, cos=0.17 → levels[3] = (0.97, 0.14, 0.13) ✓
```

Perfect spherical dome proportions!

### A.4 Panel Row Extrusion

**Blender (hair.py, lines 239–268):**
```python
def _panel_rows(bm, top_verts, rows_spec):
    """Extrude a strip of vertices downward in sequential quad rows.
    
    Args:
        top_verts:  List of Blender verts forming the top edge.
        rows_spec:  List of (dz, x_scale, y_scale) tuples where:
                    - dz is cumulative
                    - x_scale and y_scale are applied to original top_verts
    """
    prev = top_verts
    cumulative_dz = 0.0
    for dz, xm, ym in rows_spec:
        cumulative_dz += dz
        new_row = [
            bm.verts.new((v.co.x * xm, v.co.y * ym, v.co.z + cumulative_dz))
            for v in top_verts  # Scale relative to ORIGINAL verts
        ]
        for i in range(len(prev) - 1):
            try:
                bm.faces.new([prev[i], prev[i + 1], new_row[i + 1], new_row[i]])
            except ValueError:
                pass
        prev = new_row
```

**Three.js (hair_geo.js, lines 195–212):**
```javascript
function createPanelRows(geometry, topVerts, rowsSpec, headR) {
  let prev = topVerts;
  let cumulativeDz = 0;

  for (const [dz, xm, ym] of rowsSpec) {
    cumulativeDz += dz;
    const newRow = topVerts.map(
      v => new THREE.Vector3(v.x * xm, v.y * ym, v.z + cumulativeDz)
    );

    // Bridge rows
    for (let i = 0; i < prev.length - 1; i++) {
      addFace(geometry, prev[i], prev[i + 1], newRow[i + 1], newRow[i]);
    }

    prev = newRow;
  }
}
```

**Key Detail:** Each row scales relative to the ORIGINAL `top_verts`, not the previous row. This creates a tapered panel effect:

```
Frame 0: Original verts [0.9, 0.8]  → topVerts
Frame 1: Scale [0.97, 0.95] → new_row
Frame 2: Scale [0.93, 0.90] → new_row (tapers further)
Frame 3: Scale [0.88, 0.85] → new_row (continues taper)
```

### A.5 Fringe Clump Definitions

**Short Style (hair.py & hair_geo.js):**
```python
[
    [-0.46, -0.05, 0.04, 0.04, 0.12, 0.13],   # Left outer
    [-0.22, 0.00, 0.05, 0.04, 0.13, 0.13],    # Left inner
    [0.00, 0.00, 0.05, 0.04, 0.14, 0.15],     # Center (largest)
    [0.22, 0.00, 0.05, 0.04, 0.13, 0.13],     # Right inner
    [0.46, 0.05, 0.04, 0.04, 0.12, 0.13],     # Right outer
]
```

**Clump Definition Format:**
```
(cx, x_drift, y_fwd, z_mid, z_tip, w_root)

cx:      X centre as multiple of head_r_horiz
x_drift: Extra X at tip (×head_r_horiz) — sideways sweep
y_fwd:   Forward motion at tip (×head_r_horiz) — added to fr_y
z_mid:   Z drop at mid-point below root (×head_r)
z_tip:   Z drop at tip below root (×head_r)
w_root:  Half-width at root (×head_r_horiz)
```

**Example Calculation (Center Clump):**
```python
head_r = 0.10m, head_r_horiz = 0.10m
hr_h = head_r_horiz = 0.10m

cx=0.00:     x_centre = 0.00 * 0.10 = 0.0m
x_drift=0.00: drift = 0.00 * 0.10 = 0.0m
y_fwd=0.05:  y_forward = 0.05 * 0.10 = 0.005m
z_mid=0.04:  z_drop_mid = 0.04 * 0.10 = 0.004m
z_tip=0.14:  z_drop_tip = 0.14 * 0.10 = 0.014m
w_root=0.15: width_root = 0.15 * 0.10 = 0.015m
w_mid = w_root * 0.58 = 0.0087m

Spine points:
  Root: (0.0, fr_y, hl_z + 0.001)
  Mid:  (0.0, fr_y - 0.0025, hl_z - 0.004)
  Tip:  (0.0, fr_y - 0.005, hl_z - 0.014)

Widths: [0.015, 0.0087, 0]  → pointed tip
```

---

## B. EYE SYSTEM - DETAILED GEOMETRY

### B.1 Elliptical Disc Construction

**Triangle Fan Pattern:**
```
        v0 (center)
       /|\
      / | \
     /  |  \
    v1--+--v2  (ring segment)
    |   |   |
    |   |   |
    v8--+--v3
    |   |   |
    |   |   |
    v7--+--v4
     \  |  /
      \ | /
       \|/
       v6--v5
```

**Blender Construction (eyes.py, lines 86–110):**
```python
bm = bmesh_mod.new()

for x_sign in (1, -1):
    cx = x_sign * eye_x  # ±0.0324m (for HR=0.09m)
    y  = disc_y          # ≈-0.0558m (forward offset)
    
    # Center vertex
    center_v = bm.verts.new((cx, y, eye_z))
    
    # Ring vertices (10 segments)
    ring_vs = [
        bm.verts.new((
            cx + rx * math.cos(2 * math.pi * i / n),  # cos for X
            y,
            eye_z + ry * math.sin(2 * math.pi * i / n),  # sin for Z
        ))
        for i in range(n)
    ]
    
    # Triangle fan (winding depends on x_sign for correct normals)
    for i in range(n):
        j = (i + 1) % n
        if x_sign > 0:
            bm.faces.new([center_v, ring_vs[i], ring_vs[j]])
        else:
            bm.faces.new([center_v, ring_vs[j], ring_vs[i]])  # Reversed
```

**Key Detail:** Face winding reversed for right eye to maintain consistent outward-facing normals (CCW when viewed from front).

### B.2 Highlight Positioning

**Blender (eyes.py, lines 136–177):**
```python
# Highlight positioned in upper-right corner, forward of eye disc
highlight_r = eye_r * 0.18  # 3.24% of head width (small glint)
hl_n = 6                     # Fewer segments than eye disc

for x_sign in (1, -1):
    # X: shifted right by 35% of eye radius
    cx = x_sign * eye_x + rx * 0.35
    
    # Z: high in eye (45% above center)
    hz = eye_z + ry * 0.45
    
    # Y: well forward (80% of highlight radius)
    hy = disc_y - highlight_r * 0.8
    
    # Build triangle fan
    center_h = bm2.verts.new((cx, hy, hz))
    ring_h = [
        bm2.verts.new((
            cx + highlight_r * math.cos(2 * math.pi * i / hl_n),
            hy,
            hz + highlight_r * math.sin(2 * math.pi * i / hl_n),
        ))
        for i in range(hl_n)
    ]
```

**Positioning Math:**
```
Eye disc at: (±eye_x, disc_y, eye_z)
             (±0.0324, -0.0558, 0.015)

Highlight center:
  X: ±0.0324 + 0.0405*0.35 = ±0.0546m (right of eye center)
  Y: -0.0558 - 0.0073*0.8 = -0.0616m (forward)
  Z: 0.015 + 0.0427*0.45 = 0.034m (high)

Result: Upper-right shine at 45° angle
```

---

## C. CLOTHING SYSTEM - RING-BASED APPROACH

### C.1 Blender Ring Tubes

**Torso Rings (clothing.py, lines 101–127):**
```python
def _torso_rings(bm, cfg, s, hem_fraction):
    """Build shared torso tube.
    
    s parameter: scale factor (1.22–1.25)
    hem_fraction: 0=hip level, 1=mid-torso
    """
    sw = cfg["shoulder_width"]      # ~0.18m
    hw = cfg["hip_width"]           # ~0.16m
    td = cfg.get("torso_depth", 0.20)  # front-to-back
    leg_len = cfg["leg_length"]     # ~0.93m
    torso_len = cfg["torso_length"] # ~0.68m
    
    hem_z = hip_z + torso_len * hem_fraction
    waist_z = hip_z + torso_len * 0.42
    lower_chest_z = hip_z + torso_len * 0.68
    chest_z = hip_z + torso_len
    
    specs = [
        (hem_z,         hw * 0.80 * s,  td * 0.44 * s),   # Hem (narrow)
        (waist_z,       sw * 0.65 * s,  td * 0.40 * s),   # Waist
        (lower_chest_z, sw * 0.90 * s,  td * 0.54 * s),   # Lower chest
        (chest_z,       sw * 1.05 * s,  td * 0.58 * s),   # Chest (widest)
    ]
    
    rings = []
    for z, rx, ry in specs:
        rings.append(_make_ring(bm, (0, 0, z), rx, ry))  # n=8 by default
    
    # Bridge consecutive rings
    for i in range(len(rings) - 1):
        _bridge_rings(bm, rings[i], rings[i + 1])
    
    # Cap bottom (hem)
    _cap_ring(bm, rings[0], top=False)
```

**Geometry Result:**
```
      Ring 0 (hem)      : 8 verts
          ↓ bridge ↓    : 8 quads × 2 = 16 faces
      Ring 1 (waist)    : 8 verts
          ↓ bridge ↓    : 16 faces
      Ring 2 (lower)    : 8 verts
          ↓ bridge ↓    : 16 faces
      Ring 3 (chest)    : 8 verts
      
Bottom cap: 8 triangles
─────────────────────────
Torso Total: 3 × 16 + 8 = 56 faces

Sleeves add another 40–60 faces depending on length.
```

### C.2 Sleeve Rings (clothing.py, lines 130–170)

**Short Sleeve Construction:**
```python
def _sleeve_rings(bm, cfg, s, to_wrist=True):
    for sign in [1, -1]:  # Left & right
        sx = sign * (sw + 0.04)  # Shoulder X position
        
        if to_wrist:
            # Full-length sleeve: 5 rings
            specs = [
                (arm_top_z,                        0.080 * lt * s, 0.070 * lt * s),
                (arm_top_z - upper_arm_len * 0.45, 0.072 * lt * s, 0.064 * lt * s),
                (elbow_z,                          0.058 * lt * s, 0.054 * lt * s),
                (elbow_z - lower_arm_len * 0.40,   0.060 * lt * s, 0.054 * lt * s),
                (wrist_z,                          0.046 * lt * s, 0.042 * lt * s),
            ]
        else:
            # Short sleeve: 3 rings
            specs = [
                (arm_top_z,                        0.080 * lt * s, 0.070 * lt * s),
                (arm_top_z - upper_arm_len * 0.25, 0.076 * lt * s, 0.068 * lt * s),
                (mid_arm_z,                        0.068 * lt * s, 0.062 * lt * s),
            ]
        
        # Build rings & bridge
        sleeve_rings = [_make_ring(bm, (sx, 0, z), rx, ry) for z, rx, ry in specs]
        for i in range(len(sleeve_rings) - 1):
            _bridge_rings(bm, sleeve_rings[i], sleeve_rings[i + 1])
        _cap_ring(bm, sleeve_rings[-1], top=False)
```

---

## D. THREE.JS CLOTHING - FACE-EXTRUSION APPROACH

### D.1 Zone-Based Face Selection

**Algorithm (clothing_geo.js, lines 56–97):**
```javascript
// Iterate through all triangles in body mesh
const triCount = idxAttr ? idxAttr.count / 3 : posAttr.count / 3;
for (let t = 0; t < triCount; t++) {
    // Get triangle vertex indices
    const [ia, ib, ic] = idxAttr
        ? [idxAttr.getX(t*3), idxAttr.getX(t*3+1), idxAttr.getX(t*3+2)]
        : [t*3, t*3+1, t*3+2];
    
    // Fetch vertex positions
    const vs = [ia, ib, ic].map(i => ({
        x: posAttr.getX(i), y: posAttr.getY(i), z: posAttr.getZ(i), i,
    }));
    
    // Check if ANY vertex is in the clothing zone
    const anyInZone = vs.some(v => v.z >= zLo && v.z <= zHi);
    if (!anyInZone) continue;
    
    // For leg clothing, exclude vertices beyond torso width
    if (!includeArms && vs.some(v => Math.abs(v.x) > BODY_X_CAP)) continue;
    
    // Create offset vertices
    const newIdxs = vs.map(v => {
        if (!vertMap.has(v.i)) {
            // Calculate radial distance from Y-axis (body center)
            const radialDist = Math.sqrt(v.x**2 + v.y**2) || 0.001;
            // Offset proportional to distance
            const offsetAmount = baseOffset / radialDist;
            verts.push(
                v.x + v.x * offsetAmount,
                v.y + v.y * offsetAmount,
                v.z
            );
            vertMap.set(v.i, verts.length / 3 - 1);
        }
        return vertMap.get(v.i);
    });
    faces.push(...newIdxs);
}
```

### D.2 Radial Offset Formula

**Mathematical Model:**
```
Original position: (x, y, z)
Distance from Y-axis: r = √(x² + y²)
Radial direction: (x/r, y/r)

Offset amount: offset = baseOffset / r
  Why divide by r?
  - Vertices far from center: larger r → smaller relative offset
  - Vertices near center: smaller r → larger relative offset
  - Creates uniform clothing thickness in X-Y plane
  
New position:
  x_new = x + (x/r) × offset = x × (1 + baseOffset/r²)
  y_new = y + (y/r) × offset = y × (1 + baseOffset/r²)
  z_new = z  (unchanged)
```

**Example (Character Height H=1.75m):**
```
baseOffset = 0.015 × (1.75 / 1.75) = 0.015m (15mm)

Torso vertex at (0.10, 0, 0.5):
  r = 0.10m
  offset = 0.015 / 0.10 = 0.15m
  new_x = 0.10 × (1 + 0.15) = 0.115m  (15% outward)

Limb vertex at (0.04, 0, 0.3):
  r = 0.04m
  offset = 0.015 / 0.04 = 0.375m
  new_x = 0.04 × (1 + 0.375) = 0.055m  (37.5% outward)
```

Result: **Proportional scaling maintains geometry integrity**.

---

## E. MATERIAL PROPERTY MAPPINGS

### E.1 Hair Material

**Blender:**
```python
bsdf.inputs["Base Color"].default_value = hair_rgba    # (R, G, B, A)
bsdf.inputs["Roughness"].default_value = 0.75          # Matte
bsdf.inputs["Metalness"].default_value = 0.0           # Non-metal
bsdf.inputs["Specular IOR Level"].default_value = 1.5  # Default IOR
```

**Three.js Equivalent:**
```javascript
new THREE.MeshStandardMaterial({
    color: new THREE.Color(hair_rgba[0], hair_rgba[1], hair_rgba[2]),
    roughness: 0.75,
    metalness: 0.0,
    side: THREE.DoubleSide,  // Extra: render both sides
})
```

**Principled BSDF → MeshStandardMaterial Mapping:**
| BSDF Input | Default | Three.js Property |
|-----------|---------|-------------------|
| Base Color | (0.8, 0.8, 0.8) | color |
| Roughness | 0.5 | roughness |
| Metallic | 0.0 | metalness |
| Transmission | 0.0 | (not supported) |
| IOR | 1.45 | (fixed in Three.js) |

---

## F. SKELETON BINDING

### F.1 Blender Approach

**Simple Parenting/Constraints:**
```python
# hair_obj created in world space
hair_obj.location = (world_x, world_y, world_z)
hair_obj.rotation_euler = (rx, ry, rz)

# Constraint: Copy Transform from Head bone
constraint = hair_obj.constraints.new(type='COPY_TRANSFORMS')
constraint.target = armature
constraint.subtarget = 'Head'
```

**Result:** Hair position follows bone through constraint evaluation.

### F.2 Three.js Approach

**SkinnedMesh with Bone Parenting:**
```javascript
// Create skeleton
const skeleton = buildSkeleton(H);
const headBone = skeleton.bones[BONE_NAMES.indexOf('Head')];

// Create hair geometry & material
const hairGeo = buildHairGeometry(headRadius, style);
const hairMat = new THREE.MeshStandardMaterial({...});
const hairMesh = new THREE.Mesh(hairGeo, hairMat);

// Transform relative to bone frame
hairMesh.rotation.x = -Math.PI / 2;
hairMesh.position.set(0, headRadius * 5.5, -headRadius * 0.6);
hairMesh.scale.set(0.725, 0.725, 0.725);

// Add as child of head bone
headBone.add(hairMesh);
```

**Result:** Hair inherits all transforms from head bone automatically (world matrix multiplication).

**Advantages of Three.js Approach:**
- ✓ No constraint evaluation overhead
- ✓ Automatic synchronization with animation
- ✓ Works with any bone transform
- ✓ Compatible with game engine imports

---

## G. PERFORMANCE CHARACTERISTICS

### G.1 Face Count by Hair Style

```
Style       Cap  Extensions  Total  Vertices
────────────────────────────────────────────
buzzed       84      18        102     ~44
short        84      84        168     ~68
spiky       84      66        150     ~62
long        84     138        222     ~90
mohawk      84      68        152     ~65
ponytail    84      96        180     ~75
```

### G.2 Clothing Face Count (Approximate)

```
Type           Torso Verts  Legs Verts  Combined Faces
──────────────────────────────────────────────────────
short_sleeve   250         —           ~90
long_sleeve    300         —           ~110
v_neck         280         —           ~105
shorts         —           300         ~120
jeans          —           500         ~180
full_outfit    500         500         ~250
```

### G.3 Total Character Budget

```
Component      Faces   Vertices   Memory (MB)
─────────────────────────────────────────────
Body           6000    4000       ~0.5
Hair (short)   168     68         ~0.01
Eyes           32      32         ~0.01
Clothing       200     300        ~0.04
Skeleton       —       —          ~0.1 (bone data)
─────────────────────────────────
TOTAL          ~6400   ~4400      ~0.7
```

✓ **Fits easily in mobile memory budgets**

---

## H. VERTEX ATTRIBUTE LAYOUT

### H.1 Body Mesh Attributes

**Required for Skinning:**
```javascript
geometry.attributes.position  // [VEC3] float32
geometry.attributes.normal    // [VEC3] float32
geometry.attributes.uv        // [VEC2] float32
geometry.skinIndex            // [VEC4] uint8  (bone indices)
geometry.skinWeight           // [VEC4] float32 (blend weights)
```

**Usage in Vertex Shader:**
```glsl
#include <skinning_pars_vertex>

void main() {
    #include <begin_vertex>
    #include <skinning_vertex>
    #include <project_vertex>
}
```

### H.2 Hair Mesh Attributes (Minimal)

```javascript
geometry.attributes.position  // [VEC3] float32 (only required)
geometry.attributes.normal    // [VEC3] float32 (auto-computed)
// No UV, skinning, or other attributes
```

---

## I. ANIMATION DATA FLOW

**Skeleton → Animation System → Character Mesh:**

```
Animation Timeline (0–1 normalized)
         ↓
  Bone Transform Keyframes
  (position, quaternion, scale)
         ↓
  Skeleton Pose Matrix Update
  (world transforms computed)
         ↓
  Skinned Mesh Deformation
  (vertex positions transformed)
         ↓
  Cloth/Hair Deformation
  (inherit bone transforms)
         ↓
  Render
```

**All geometry components (body, hair, eyes, clothing) share single skeleton** → guaranteed synchronization.

---

**End of Appendix**

