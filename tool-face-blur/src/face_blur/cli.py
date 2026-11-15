"""Command line interface."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import blur, imageio, pipeline, server

_EXT_FORMATS = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".webp": "webp"}


def _score(value: str) -> float:
    number = float(value)
    if not 0 <= number <= 1:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return number


def _positive(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be > 0")
    return number


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="face-blur", description="Blur faces in images offline.")
    sub = parser.add_subparsers(dest="command", required=True)

    auto = sub.add_parser("auto", help="detect and blur all faces")
    auto.add_argument("input", type=Path)
    auto.add_argument("output", type=Path)
    auto.add_argument("--method", choices=blur.METHODS, default="gaussian")
    auto.add_argument("--strength", type=int, choices=range(1, 11), metavar="1-10", default=5)
    auto.add_argument("--shape", choices=("ellipse", "rect"), default="ellipse")
    auto.add_argument("--padding", type=float, default=0.15)
    auto.add_argument("--min-score", type=_score, default=None)
    auto.add_argument("--max-side", type=_positive, default=None)
    auto.add_argument("--quality", type=int, default=92)
    auto.add_argument("--boxes-json", type=Path, default=None, help="write the used boxes here")

    det = sub.add_parser("detect", help="print detected face boxes as JSON")
    det.add_argument("input", type=Path)
    det.add_argument("--min-score", type=_score, default=None)
    det.add_argument("--max-side", type=_positive, default=None)

    srv = sub.add_parser("serve", help="start the local web UI")
    srv.add_argument("--port", type=int, default=8765)
    srv.add_argument("--host", default=server.DEFAULT_HOST)
    srv.add_argument("--no-browser", action="store_true")
    return parser


def _fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 2


def _cmd_auto(args: argparse.Namespace) -> int:
    fmt = _EXT_FORMATS.get(args.output.suffix.lower())
    if fmt is None:
        return _fail("output extension must be one of " + ", ".join(_EXT_FORMATS))
    try:
        opts = pipeline.AutoOptions(
            method=args.method,
            strength=args.strength,
            shape=args.shape,
            padding=args.padding,
            min_score=args.min_score,
            max_side=args.max_side,
        )
        rgb = imageio.load_bytes(args.input.read_bytes())
        out, regions = pipeline.auto_blur(rgb, opts)
        data = imageio.encode(out, fmt, args.quality)
    except (OSError, ValueError) as exc:
        return _fail(str(exc))
    args.output.write_bytes(data)
    if args.boxes_json is not None:
        args.boxes_json.write_text(json.dumps([r.to_dict() for r in regions], indent=2))
    if not regions:
        print("warning: no faces found; output written unchanged", file=sys.stderr)
    print(f"{len(regions)} faces blurred")
    return 0


def _cmd_detect(args: argparse.Namespace) -> int:
    try:
        rgb = imageio.load_bytes(args.input.read_bytes())
    except (OSError, ValueError) as exc:
        return _fail(str(exc))
    faces = pipeline.detect(rgb, args.min_score, args.max_side)
    payload = {
        "width": int(rgb.shape[1]),
        "height": int(rgb.shape[0]),
        "faces": [
            {"id": i, "x": f.x, "y": f.y, "w": f.w, "h": f.h, "score": f.score}
            for i, f in enumerate(faces)
        ],
    }
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    if args.host != server.DEFAULT_HOST:
        print(
            f"warning: binding to {args.host} exposes the tool beyond this machine",
            file=sys.stderr,
        )
    server.run(args.host, args.port, open_browser=not args.no_browser)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point; returns the process exit code."""
    args = _build_parser().parse_args(argv)
    handlers = {"auto": _cmd_auto, "detect": _cmd_detect, "serve": _cmd_serve}
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
