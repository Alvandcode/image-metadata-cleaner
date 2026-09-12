"""Example usage of image-metadata-cleaner (run as script, not on import)."""

from cleaner.exif_cleaner import analyze_metadata, batch_clean, clean_metadata


def main() -> None:
    src = "test.jpg"
    dst = "test_cleaned.jpg"

    print("Analyze:", analyze_metadata(src))
    result = clean_metadata(src, dst, resize=(1200, 800), watermark_text="© AlvandCode")
    print("Clean:", result)

    # Batch example:
    # results = batch_clean(["1.jpg", "2.jpg"], output_dir="cleaned")
    # print(results)


if __name__ == "__main__":
    main()
