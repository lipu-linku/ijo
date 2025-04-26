#!/usr/bin/env python3
# STL
import argparse
import logging
import os
from io import BytesIO
from zipfile import ZipFile

# PDM
import magic

# LOCAL
from utils import download, download_json

LOG = logging.getLogger()

SONA_FONTS = "https://api.linku.la/v1/fonts"

VALID_LICENSE_FAMILIES = [
    "GPL",
    "MIT",
    "OFL",
    "CC",
    "SIL Open Font License",
]
VALID_MIMETYPES = [
    "font/sfnt",  # ttf
    "application/vnd.ms-opentype",  # otf
    "application/font-woff"  # woff
    # magic does not use these:
    # "font/ttf",
    # "font/otf",
    # "font/woff",
    # "font/woff2",
    # "application/x-font-ttf",
    # "application/x-font-otf",
]

FONTDIR = "nasinsitelen"

# map of special behaviors per font
SPECIAL_CASES = {
    "insa pi supa lape": lambda url: unzip_font_zip(url, "standard/supalape.otf"),
}


def is_valid_license(to_check: str) -> bool:
    """an incomplete enumeration of licenses this project accepts"""
    for license_id in VALID_LICENSE_FAMILIES:
        if to_check.startswith(license_id):
            # catch families of licenses such as GPL*, CC*
            return True

    return False


def is_font_file(to_check: bytes) -> bool:
    mimetype = magic.from_buffer(to_check, mime=True)

    return mimetype in VALID_MIMETYPES


def unzip_font_zip(fontzip: bytes, filename: str):
    zipfile = ZipFile(BytesIO(fontzip))
    f = zipfile.open(filename)
    resp = f.read()
    f.close()
    return resp


def write_font(filename: str, content: bytes) -> int:
    with open(os.path.join(FONTDIR, filename), "wb") as f:
        written = f.write(content)
    return written


def main(argv):
    LOG.setLevel(argv.log_level)

    fonts = download_json(SONA_FONTS)
    for name, data in fonts.items():
        if "fontfile" not in data["links"]:
            LOG.warning("No download available for %s", name)
            continue

        if argv.licenses and not is_valid_license(data.get("license", "")):
            LOG.warning("Non-open or missing license for %s", name)
            continue

        try:
            font = download(data["links"]["fontfile"])
            if name in SPECIAL_CASES:
                # only insa pi supa lape, since it is distributed as a zip
                font = SPECIAL_CASES[name](font)

            if not is_font_file(font):
                LOG.warning("Downloaded non-font object for %s", name)
                continue

            write_font(data["filename"], font)

        except Exception as e:
            LOG.error("Failed to download %s", name)
            LOG.error("        %s", e)
            LOG.error("        %s", e.__dict__)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Script to update locally tracked fonts"
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
        "--licenses",
        help="Enable license checking, excluding fonts with non-open licenses",
        dest="licenses",
        default=True,
        action="store_true",
    )
    ARGV = parser.parse_args()
    main(ARGV)
