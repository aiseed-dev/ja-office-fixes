#!/usr/bin/env python3
"""Fetch, patch, build and start ONLYOFFICE Desktop Editors with the Japanese patches.

    python3 build.py fetch     # get ONLYOFFICE sdkjs and the Linux desktop package
    python3 build.py build     # apply patches/sdkjs/*.patch to the tag and build the word editor
    python3 build.py install   # put the build into the unpacked package
    python3 build.py restore   # put the original word editor back
    python3 build.py run [FILE...]
    python3 build.py menu      # add the patched app to the desktop menu, and open documents with it
    python3 build.py unmenu    # take it out of the menu and give the documents back
    python3 build.py all       # fetch, build, install and menu

Everything goes into work/ next to this file:

* work/sdkjs: ONLYOFFICE sdkjs at the tag of the desktop release, cloned
  with --depth 1 (about 210 MB)
* work/desktop: the official Linux package (onlyoffice-desktopeditors-x64.tar.xz,
  about 345 MB) unpacked; the original word editor is kept in
  work/desktop/orig-sdkjs-word

The menu entry is ja-office-fixes.desktop in ~/.local/share/applications
(or $XDG_DATA_HOME/applications). It lists the file types of the package's
own entry, so the app appears under "Open with" for all of them, and it
becomes the default app of the word-processing types (DOCUMENTS), so a
double-click on a docx opens it. The defaults go into ~/.config/mimeapps.list
with xdg-mime; unmenu takes them out again. These two files are the only
ones written outside work/.

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
# The types a double-click opens in the patched app: the ones the word
# editor handles, as the package's own entry names them
DOCUMENTS = [
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.template",
    "application/vnd.ms-word.document.macroEnabled.12",
    "application/vnd.ms-word.template.macroEnabled.12",
    "application/msword",
    "application/msword-template",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.text-template",
    "application/vnd.oasis.opendocument.text-flat-xml",
    "application/rtf",
]
MENU = pathlib.Path(os.environ.get("XDG_DATA_HOME") or pathlib.Path.home() / ".local/share") / "applications/ja-office-fixes.desktop"


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


def exec_arg(arg: str) -> str:
    """One argument of a desktop entry's Exec key, quoted and escaped

    The Desktop Entry Specification quotes the argument first, then escapes
    backslashes once more as for any string value; a literal % is %%.
    """
    quoted = '"' + "".join("\\" + c if c in '"`$\\' else c for c in arg) + '"'
    return quoted.replace("\\", "\\\\").replace("%", "%%")


def menu() -> None:
    # The app needs its own folder as the working folder (Path) and
    # LD_LIBRARY_PATH, as start() gives it. The icon is a generic one from
    # the desktop theme: the ONLYOFFICE logo is a trademark of Ascensio
    # System SIA and is not used for a modified build.
    entry = "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        "Name=ja-office-fixes",
        "GenericName=Office suite",
        "GenericName[ja]=オフィス",
        "Comment=ONLYOFFICE Desktop Editors with the Japanese line-breaking and vertical-writing patches",
        "Comment[ja]=日本語の行の折り返しと縦書きのパッチを当てた ONLYOFFICE Desktop Editors",
        f"Path={APP}",
        f"Exec=env {exec_arg(f'LD_LIBRARY_PATH={APP}')} QT_QPA_PLATFORM=xcb {exec_arg(str(APP / 'DesktopEditors'))} %F",
        "Icon=x-office-document",
        "Terminal=false",
        "Categories=Office;WordProcessor;",
        f"MimeType={';'.join(mime_types())};",
        "StartupWMClass=DesktopEditors",
        "",
    ])
    MENU.parent.mkdir(parents=True, exist_ok=True)
    MENU.write_text(entry)
    refresh_menu()
    run("xdg-mime", "default", MENU.name, *DOCUMENTS)
    print("added to the menu:", MENU)
    print("documents (docx, doc, odt, rtf) now open in it with a double-click")


def mime_types() -> list[str]:
    """The file types of the package's own desktop entry"""
    own = PKG / "usr/share/applications/onlyoffice-desktopeditors.desktop"
    for line in own.read_text().splitlines():
        if line.startswith("MimeType="):
            # The entry opens files (%F), not oo-office: links
            return [t for t in line[9:].split(";") if t and not t.startswith("x-scheme-handler/")]
    return DOCUMENTS


def refresh_menu() -> None:
    # The cache of which app opens which type; desktops read it, when it is there
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", str(MENU.parent)], capture_output=True)


def unmenu() -> None:
    MENU.unlink(missing_ok=True)
    refresh_menu()
    # Take the entry out of the user's defaults; the types fall back to the
    # apps the system names for them
    config = pathlib.Path(os.environ.get("XDG_CONFIG_HOME") or pathlib.Path.home() / ".config") / "mimeapps.list"
    if config.exists():
        lines = []
        for line in config.read_text().splitlines():
            key, eq, apps = line.partition("=")
            if eq and MENU.name in apps.split(";"):
                apps = ";".join(a for a in apps.split(";") if a != MENU.name)
                if not apps.strip(";"):
                    continue
                line = f"{key}={apps}"
            lines.append(line)
        config.write_text("\n".join(lines) + "\n")
    print("removed from the menu:", MENU)


def main() -> int:
    cmd, rest = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("", [])
    steps = {"fetch": [fetch], "build": [build], "install": [install], "restore": [restore],
             "menu": [menu], "unmenu": [unmenu], "all": [fetch, build, install, menu]}
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
