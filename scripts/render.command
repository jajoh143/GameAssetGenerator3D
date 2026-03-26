#!/bin/bash
cd /Users/jjohnson/GameAssetGenerator3D
/Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/run_preview.py 2>&1
echo ""
echo "=== Render complete! You can close this window. ==="
