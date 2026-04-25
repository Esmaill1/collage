#!/usr/bin/env python3
"""Saliency-Aware Collage Generator — Script Entry Point.

Usage:
    python main.py --input_dir ./photos --output_file collage.png [--debug]

See `python main.py --help` for all options.
"""

import sys

from collage_generator.cli import run

if __name__ == "__main__":
    sys.exit(run())
