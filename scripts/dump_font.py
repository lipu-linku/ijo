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
import re
import sys
from math import ceil, floor

# PDM
import fontforge
import lxml.etree
import numpy as np
from cairosvg.bounding_box import bounding_box_path
from cairosvg.parser import Node, Tree
from cairosvg.surface import SVGSurface
from svgpathtools import Path, parse_path
from svgpathtools.path import transform as svg_transform

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.append(SCRIPT_DIR)


from ssk20260216 import SSK_MAP
from utils import configure_logger, download_json, existing_directory, existing_file

LOG = logging.getLogger("script")

USER_IS_LICENSED = 1
LOAD_ALL_IN_TTC = 4
NO_GUI = 16
KEEP_ALL_TABLES = 32
FLAGS = USER_IS_LICENSED | LOAD_ALL_IN_TTC | NO_GUI | KEEP_ALL_TABLES

SONA_WORDS = "https://api.linku.la/v1/words"
SANDBOX_WORDS = "https://api.linku.la/v1/sandbox"

IGNORABLE_TABLES = {
    "Position",
    "Pair",
    # "Substitition",
    # "AltSubs",
    "MultSubs",
    # "Ligature",
}

IGNORABLE_SYMBOLS = {
    "plus": "+",
    "dash": "-",  # TODO
    "hyphen": "-",  # TODO
    "backslash": "\\",
    "bracketleft": "[",
    "bracketright": "]",
    "parenleft": "(",
    "parenright": ")",
    "braceleft": "{",
    "braceright": "}",
}

SYMBOL_MAP = {
    "plus": "+",
    "dash": "-",  # TODO
    "hyphen": "-",  # TODO
    "backslash": "\\",
    "asciicircum": "",  # TODO
    "asterisk": "*",
    "bracketleft": "[",
    "bracketright": "]",
    "parenleft": "(",
    "parenright": ")",
    "braceleft": "{",
    "braceright": "}",
    "period": ".",
    "colon": ":",
    "semicolon": ";",
    "question": "?",
    "exclam": "!",
    "space": " ",
}


VARIANT_MAP = {
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


Matrix = tuple[float, float, float, float, float, float]


def strip_space(ligature: tuple[str, ...]) -> tuple[str, ...]:
    # dupes will write to the same position
    if ligature[-1] == "space":
        return ligature[:-1]
    return ligature


def handle_variant(
    ligature: tuple[str, ...],
    joiner: str = "",
) -> tuple[tuple[str, ...], str]:
    if ligature[-1] in VARIANT_MAP:
        variant_suffix = joiner + VARIANT_MAP[ligature[-1]]
        ligature = ligature[:-1]  # last is number
        return ligature, variant_suffix
    return ligature, ""


def subst_syms(
    ligature: tuple[str, ...],
    joiner: str = "",
) -> tuple[str, ...]:
    return tuple(SYMBOL_MAP.get(item, item) for item in ligature)


def get_transform_matrix(transform: str) -> Matrix:
    match = re.search(r"matrix\(([^)]+)\)", transform)
    if not match:
        raise ValueError("Only matrix() transforms are supported")

    values = list(map(float, match.group(1).replace(",", " ").split()))
    if len(values) != 6:
        raise ValueError("Matrix must have exactly 6 values")

    return tuple(values)


def _apply_matrix_to_path(path: Path, matrix) -> Path:
    a, b, c, d, e, f = matrix
    tf = np.array(
        [
            [a, c, e],
            [b, d, f],
            [0, 0, 1],
        ]
    )
    return svg_transform(path, tf)


def bake_transform(svg_data: bytes) -> bytes:
    parser = lxml.etree.XMLParser(remove_blank_text=True)
    root = lxml.etree.fromstring(svg_data, parser)

    nsmap = {"svg": root.nsmap.get(None)} if None in root.nsmap else None

    groups = (
        root.xpath(".//svg:g[@transform]", namespaces=nsmap)
        if nsmap
        else root.xpath(".//g[@transform]")
    )

    for g in groups:
        transform = g.attrib.get("transform")
        if not transform or "matrix" not in transform:
            continue

        matrix = get_transform_matrix(transform)

        paths = (
            g.xpath(".//svg:path", namespaces=nsmap) if nsmap else g.xpath(".//path")
        )
        for path_elem in paths:
            d = path_elem.attrib.get("d")
            if not d:
                continue

            parsed = parse_path(d)
            transformed = _apply_matrix_to_path(parsed, matrix)
            path_elem.attrib["d"] = transformed.d()

        # Remove transform attribute
        del g.attrib["transform"]

    return lxml.etree.tostring(
        root,
        pretty_print=True,
        xml_declaration=True,
        encoding="utf-8",
    )


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


def fix_svg_viewbox(svg_file: str, pad_pct: float = 0.0, even_sides=False):
    with open(svg_file, "rb") as f:
        svg_data = f.read()

    svg_data = bake_transform(svg_data)
    min_x, min_y, width, height = get_path_bounding_box(svg_data)

    if even_sides:
        width = max(width, height)
        height = width

    pad_x = width * pad_pct  # / 2
    pad_y = height * pad_pct  # / 2

    min_x -= pad_x
    min_y -= pad_y
    width += pad_x * 2
    height += pad_y * 2

    min_x = floor(min_x)
    min_y = floor(min_y)
    width = ceil(width)
    height = ceil(height)

    svg_elem = lxml.etree.fromstring(svg_data)
    svg_elem.set("viewBox", f"{min_x} {min_y} {width} {height}")

    # just in case these values are present; we only want viewBox
    svg_elem.set("width", str(width))
    svg_elem.set("height", str(height))
    svg_elem.attrib.pop("width")
    svg_elem.attrib.pop("height")

    corrected_svg = lxml.etree.tostring(
        svg_elem,
        # pretty_print=False,
        # xml_declaration=True,
        # encoding="UTF-8",
        # doctype="""<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd" >""",
    )
    with open(svg_file, "wb") as f:
        _ = f.write(corrected_svg)
    return


def dumpable_glyphs(
    font: fontforge.font,
    dump_unknown: bool = False,
    as_typed: bool = False,
):
    joiner = "-"
    if as_typed:
        joiner = ""

    for glyph in font.glyphs("encoding"):
        ligs: tuple[tuple[str, ...], ...] = glyph.getPosSub("*")
        for lig_raw in ligs:
            if not len(lig_raw):
                LOG.debug("Skipping due to blank: %s", lig_raw)
                continue

            table, tabletype, *text = lig_raw

            if tabletype in IGNORABLE_TABLES:
                LOG.debug("Skipping due to table: %s", lig_raw)
                continue

            if set(text).intersection(IGNORABLE_SYMBOLS.keys()):
                LOG.debug("Skipping due to symbol: %s", lig_raw)
                continue

            text = strip_space(text)
            if not text:
                LOG.debug("Skipping due to space-only lig: %s", text)
            text, variant = handle_variant(text)
            text = subst_syms(text)

            word = "".join(text)
            if not (dump_unknown or word in NIMI_ALE):
                LOG.debug("Skipping due to unknown word: %s", word)
                continue

            name = word
            lig = word
            if variant:
                name = word + joiner + variant
                lig = word + variant

            yield glyph, word, name, lig, lig_raw


def dump_glyph(
    glyph: fontforge.glyph,
    name: str,
    format: str,
    output_dir: str,
) -> bool:
    filename = name + "." + format
    output_file = os.path.join(output_dir, filename)
    try:
        # NOTE: if some glyphs fail to export, update fontforge to the latest commit
        # you _can_ set usetransform=True but this, per the name,
        # adds a transform to the svg which breaks bounding box calc
        # see https://github.com/fontforge/fontforge/issues/5695

        glyph.export(output_file, usetransform=False)
        LOG.info("Exported %s", output_file)

        if format == "svg":
            try:
                fix_svg_viewbox(output_file, 0.05)
                LOG.debug("Fixed viewbox in %s (%s)", output_file, name)
            except ValueError:
                glyph.export(output_file, usetransform=True)
                fix_svg_viewbox(output_file, 0.05)
                LOG.info("Fixed viewbox %s (%s) with transform", output_file, name)

        return True
    except RuntimeError as e:
        # literally anything could be wrong with the glyph
        LOG.warning("Couldn't export %s (%s): %s", filename, name, e)
    return False


def dump_font(
    font_file: str,
    format: str,
    output_dir: str,
    dump_unknown: bool = False,
    target_ligature: str = "",
):
    font = fontforge.open(font_file, FLAGS)
    glyph_map = dict()
    for glyph, word, name, lig, lig_raw in dumpable_glyphs(
        font,
        dump_unknown,
        as_typed=False,
    ):
        if target_ligature:
            if lig == target_ligature:
                dump_glyph(glyph, name, format, output_dir)
                break
        else:
            # dump_glyph(glyph, name, format, output_dir)
            glyph_map[lig] = glyph

    for glyph_id, ligature in SSK_MAP.items():
        if ligature and (ligature in glyph_map):
            # LOG.info("Dumping %s (%s)", glyph_id, ligature)
            glyph = glyph_map[ligature]
            dump_glyph(glyph, glyph_id, format, output_dir)


def main(argv: argparse.Namespace):
    configure_logger("script", argv.log_level)
    dump_font(argv.font_file, argv.format, argv.dir, argv.dump_unknown, argv.ligature)


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
        dest="font_file",
        required=True,
        type=existing_file,
    )
    _ = parser.add_argument(
        "--ligature",
        "--lig",
        help="A specific ligature to dump from a font.",
        dest="ligature",
        required=False,
        type=str,
    )
    _ = parser.add_argument(
        "--directory",
        "--dir",
        "-d",
        help="A directory to dump glyphs to.",
        dest="dir",
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
