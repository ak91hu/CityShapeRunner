# Free-text AI drawing pipeline

Unknown or compound shape descriptions use a bounded, provider-neutral drawing
pipeline. Built-in templates and text outlines still avoid unnecessary model
calls.

1. A strict `ShapeSpec` preserves subject, modifiers, pose, part hierarchy and
   three to six route-scale recognition cues.
2. Complexity and ambiguity select two to four competing candidates.
3. The generator emits `move`, `line`, cubic `curve` and `close` commands. Each
   contour interval names the recognition cue it represents.
4. The deterministic compiler rejects invalid coordinates, collapsed shapes,
   self-intersections, long inter-stroke transfers, stock-template duplicates
   and duplicate candidates. It also measures cue coverage.
5. Candidates are rendered to 256 px PNG thumbnails. When a different configured
   provider is available, it independently scores every cue, subject identity,
   silhouette and route readability. A local geometry review is used otherwise
   and is never presented as a semantic score.
6. Missing cues, wrong relations and geometry failures produce typed diagnostics
   for at most one targeted repair. Passing contour spans are preserved.
7. The chosen shape stores its spec, candidate count, generator identity and
   review metadata. The API exposes these fields and logs a structured
   `shape.ai.generated` event.

## Linked-image fast path

A public image URL uses a dedicated visual path instead of being interpreted
from its filename. SVG geometry is sampled for a deterministic fallback and
also rendered as a model-visible PNG. Other files are identified from their
contents with Pillow, not their extension. Every decodable raster is EXIF-
oriented, limited to 40 million source pixels, reduced to at most 1024 px on
either axis, flattened onto white, and encoded once as PNG. Animated or layered
inputs use their first rendered frame. Downloads remain limited to 5 MB and
private-network destinations are rejected.
The 64 most recent normalised URLs are cached per server process, so retrying
the same link avoids another download and decode; cached values are copied
before use.

The authoritative reference image, semantic `ShapeSpec`, and exactly two GPS-
art programs are handled in one strict-schema multimodal generation call. This
replaces the previous sequential image-analysis and geometry calls. If an
independent reviewer provider is configured, it receives the original image
before the candidate thumbnails so it can compare the generated silhouette
directly with the source. With only the OpenCode provider configured, the local
geometry review is used and no redundant second-provider call is made.

This follows OpenCode's documented image-normalisation model and image-capable
model metadata:

- <https://dev.opencode.ai/docs/config#image-attachments>
- <https://opencode.ai/v2/docs/models>
- <https://dev.opencode.ai/docs/zen>

The accepted raster set is the set Pillow can decode in the deployed build,
which is intentionally broader than a fixed PNG/JPEG/WebP allowlist:
<https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html>.
Pillow 12 also officially supports Python 3.14:
<https://pillow.readthedocs.io/en/stable/installation/python-support.html>.

Run the multilingual benchmark without street-routing calls:

```powershell
python scripts/benchmark_ai_shapes.py --output ai-shape-report.json
```

For a genuinely independent visual review, configure at least two providers in
`LLM_FALLBACK`. The generator's provider is excluded from the reviewer call.
Use `OPENAI_MODEL`, `ANTHROPIC_MODEL`, `OPENCODE_MODEL`, or `OLLAMA_MODEL` when
overriding a fallback provider's default model; `LLM_MODEL` applies to the
first provider in the resolved primary/fallback order.
`AI_SHAPE_VERIFIER_ENABLED=false` disables that call. Candidate count and the
semantic repair threshold are controlled by `AI_SHAPE_MAX_CANDIDATES` and
`AI_SHAPE_MIN_SEMANTIC_SCORE`.
