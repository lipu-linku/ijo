#!/usr/bin/env python3

"""
This is a utility for dumping glyphs from a target font which implements ligatures.
You must install `fontforge`. This is not provided in `./requirements.txt` because 
that file is intended for Github Actions.

Example use: 
python ./scripts/dump_font.py --font ./nasinsitelen/sitelenselikiwenasuki.ttf --directory ./sitelenpona/sitelen-seli-kiwen/
"""

# STL
import argparse
import logging
import os

# PDM
import fontforge

# LOCAL
from utils import download_json, existing_directory, existing_file

LOG = logging.getLogger()

SONA_WORDS = "https://api.linku.la/v1/words"
SANDBOX_WORDS = "https://api.linku.la/v1/sandbox"

IGNORABLES = {
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


def strip_metadata(ligature: tuple[str, ...]) -> tuple[str, ...]:
    # first entry is table name, second is glyph type
    # both are unneeded
    return ligature[2:]


def is_ignorable(ligature: tuple[str, ...]) -> bool:
    # see `IGNORABLES`; we ignore ligatures for any non-primitive non-variant glyph
    if not len(ligature):
        return True
    return not not set(ligature).intersection(IGNORABLES)


def strip_space(ligature: tuple[str, ...]) -> tuple[str, ...]:
    # this can make dupes, but they write to the same position
    # some words DO NOT HAVE a named word-only ligature
    if ligature[-1] == "space":
        return ligature[:-1]
    return ligature


def handle_variant(ligature: tuple[str, ...]) -> tuple[str, tuple[str, ...]]:
    if ligature[-1] in VARIANT_NUMBERS:
        variant_suffix = "-" + VARIANT_NUMBERS[ligature[-1]]
        ligature = ligature[:-1]  # last is number
        return variant_suffix, ligature
    return "", ligature


def main(argv: argparse.Namespace):
    LOG.setLevel(argv.log_level)

    font = fontforge.open(argv.font)
    for glyph in font.glyphs():
        table_data = glyph.getPosSub("*")
        for ligature in table_data:
            # we have to dump ligatures per-table per-glyph
            ligature = strip_metadata(ligature)
            if is_ignorable(ligature):
                continue

            ligature = strip_space(ligature)
            variant_suffix, ligature = handle_variant(ligature)

            word = "".join(ligature)
            if word not in NIMI_ALE:
                continue

            svg_filename = word + variant_suffix + ".svg"
            LOG.info("Creating %s", svg_filename)
            glyph.export(os.path.join(argv.directory, svg_filename))

            # WARNING: You CANNOT directly use the output. It MUST be hand-processed.
            # Different fonts use different variant numbers.
            # You must also get permission to commit any dumped font data, respecting the license.


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script to dump glyphs from a font.")
    parser.add_argument(
        "--log-level",
        help="Set the log level",
        type=str.upper,
        dest="log_level",
        default="INFO",
        choices=["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    parser.add_argument(
        "--font",
        help="A font file to dump glyphs from",
        dest="font",
        required=True,
        type=existing_file,
    )
    parser.add_argument(
        "--directory",
        help="A directory to dump glyphs to.",
        dest="directory",
        required=True,
        type=existing_directory,
    )
    # TODO: Do unicode fonts name their glyphs? If so, we could use those and pass a switch argument
    ARGV = parser.parse_args()
    main(ARGV)
