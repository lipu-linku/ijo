import json
import os
import urllib.request  # avoiding requests dep bc we can

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
