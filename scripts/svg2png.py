#!/usr/bin/env python3
"""
This is a utility for creating presentable PNGs from a directory of SVGs.
The color of the SVGs will be inverted and a border added to maximize readability.

This is necessary because Discord does not allow embedding SVGs. The preferential 
style must be applied to a pre-rendered glyph.

You must install `cairosvg` and `lxml`. These are not provided in `./requirements.txt` 
because that file is intended for Github Actions.

Example use: 
python ./scripts/svg2png.py --directory ./sitelenpona/sitelen-seli-kiwen/
"""

# STL
import argparse
import logging
import os

import cairosvg
import lxml.etree

from utils import existing_directory

LOG = logging.getLogger()

BORDER_CSS = """path {
  fill: black;
  stroke: #CDCDCD;
  stroke-width: 1em;
}
"""
STYLE = lxml.etree.Element("style", type="text/css")
STYLE.text = BORDER_CSS


def svgname_to_pngname(name: str) -> str:
    return name[: name.rfind(".svg")] + ".png"


def main(argv: argparse.Namespace):
    LOG.setLevel(argv.log_level)
    svg_files = [f for f in os.listdir(argv.directory) if f.endswith(".svg")]
    # TODO: check type explicitly
    for svgname in svg_files:
        fullsvg = os.path.join(argv.directory, svgname)

        pngname = svgname_to_pngname(svgname)
        fullpng = os.path.join(argv.directory, pngname)

        svg_elem = lxml.etree.parse(fullsvg)
        root = svg_elem.getroot()
        root.insert(0, STYLE)

        svg = lxml.etree.tostring(svg_elem)

        cairosvg.svg2png(
            bytestring=svg,
            write_to=fullpng,
            negate_colors=True,
            output_width=256,
            output_height=256,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Script to convert a directory of SVGs to PNGs with some added style."
    )
    parser.add_argument(
        "--log-level",
        help="Set the log level",
        type=str.upper,
        dest="log_level",
        default="INFO",
        choices=["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    parser.add_argument(
        "--directory",
        help="Specify a directory of SVGs to be converted to PNGs",
        dest="directory",
        required=True,
        type=existing_directory,
    )
    ARGV = parser.parse_args()
    main(ARGV)
