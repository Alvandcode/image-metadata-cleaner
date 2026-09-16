"""image-metadata-cleaner — privacy-first metadata removal.

Rebuilds pixel data into a fresh image instead of surgically deleting tags, so
no EXIF/GPS/ICC/XMP/comment chunk can survive. The input file is never touched.
"""

from .exif_cleaner import (
    MAX_DIMENSION,
    MAX_PIXELS,
    SUPPORTED_EXTENSIONS,
    SUPPORTED_FORMATS,
    add_watermark,
    analyze_metadata,
    batch_clean,
    clean_metadata,
    format_for_extension,
    has_rtl,
)

__version__ = "0.4.0"

__all__ = [
    "MAX_DIMENSION",
    "MAX_PIXELS",
    "SUPPORTED_EXTENSIONS",
    "SUPPORTED_FORMATS",
    "__version__",
    "add_watermark",
    "analyze_metadata",
    "batch_clean",
    "clean_metadata",
    "format_for_extension",
    "has_rtl",
]
