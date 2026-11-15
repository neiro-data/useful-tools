# face-blur

Offline tool that blurs faces in an image, from a CLI or a local web UI. The YuNet model is bundled;
nothing goes over the network and the server binds to `127.0.0.1` only (unless `--host` is given).

## Resume

- Stack: Python >=3.12, uv, OpenCV (`opencv-python-headless`, YuNet via `cv2.FaceDetectorYN`), Pillow, Flask.
- Layout: `src/face_blur/` (`regions`, `detector`, `blur`, `imageio`, `pipeline`, `server`, `cli`,
  `static/` UI, `models/` ONNX + MIT licence), `tests/` with public-domain fixtures.
- Run: `uv sync`, then `uv run face-blur auto IN OUT` or `uv run face-blur serve`.
- Gate: `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest`.
- Stateless server: the browser re-sends the image with each request; no temp files. Output is
  re-encoded without metadata (EXIF stripped).

## Usage

```
uv run face-blur auto IN OUT [--method gaussian|pixelate|solid] [--strength 1-10] [--shape ellipse|rect]
                             [--padding 0.15] [--min-score 0.6] [--max-side 1280] [--quality 92]
                             [--boxes-json PATH]
uv run face-blur detect IN [--min-score S] [--max-side N]      # JSON boxes on stdout
uv run face-blur serve [--port 8765] [--host 127.0.0.1] [--no-browser]
```

`auto` takes the output format from the OUT extension (`.jpg`, `.png`, `.webp`), prints
`N faces blurred`, and exits 2 on bad arguments or unreadable input. With zero faces it still writes OUT
and prints a warning.

Web UI: faces are detected on load; click a box to toggle it, switch to Draw to add rectangles
(click a drawn rectangle in Select mode to delete it), then Preview and Download.

API: `POST /api/detect`, `/api/blur`, `/api/auto` (multipart `image`, optional JSON `params`);
each `/api/blur` region takes an optional `source` (`"auto"` or `"manual"`, default `"manual"`);
padding applies to ellipse and `"auto"` regions, so UI, CLI and `/api/auto` give the same result.
Errors are `{"error": "..."}` with 400/413/415 (500 for unexpected failures). Upload limit 25 MB, 40 MP.

## Privacy note

Gaussian blur at low strength can be partly reversed. For sensitive images use `--method solid`
(a flat fill) or a high strength. Tiny or profile faces may be missed: lower `--min-score` or draw
the region manually.

## Model

`src/face_blur/models/` holds YuNet (`face_detection_yunet_2023mar.onnx`, MIT, from
`opencv/opencv_zoo`) with its licence and pinned SHA-256. It is loaded from package resources.
