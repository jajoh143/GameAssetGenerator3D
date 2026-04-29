"""Worker script: runs *inside* the TRELLIS.2 conda env.

Reads a JSON job spec from stdin, generates a mesh, writes a GLB.
Imports TRELLIS.2 modules in-process and invokes the public pipeline.

Job spec:
    {"image": "...", "output": "...", "model_id": "...", "resolution": 1024}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    job = json.loads(sys.stdin.read())

    image_path = Path(job["image"])
    output_path = Path(job["output"])
    model_id = job.get("model_id", "microsoft/TRELLIS.2-4B")
    resolution = int(job.get("resolution", 1024))

    from PIL import Image
    from trellis2.pipelines import Trellis2ImageTo3DPipeline

    pipeline = Trellis2ImageTo3DPipeline.from_pretrained(model_id)
    pipeline.cuda()

    image = Image.open(image_path).convert("RGBA")
    mesh = pipeline.run(image, resolution=resolution)[0]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(output_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
