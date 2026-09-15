"""Example usage of image-metadata-cleaner (run as a script).

python examples/clean_example.py path/to/photo.jpg
"""

from __future__ import annotations

import os
import sys

from cleaner.exif_cleaner import analyze_metadata, clean_metadata


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    src = argv[0] if argv else "test.jpg"
    if not os.path.isfile(src):
        print(f"usage: python {os.path.basename(__file__)} <photo.jpg>")
        return 2

    # 1. Read-only report. `metadata` holds privacy-relevant chunks only;
    #    container plumbing (JFIF/DPI) is kept apart in `technical`.
    report = analyze_metadata(src)
    print("analyze:", report.get("error") or report["format"], report.get("size"))
    if report.get("has_gps"):
        gps = report["gps_decimal"]
        print(f"  !! GPS: {gps.get('lat')}, {gps.get('lon')}")
        print(f"  https://www.openstreetmap.org/?mlat={gps.get('lat')}&mlon={gps.get('lon')}")
    print(f"  has_metadata={report.get('has_metadata')} removed tags={list(report.get('exif') or {})}")

    # 2. Clean it. Portrait photos keep their real orientation, the colour
    #    profile can be preserved, and the result is verified by re-analysing
    #    the file we just wrote.
    result = clean_metadata(
        src,
        # output_path=None -> "<name>_cleaned.<ext>" next to the source
        resize=(1600, 1200),
        watermark_text="© علیرضا",
        opacity=0.4,
        watermark_position="bottom-right",
        auto_orient=True,
        keep_icc=False,  # set True to keep the embedded colour profile
        overwrite=True,  # required if the output file already exists
    )
    print("\nclean:")
    print(f"  output         : {result['output']} ({result['format']}, {result['frames']} frame(s))")
    print(f"  removed        : {result['removed_count']} field(s) -> {', '.join(result['removed'])}")
    print(f"  auto_oriented  : {result['auto_oriented']}")
    print(f"  verified clean : {not result['verified'].get('has_metadata')}")

    # 3. Batch (never raises; one status dict per file).
    #
    #    from cleaner.exif_cleaner import batch_clean
    #
    #    results = batch_clean(
    #        ["1.jpg", "2.jpg"],
    #        output_dir="cleaned",
    #        out_format="webp",      # optional conversion
    #        jobs=4,                 # parallel workers
    #        skip_existing=True,
    #        progress=lambda done, total, path: print(f"{done}/{total} {path}"),
    #    )
    #    for r in results:
    #        print(r["status"], r.get("output") or r.get("error"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
