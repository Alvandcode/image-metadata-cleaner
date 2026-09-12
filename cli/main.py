"""CLI entry-point for image-metadata-cleaner."""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

try:
    from cleaner.exif_cleaner import (
        MAX_DIMENSION,
        analyze_metadata,
        batch_clean,
        clean_metadata,
    )
except ImportError:  # running from a different CWD: add repo root to path
    import os as _os
    import sys as _sys

    _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from cleaner.exif_cleaner import (  # type: ignore
        MAX_DIMENSION,
        analyze_metadata,
        batch_clean,
        clean_metadata,
    )

__version__ = "0.2.0"

_RESIZE_RE = re.compile(r"^\s*(\d+)\s*[xX×*]\s*(\d+)\s*$")


def parse_resize(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    m = _RESIZE_RE.match(value)
    if not m:
        raise ValueError("Resize format invalid. Example: 800x600")
    w, h = int(m.group(1)), int(m.group(2))
    if w <= 0 or h <= 0:
        raise ValueError("Resize dimensions must be positive (e.g. 800x600)")
    if w > MAX_DIMENSION or h > MAX_DIMENSION:
        raise ValueError(f"Resize too large (max {MAX_DIMENSION}x{MAX_DIMENSION})")
    return (w, h)


def expand_inputs(pattern: str) -> list[str]:
    """Expand glob patterns robustly; return sorted unique existing files."""
    # Always try glob first (handles *, ?, [...], **).
    matches = glob.glob(pattern, recursive=True)
    if matches:
        files = sorted({m for m in matches if os.path.isfile(m)})
        if files:
            return files
    # Fallback: literal path.
    if os.path.isfile(pattern):
        return [pattern]
    return []


def _is_glob_pattern(s: str) -> bool:
    return any(c in s for c in ("*", "?", "["))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Image Metadata Cleaner — remove EXIF/GPS metadata from photos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            '  img-clean photo.jpg -o clean.jpg\n'
            '  img-clean "photos/*.jpg" -o cleaned/ --resize 1200x800\n'
            '  img-clean photo.jpg --analyze\n'
        ),
    )
    parser.add_argument("input", help="Input file or glob pattern (e.g. photo.jpg, \"photos/*.jpg\")")
    parser.add_argument("-o", "--output", default=None, help="Output file (single) or directory (batch)")
    parser.add_argument("--analyze", action="store_true", help="Only show metadata, do not clean")
    parser.add_argument("--resize", default=None, help="Resize, e.g. 800x600")
    parser.add_argument("--watermark", default=None, help="Watermark text")
    parser.add_argument("--quality", type=int, default=95, help="JPEG/WebP quality 1-100 (default 95)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output files")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-q", "--quiet", action="store_true", help="Minimal output")

    args = parser.parse_args(argv)

    if not (1 <= args.quality <= 100):
        print("Error: --quality must be 1..100", file=sys.stderr)
        return 2
    if args.watermark is not None and not args.watermark.strip():
        print("Error: --watermark must be non-empty", file=sys.stderr)
        return 2

    try:
        resize = parse_resize(args.resize)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    inputs = expand_inputs(args.input)
    if not inputs:
        print(f"Error: no files matched: {args.input}", file=sys.stderr)
        return 1

    # ---- analyze-only ----
    if args.analyze:
        code = 0
        for inp in inputs:
            result = analyze_metadata(inp)
            if not args.quiet:
                print(f"\nAnalysis: {inp}")
                print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
            if "error" in result:
                code = 1
        return code

    # ---- decide single vs batch ----
    output = args.output
    output_is_dir = False
    if output:
        # Explicit dir signals, trailing sep, existing dir, or multi-input.
        if output.endswith((os.sep, "/")) or os.path.isdir(output) or len(inputs) > 1 or _is_glob_pattern(args.input):
            # If output has an image extension and single input -> treat as file.
            _, ext = os.path.splitext(output)
            if len(inputs) == 1 and ext.lower() in (".jpg", ".jpeg", ".png", ".webp") and not os.path.isdir(output):
                output_is_dir = False
            else:
                output_is_dir = True
    else:
        output_is_dir = len(inputs) > 1

    try:
        if len(inputs) > 1 or output_is_dir:
            out_dir = output if output_is_dir else None
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            # Overwrite guard for batch.
            if not args.overwrite and out_dir:
                collisions = []
                for p in inputs:
                    base, ext = os.path.splitext(os.path.basename(p))
                    cand = os.path.join(out_dir, f"{base}_cleaned{ext}")
                    if os.path.exists(cand):
                        collisions.append(cand)
                if collisions:
                    print(
                        f"Error: {len(collisions)} output file(s) already exist. "
                        "Use --overwrite to replace. First: " + collisions[0],
                        file=sys.stderr,
                    )
                    return 1
            results = batch_clean(inputs, out_dir, resize, args.watermark, args.quality)
            ok = sum(1 for r in results if r.get("status") == "success")
            fail = len(results) - ok
            if not args.quiet:
                for r in results:
                    if r.get("status") == "success":
                        print(f"OK  {r['input']} -> {r['output']}")
                    else:
                        print(f"FAIL {r.get('input')}: {r.get('error')}", file=sys.stderr)
                print(f"Done: {ok}/{len(results)} succeeded" + (f", {fail} failed" if fail else ""))
            return 0 if fail == 0 else 1
        else:
            single_out = output
            if single_out and os.path.isdir(single_out):
                base, ext = os.path.splitext(os.path.basename(inputs[0]))
                single_out = os.path.join(single_out, f"{base}_cleaned{ext}")
            if single_out and os.path.exists(single_out) and not args.overwrite:
                print(f"Error: output exists: {single_out} (use --overwrite)", file=sys.stderr)
                return 1
            result = clean_metadata(inputs[0], single_out, resize, args.watermark, args.quality)
            if not args.quiet:
                print("Cleaning succeeded!")
                print(f"  input : {result['input']}")
                print(f"  output: {result['output']}")
                print(f"  removed {result.get('removed_count', len(result.get('removed', [])))} metadata field(s): {', '.join(result.get('removed', [])) or 'none'}")
                if result.get("resized"):
                    print("  resized: yes")
                if result.get("watermarked"):
                    print("  watermark: yes")
            return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
