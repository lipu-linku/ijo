#!/usr/bin/env python3

"""
This is a utility for dumping glyphs from a target font which implements ligatures.
You must install `fontforge`, `cairosvg`, and `lxml`.
These are not provided in `./requirements.txt` because that file is for Github Actions.

Example use:
python ./scripts/dump_font.py -f ./nasinsitelen/sitelenselikiwenasuki.ttf -d ./sitelenpona/sitelen-seli-kiwen/
"""

# STL
import argparse
import logging
import os

# PDM
import fontforge
import lxml.etree
from cairosvg.bounding_box import bounding_box_path
from cairosvg.parser import Node, Tree
from cairosvg.surface import SVGSurface

# LOCAL
from utils import configure_logger, download_json, existing_directory, existing_file

LOG = logging.getLogger("script")

USER_IS_LICENSED = 1
LOAD_ALL_IN_TTC = 4
NO_GUI = 16
KEEP_ALL_TABLES = 32
FLAGS = USER_IS_LICENSED | LOAD_ALL_IN_TTC | NO_GUI | KEEP_ALL_TABLES

SONA_WORDS = "https://api.linku.la/v1/words"
SANDBOX_WORDS = "https://api.linku.la/v1/sandbox"

IGNORABLE_SYMS = {
    "plus",
    "dash",
    "hyphen",
    "backslash",
    "asciicircum",
    "asterisk",
    "bracketleft",
    "bracketright",
    "parenleft",
    "parenright",
    "braceleft",
    "braceright",
    "period",
    "colon",
    # "space",
}
IGNORABLE_TABLES = {
    "Position",
    "Pair",
    # "Substitition",
    # "AltSubs",
    "MultSubs",
    # "Ligature",
}

VARIANT_NUMBERS = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "zero": "0",
}

words = download_json(SONA_WORDS)
sandbox = download_json(SANDBOX_WORDS)

NIMI_LINKU = {word_data["word"] for word_data in words.values()}
NIMI_KO = {word_data["word"] for word_data in sandbox.values()}
NIMI_ALE = NIMI_LINKU | NIMI_KO


def strip_space(ligature: tuple[str, ...]) -> tuple[str, ...]:
    # dupes will write to the same position
    if ligature[-1] == "space":
        return ligature[:-1]
    return ligature


def handle_variant(ligature: tuple[str, ...]) -> tuple[tuple[str, ...], str]:
    if ligature[-1] in VARIANT_NUMBERS:
        variant_suffix = "-" + VARIANT_NUMBERS[ligature[-1]]
        ligature = ligature[:-1]  # last is number
        return ligature, variant_suffix
    return ligature, ""


def get_path_bounding_box(
    svg_data: bytes,
) -> tuple[float, float, float, float]:
    tree = Tree(bytestring=svg_data)
    surface = SVGSurface(tree, None, 300)

    def find_path(node: Node) -> Node | None:
        if getattr(node, "tag", None) == "path":
            return node

        for child in getattr(node, "children", []):
            found = find_path(child)
            if found is not None:
                return found

        return None

    node = find_path(tree)
    if node is None:
        raise ValueError("No path element found in SVG")

    return bounding_box_path(surface=surface, node=node)


def correct_path_bounding_box(svg_file: str, pad_pct: float = 0.0):
    with open(svg_file, "rb") as f:
        svg_data = f.read()

    minx, miny, width, height = get_path_bounding_box(svg_data)

    new_minx = minx
    new_miny = miny
    new_maxx = minx + width
    new_maxy = miny + height

    svg_elem = lxml.etree.fromstring(svg_data)
    orig_minx, orig_miny, orig_w, orig_h = map(float, svg_elem.get("viewBox").split())
    orig_maxx = orig_minx + orig_w
    orig_maxy = orig_miny + orig_h

    if (
        new_minx >= orig_minx
        and new_miny >= orig_miny
        and new_maxx <= orig_maxx
        and new_maxy <= orig_maxy
    ):
        return

    # integer pad
    # minx -= pad_pct
    # miny -= pad_pct
    # width += pad_pct * 2
    # height += pad_pct * 2

    # percent pad
    pad_x = width * pad_pct / 2
    pad_y = height * pad_pct / 2
    minx -= pad_x
    miny -= pad_y
    width += pad_x * 2
    height += pad_y * 2

    svg_elem = lxml.etree.fromstring(svg_data)
    svg_elem.set("viewBox", f"{minx} {miny} {width} {height}")
    svg_elem.set("width", str(width))
    svg_elem.set("height", str(height))

    corrected_svg = lxml.etree.tostring(
        svg_elem,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8",
        doctype="""<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd" >""",
    )
    with open(svg_file, "wb") as f:
        _ = f.write(corrected_svg)
    return


def dumpable_glyphs(font: fontforge.font, dump_unknown: bool = False):
    for glyph in font.glyphs("encoding"):
        ligs: tuple[tuple[str, ...], ...] = glyph.getPosSub("*")
        for lig in ligs:
            if not len(lig):
                LOG.debug("Skipping due to blank: %s", lig)
                continue

            table, tabletype, *text = lig

            if tabletype in IGNORABLE_TABLES:
                LOG.debug("Skipping due to table: %s", lig)
                continue

            if set(text).intersection(IGNORABLE_SYMS):
                LOG.debug("Skipping due to symbol: %s", lig)
                continue

            text = strip_space(text)
            text, variant = handle_variant(text)

            word = "".join(text)
            if word not in NIMI_ALE and not dump_unknown:
                LOG.debug("Skipping due to unknown word: %s", lig)
                continue

            word = word + variant
            yield glyph, word, lig


def main(argv: argparse.Namespace):
    configure_logger("script", argv.log_level)

    font = fontforge.open(argv.font, FLAGS)
    for glyph, word, lig in dumpable_glyphs(font, argv.dump_unknown):
        filename = word + "." + argv.format
        output_file = os.path.join(argv.directory, filename)
        try:
            # NOTE: usetransform is set to avoid
            # https://github.com/fontforge/fontforge/issues/5695
            # could copy instead of 2x export, but i prefer consistent logic
            glyph.export(output_file, usetransform=True)
            LOG.info("Exported %s (%s)", output_file, lig[2:])
            if argv.format == "svg":
                correct_path_bounding_box(output_file, 0.05)
                LOG.debug("Corrected bounding box for %s", output_file)
        except RuntimeError as e:
            # literally anything could be wrong with the glyph
            LOG.warning("Couldn't export %s (%s): %s", filename, lig[2:], e)

        # WARNING: You CANNOT directly use the output. It MUST be hand-processed.
        # Different fonts use different variant numbers.
        # You may also need permission to commit (distribute) font glyphs. Check the license!


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script to dump glyphs from a font.")
    _ = parser.add_argument(
        "--log-level",
        "-l",
        help="Set the log level",
        type=str.upper,
        dest="log_level",
        default="INFO",
        choices=["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    _ = parser.add_argument(
        "--font",
        "-f",
        help="A font file to dump glyphs from",
        dest="font",
        required=True,
        type=existing_file,
    )
    _ = parser.add_argument(
        "--directory",
        "-d",
        help="A directory to dump glyphs to.",
        dest="directory",
        required=True,
        type=existing_directory,
    )
    _ = parser.add_argument(
        "--format",
        help="The format to dump glyps in.",
        dest="format",
        default="svg",
        choices=["svg", "pdf", "png", "bmp", "fig", "xbm", "eps"],
    )
    _ = parser.add_argument(
        "--dump-unknown",
        help="Whether to dump words unknown to Linku from the font.",
        dest="dump_unknown",
        action="store_true",
    )
    ARGV = parser.parse_args()
    main(ARGV)
