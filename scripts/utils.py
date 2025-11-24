import json
import logging
import os
import urllib.request  # avoiding requests dep bc we can
from functools import partial

LOG_FORMAT = (
    "[%(asctime)s] [%(filename)14s:%(lineno)-4s] [%(levelname)8s]   %(message)s"
)


HEADERS = {  # pretend to be Chrome 121 for Discord links
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.3"
}


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    resp = urllib.request.urlopen(req).read()
    return resp


def download_json(url: str) -> dict:
    resp = download(url)
    return json.loads(resp)


### Typing utils for argparse
def existing_directory(dir_path: str) -> str:
    if os.path.isdir(dir_path):
        return dir_path
    raise NotADirectoryError(dir_path)


def existing_file(file_path: str) -> str:
    if os.path.isfile(file_path):
        return file_path
    raise FileNotFoundError(file_path)


def configure_logger(
    logger: str,
    log_level: int = logging.DEBUG,
    stacktrace_level: int = logging.ERROR,
) -> None:
    _log = logging.getLogger(logger)
    _log.setLevel(log_level)

    logging.basicConfig(format=LOG_FORMAT)
    if stacktrace_level > logging.NOTSET:
        if stacktrace_level <= logging.DEBUG:
            _log.debug = partial(_log.debug, exc_info=True, stack_info=True)
        if stacktrace_level <= logging.INFO:
            _log.info = partial(_log.info, exc_info=True, stack_info=True)
        if stacktrace_level <= logging.WARNING:
            _log.warning = partial(_log.warning, exc_info=True, stack_info=True)
        if stacktrace_level <= logging.ERROR:
            _log.error = partial(_log.error, exc_info=True, stack_info=True)
        if stacktrace_level <= logging.CRITICAL:
            _log.critical = partial(_log.critical, exc_info=True, stack_info=True)
            _log.fatal = partial(_log.fatal, exc_info=True, stack_info=True)
