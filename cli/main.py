"""Command line interface for image-metadata-cleaner.

Entry point: ``img-clean`` (console script) or ``python -m cli.main``.
The console script wraps ``main()`` in ``sys.exit`` so the process exit code is
real — CI and shell ``&&`` chains can rely on it.
"""

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
        SUPPORTED_EXTENSIONS,
        analyze_metadata,
        batch_clean,
        clean_metadata,
    )
except ImportError:  # running from a different CWD: add repo root to path
    _sys = sys
    _sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from cleaner.exif_cleaner import (  # type: ignore
        MAX_DIMENSION,
        SUPPORTED_EXTENSIONS,
        analyze_metadata,
        batch_clean,
        clean_metadata,
    )

# Re-exported from the package so the CLI, the wheel metadata and a release tag
# can never disagree again.
from cleaner import __version__

_RESIZE_RE = re.compile(r"^\s*(\d+)\s*[xX×*]\s*(\d+)\s*$")
_CLEANED_RE = re.compile(r"_cleaned$", re.IGNORECASE)

# Exit codes (documented in README)
EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
EXIT_INTERRUPT = 130


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


def _is_cleaned_output(path: str) -> bool:
    """True for `*_cleaned.jpg` — our own output naming scheme."""
    base, ext = os.path.splitext(os.path.basename(path))
    return bool(_CLEANED_RE.search(base)) and ext.lower() in SUPPORTED_EXTENSIONS


def expand_inputs(pattern: str, *, recursive: bool = True, skip_cleaned: bool = True) -> list[str]:
    """Expand a path, glob pattern or directory into a sorted list of files.

    Files that match our own ``*_cleaned.<ext>`` output naming are skipped for
    glob/directory input, so running the same command twice cannot feed the
    second run its own output (which used to grow files exponentially).
    """
    pattern = os.path.expanduser(pattern)
    matches: list[str] = []

    if os.path.isdir(pattern):
        walker = os.walk(pattern) if recursive else [(pattern, [], os.listdir(pattern))]
        for root, _dirs, files in walker:
            for name in files:
                matches.append(os.path.join(root, name))
    else:
        matches = glob.glob(pattern, recursive=recursive)
        if not matches and os.path.isfile(pattern):
            matches = [pattern]

    files = sorted({os.path.normpath(m) for m in matches if os.path.isfile(m)})
    if skip_cleaned:
        files = [f for f in files if not _is_cleaned_output(f)]
    return files


def expected_output(path: str, out_dir: str | None, forced_ext: str | None = None) -> str:
    """Where will ``path`` land? Mirrors the naming used by batch_clean()."""
    base, ext = os.path.splitext(os.path.basename(path))
    if forced_ext:
        ext = forced_ext
    elif ext.lower() not in SUPPORTED_EXTENSIONS:
        ext = ".jpg"
    name = f"{base}_cleaned{ext}"
    return os.path.join(out_dir, name) if out_dir else os.path.join(os.path.dirname(path) or ".", name)


def resolve_output(
    inputs: list[str], output: str | None, used_glob: bool, input_is_dir: bool = False
) -> tuple[str | None, bool]:
    """Decide whether ``-o`` is a file or a directory. Returns (path, is_dir).

    The old heuristic treated *any* ``-o`` without an image extension as a
    directory, so ``img-clean photo.jpg -o newdir`` silently created
    ``newdir/photo_cleaned.jpg`` even though the user asked for a file called
    ``newdir``. The rules are now explicit:

    * directory input, glob input or more than one file -> directory
    * trailing separator, or a path that already is a directory -> directory
    * otherwise ``-o`` is taken literally as the output *file*
    """
    if output is None:
        return None, len(inputs) > 1

    expanded = os.path.normpath(os.path.expanduser(output))
    if output.endswith(("/", os.sep, "\\")) or os.path.isdir(expanded):
        return expanded, True
    if input_is_dir or used_glob or len(inputs) > 1:
        return expanded, True
    return expanded, False


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="img-clean",
        description="Image Metadata Cleaner — remove EXIF/GPS metadata from photos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  img-clean photo.jpg -o clean.jpg\n"
            "  img-clean photo.jpg -o newdir/                 # directory\n"
            '  img-clean "photos/*.jpg" -o cleaned/ --resize 1200x800\n'
            "  img-clean photos/ -o cleaned/ --format webp --jobs 4 --progress\n"
            "  img-clean photo.jpg --analyze --json\n"
            "\nexit codes: 0 ok | 1 processing failure | 2 usage error | 130 interrupted\n"
        ),
    )
    parser.add_argument(
        "input",
        nargs="+",
        help="Input file(s), directory or glob pattern(s)",
    )
    parser.add_argument("-o", "--output", default=None, help="Output file (single input) or directory (many)")
    parser.add_argument("--analyze", action="store_true", help="Only show metadata, do not modify anything")
    parser.add_argument(
        "--resize",
        default=None,
        metavar="WxH",
        help="Fit inside WxH, keeping the aspect ratio (never enlarges), e.g. 800x600",
    )
    parser.add_argument("--watermark", default=None, help="Watermark text (RTL/Persian supported)")
    parser.add_argument("--opacity", type=float, default=0.35, help="Watermark opacity 0-1 (default 0.35)")
    parser.add_argument(
        "--watermark-position",
        default="bottom-right",
        choices=[
            "bottom-right",
            "bottom-left",
            "bottom-center",
            "top-right",
            "top-left",
            "top-center",
            "center",
        ],
        help="Watermark placement (default bottom-right)",
    )
    parser.add_argument("--quality", type=int, default=95, help="JPEG/WebP quality 1-100 (default 95)")
    parser.add_argument(
        "--format",
        default=None,
        dest="out_format",
        help="Force output format/extension, e.g. png (converts JPG -> PNG)",
    )
    parser.add_argument("--keep-icc", action="store_true", help="Keep the embedded ICC colour profile")
    parser.add_argument("--no-auto-orient", action="store_true", help="Do not bake EXIF orientation into pixels")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output files")
    parser.add_argument("--skip-existing", action="store_true", help="Skip files whose output already exists")
    parser.add_argument("--jobs", type=int, default=1, help="Parallel workers for batch mode (default 1)")
    parser.add_argument("--progress", action="store_true", help="Print batch progress to stderr")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Machine readable JSON on stdout")
    parser.add_argument("--no-recursive", action="store_true", help="Do not descend into sub-directories")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-q", "--quiet", action="store_true", help="Minimal output")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    force_ext = None
    if args.out_format:
        force_ext = "." + str(args.out_format).lstrip(".").lower()
        if force_ext not in SUPPORTED_EXTENSIONS:
            print(
                f"Error: unsupported --format '{args.out_format}'. "
                f"Supported: {', '.join(sorted(set(SUPPORTED_EXTENSIONS)))}",
                file=sys.stderr,
            )
            return EXIT_USAGE

    if not (1 <= args.quality <= 100):
        print("Error: --quality must be 1..100", file=sys.stderr)
        return EXIT_USAGE
    if not (0.0 < args.opacity <= 1.0):
        print("Error: --opacity must be in (0, 1]", file=sys.stderr)
        return EXIT_USAGE
    if args.watermark is not None and not args.watermark.strip():
        print("Error: --watermark must be non-empty", file=sys.stderr)
        return EXIT_USAGE
    if args.jobs < 1:
        print("Error: --jobs must be >= 1", file=sys.stderr)
        return EXIT_USAGE

    try:
        resize = parse_resize(args.resize)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_USAGE

    patterns: list[str] = list(args.input)
    used_glob = any(_is_glob(p) for p in patterns)
    input_is_dir = any(os.path.isdir(os.path.expanduser(p)) for p in patterns)
    inputs: list[str] = []
    try:
        for pattern in patterns:
            for found in expand_inputs(pattern, recursive=not args.no_recursive):
                if found not in inputs:
                    inputs.append(found)
    except OSError as e:
        print(f"Error: cannot read {patterns[0]}: {e}", file=sys.stderr)
        return EXIT_FAILURE
    if not inputs:
        print(f"Error: no files matched: {' '.join(patterns)}", file=sys.stderr)
        return EXIT_FAILURE

    # ---------------------------------------------------------------- analyze
    if args.analyze:
        code = EXIT_OK
        reports = []
        for inp in inputs:
            result = analyze_metadata(inp)
            reports.append(result)
            if "error" in result:
                code = EXIT_FAILURE
            if args.as_json:
                continue
            if not args.quiet:
                print(f"\nAnalysis: {inp}")
                print(_format_analysis(result))
        if args.as_json:
            payload = reports[0] if len(reports) == 1 else {"results": reports}
            json.dump(payload, sys.stdout, indent=2, ensure_ascii=False, default=str)
            sys.stdout.write("\n")
        return code

    # ------------------------------------------------------- output resolution
    output, output_is_dir = resolve_output(inputs, args.output, used_glob, input_is_dir)
    if output_is_dir and output:
        try:
            os.makedirs(output, exist_ok=True)
        except OSError as e:
            print(f"Error: cannot create output directory {output}: {e}", file=sys.stderr)
            return EXIT_USAGE

    single_file_mode = len(inputs) == 1 and not output_is_dir
    if single_file_mode and output and os.path.isdir(output):
        output = os.path.join(output, os.path.basename(expected_output(inputs[0], None, force_ext)))

    # -------------------------------------------------------- collision guard
    # Applies to batch-with-`-o` AND batch-without-`-o` (writes next to source).
    if not single_file_mode and not args.overwrite and not args.skip_existing:
        out_dir = output if output_is_dir else None
        collisions = [expected_output(p, out_dir, force_ext) for p in inputs]
        collisions = [c for c in collisions if os.path.exists(c)]
        if collisions:
            print(
                f"Error: {len(collisions)} output file(s) already exist. "
                "Use --overwrite to replace or --skip-existing to skip. First: " + collisions[0],
                file=sys.stderr,
            )
            return EXIT_FAILURE
    if single_file_mode and output and os.path.exists(output) and not args.overwrite:
        if args.skip_existing:
            if args.as_json:
                json.dump(
                    {"status": "skipped", "input": inputs[0], "output": output},
                    sys.stdout,
                    ensure_ascii=False,
                )
                sys.stdout.write("\n")
            elif not args.quiet:
                print(f"SKIP {inputs[0]} (output exists)")
            return EXIT_OK
        print(f"Error: output exists: {output} (use --overwrite or --skip-existing)", file=sys.stderr)
        return EXIT_FAILURE

    # `-o name --format png` should produce name.png rather than an
    # extension-less file that no viewer will open.
    if single_file_mode and output and force_ext and not os.path.splitext(output)[1]:
        output = output + force_ext

    common = {
        "auto_orient": not args.no_auto_orient,
        "keep_icc": args.keep_icc,
        "opacity": args.opacity,
        "watermark_position": args.watermark_position,
    }

    def _progress(done: int, total: int, path: str) -> None:
        if args.progress and not args.quiet:
            sys.stderr.write(f"\r[{done}/{total}] {os.path.basename(path)}")
            sys.stderr.flush()

    try:
        # ------------------------------------------------- single-file mode ---
        if single_file_mode:
            try:
                result = clean_metadata(
                    inputs[0],
                    output,
                    resize,
                    args.watermark,
                    args.quality,
                    overwrite=args.overwrite,
                    **common,
                )
            except FileExistsError:
                if args.skip_existing:
                    if args.as_json:
                        json.dump(
                            {"status": "skipped", "input": inputs[0], "output": output}, sys.stdout, ensure_ascii=False
                        )
                        sys.stdout.write("\n")
                    elif not args.quiet:
                        print(f"SKIP {inputs[0]} (output exists)")
                    return EXIT_OK
                raise
            code = EXIT_OK if not result.get("verified", {}).get("has_metadata") else EXIT_FAILURE
            if args.as_json:
                json.dump(result, sys.stdout, indent=2, ensure_ascii=False, default=str)
                sys.stdout.write("\n")
            elif not args.quiet:
                print("Cleaning succeeded!")
                print(f"  input : {result['input']}")
                print(f"  output: {result['output']}")
                print(f"  format: {result['original_format']} -> {result['format']}")
                print(
                    f"  removed {result['removed_count']} metadata field(s): "
                    + (", ".join(result["removed"]) or "none")
                )
                if result.get("kept"):
                    print(f"  kept  : {', '.join(result['kept'])} (colour profile)")
                if result.get("auto_oriented"):
                    print("  orientation: baked into pixels")
                if result.get("is_animated"):
                    print(f"  frames: {result['frames']} (animation preserved)")
                if result.get("resized"):
                    print("  resized: yes")
                if result.get("watermarked"):
                    print("  watermark: yes")
                _print_verification(result)
            return code

        # -------------------------------------------------- batch mode --------
        results = batch_clean(
            inputs,
            output if output_is_dir else None,
            resize,
            args.watermark,
            args.quality,
            overwrite=args.overwrite,
            out_format=args.out_format,
            jobs=args.jobs,
            skip_existing=args.skip_existing,
            progress=_progress if (args.progress and not args.quiet) else None,
            **common,
        )
        if args.progress and not args.quiet:
            sys.stderr.write("\n")

        ok = sum(1 for r in results if r.get("status") == "success")
        skipped = sum(1 for r in results if r.get("status") == "skipped")
        fail = len(results) - ok - skipped
        dirty = [r for r in results if r.get("status") == "success" and r.get("verified", {}).get("has_metadata")]

        if args.as_json:
            json.dump(
                {
                    "total": len(results),
                    "succeeded": ok,
                    "skipped": skipped,
                    "failed": fail,
                    "dirty": [r["output"] for r in dirty],
                    "results": results,
                },
                sys.stdout,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
            sys.stdout.write("\n")
        elif not args.quiet:
            for r in results:
                if r.get("status") == "success":
                    mark = "OK  " if not r.get("verified", {}).get("has_metadata") else "WARN"
                    print(f"{mark} {r['input']} -> {r['output']}")
                elif r.get("status") == "skipped":
                    print(f"SKIP {r['input']} (output exists)")
                else:
                    print(f"FAIL {r.get('input')}: {r.get('error')}", file=sys.stderr)
            summary = f"Done: {ok}/{len(results)} succeeded"
            if skipped:
                summary += f", {skipped} skipped"
            if fail:
                summary += f", {fail} failed"
            if dirty:
                summary += f", {len(dirty)} still contain metadata (see WARN lines)"
            print(summary)

        if dirty:
            return EXIT_FAILURE
        return EXIT_OK if fail == 0 else EXIT_FAILURE

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_FAILURE
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_USAGE
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return EXIT_INTERRUPT
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)
        return EXIT_FAILURE


def _print_verification(result: dict) -> None:
    verified = result.get("verified") or {}
    if verified.get("has_metadata"):
        print("  verify: WARNING — output still contains: " + ", ".join(verified.get("remaining", [])))
    elif verified:
        print("  verify: clean (re-analysed the output file, nothing found)")


def _format_analysis(result: dict) -> str:
    """Human friendly analyze output, with a loud GPS block."""
    if "error" in result:
        return json.dumps(result, indent=2, ensure_ascii=False, default=str)
    lines = []
    meta = result.get("metadata") or {}
    tech = result.get("technical") or {}
    if result.get("has_gps") and result.get("gps_decimal"):
        g = result["gps_decimal"]
        lines.append(f"  !! GPS LOCATION FOUND: {g.get('lat')}, {g.get('lon')}")
        lines.append(
            f"     https://www.openstreetmap.org/?mlat={g.get('lat')}&mlon={g.get('lon')}#map=16/{g.get('lat')}/{g.get('lon')}"
        )
    lines.append(f"  format   : {result.get('format')}  size: {result.get('size')}  mode: {result.get('mode')}")
    if result.get("is_animated"):
        lines.append(f"  animated : yes ({result.get('frames')} frames)")
    size = result.get("file_size")
    if size is not None:
        lines.append(f"  file size: {size} bytes")
    lines.append(f"  HAS METADATA: {result.get('has_metadata')}")
    if meta.get("exif"):
        lines.append("  EXIF:")
        for k, v in meta["exif"].items():
            lines.append(f"    - {k}: {v}")
    if meta.get("gps"):
        lines.append("  GPS:")
        for k, v in meta["gps"].items():
            lines.append(f"    - {k}: {v}")
    for key, value in meta.items():
        if key in ("exif", "gps"):
            continue
        lines.append(f"  {key}: {value}")
    if tech:
        lines.append("  technical (harmless container headers):")
        for k, v in tech.items():
            lines.append(f"    - {k}: {_truncate(v)}")
    if not meta:
        lines.append("  no privacy-relevant metadata found")
    return "\n".join(lines)


def _truncate(value: object, limit: int = 60) -> str:
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "…"


def _is_glob(value: str) -> bool:
    return any(c in value for c in ("*", "?", "["))


def cli() -> None:
    """Console-script wrapper: turn main()'s return value into a real exit code.

    ``[project.scripts]`` ignores return values, so ``img-clean`` used to always
    exit 0 even when every file failed.
    """
    sys.exit(main())


if __name__ == "__main__":
    raise SystemExit(main())
