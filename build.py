#!/usr/bin/env python3
"""Fetch, patch, build and start ONLYOFFICE Desktop Editors with the Japanese patches.

    python3 build.py fetch     # get ONLYOFFICE sdkjs and the Linux desktop package
    python3 build.py build     # apply patches/sdkjs/*.patch to the tag and build the word editor
    python3 build.py install   # put the build into the unpacked package
    python3 build.py restore   # put the original word editor back
    python3 build.py run [FILE...]
    python3 build.py all       # fetch, build and install

Everything goes into work/ next to this file:

* work/sdkjs: ONLYOFFICE sdkjs at the tag of the desktop release, cloned
  with --depth 1 (about 210 MB)
* work/desktop: the official Linux package (onlyoffice-desktopeditors-x64.tar.xz,
  about 345 MB) unpacked; the original word editor is kept in
  work/desktop/orig-sdkjs-word

Only the word editor (documents) is changed. The spreadsheet and
presentation editors are the official ones.

## What we ran into

* The sdkjs of 9.4 builds with build/build.py, which only joins the files:
  no Closure Compiler and no npm are needed.
* sdk-all.bin next to sdk-all.js is a cache of the original script, and the
  app writes sdk-all.cache there when it runs. Both are removed whenever a
  script goes in, so a stale cache is never used.
* The app starts only from its own folder with LD_LIBRARY_PATH=./, as the
  ONLYOFFICE flatpak's launcher does. Without it, Qt cannot load its xcb
  plugin and the app stops at once.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import urllib.request

# The desktop release and the sdkjs tag it was built from (the header of its
# editors/sdkjs/word/sdk-all-min.js says "Version: 9.4.0 (build:129)")
VERSION = "9.4.0"
SDKJS_TAG = "v9.4.0.129"
PACKAGE_URL = f"https://github.com/ONLYOFFICE/DesktopEditors/releases/download/v{VERSION}/onlyoffice-desktopeditors-x64.tar.xz"

ROOT = pathlib.Path(__file__).resolve().parent
WORK = ROOT / "work"
SDKJS = WORK / "sdkjs"
PKG = WORK / "desktop"
APP = PKG / "opt/onlyoffice/desktopeditors"
WORD = APP / "editors/sdkjs/word"
ORIG = PKG / "orig-sdkjs-word"
PATCHES = ROOT / "patches/sdkjs"
BRANCH = "ja-office-fixes"


def run(*cmd: str, cwd: pathlib.Path | None = None) -> None:
    subprocess.run(list(cmd), cwd=cwd, check=True)


def fetch() -> None:
    WORK.mkdir(exist_ok=True)
    if not SDKJS.exists():
        run("git", "clone", "--depth", "1", "--branch", SDKJS_TAG, "https://github.com/ONLYOFFICE/sdkjs", str(SDKJS))
    if not APP.exists():
        archive = WORK / PACKAGE_URL.rsplit("/", 1)[1]
        if not archive.exists():
            print("downloading", PACKAGE_URL)
            urllib.request.urlretrieve(PACKAGE_URL, archive)
        PKG.mkdir(exist_ok=True)
        with tarfile.open(archive) as t:
            t.extractall(PKG, filter="tar")
    print("fetched", SDKJS, "and", APP)


def build() -> None:
    branches = subprocess.run(["git", "-C", str(SDKJS), "branch", "--list", BRANCH], capture_output=True, text=True, check=True).stdout
    if not branches.strip():
        # The branch starts from the official tag, whatever is checked out now
        run("git", "-C", str(SDKJS), "switch", "-q", "-c", BRANCH, SDKJS_TAG)
        patches = sorted(str(p) for p in PATCHES.glob("*.patch"))
        # git am needs an identity for the commits it makes in the local clone
        try:
            run("git", "-C", str(SDKJS), "-c", "user.name=ja-office-fixes", "-c", "user.email=ja-office-fixes@localhost",
                "am", "-q", "--3way", *patches)
        except subprocess.CalledProcessError:
            # Leave the clone as it was, so the next run starts again from the tag
            subprocess.run(["git", "-C", str(SDKJS), "am", "--abort"])
            run("git", "-C", str(SDKJS), "switch", "-q", "--detach", SDKJS_TAG)
            run("git", "-C", str(SDKJS), "branch", "-D", BRANCH)
            raise
    else:
        run("git", "-C", str(SDKJS), "switch", "-q", BRANCH)
    run(sys.executable, "build.py", "--product", "word", "--desktop", cwd=SDKJS / "build")
    print("built", SDKJS / "deploy/sdkjs/word")


def install() -> None:
    if not ORIG.exists():
        ORIG.mkdir(parents=True)
        for f in WORD.iterdir():
            shutil.copy2(f, ORIG / f.name)
    for name in ("sdk-all-min.js", "sdk-all.js"):
        shutil.copy2(SDKJS / "deploy/sdkjs/word" / name, WORD / name)
    for cache in ("sdk-all.bin", "sdk-all.cache"):
        (WORD / cache).unlink(missing_ok=True)
    print("installed the patched word editor into", WORD)


def restore() -> None:
    (WORD / "sdk-all.cache").unlink(missing_ok=True)
    for f in ORIG.iterdir():
        shutil.copy2(f, WORD / f.name)
    print("restored the original word editor into", WORD)


def start(files: list[str]) -> None:
    env = dict(os.environ, LD_LIBRARY_PATH="./", QT_QPA_PLATFORM="xcb")
    paths = [str(pathlib.Path(f).resolve()) for f in files]
    subprocess.Popen(["./DesktopEditors", *paths], cwd=APP, env=env, start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> int:
    cmd, rest = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("", [])
    steps = {"fetch": [fetch], "build": [build], "install": [install], "restore": [restore],
             "all": [fetch, build, install]}
    if cmd in steps:
        for step in steps[cmd]:
            step()
    elif cmd == "run":
        start(rest)
    else:
        print(__doc__.split("\n\n")[1])
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
