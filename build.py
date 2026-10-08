#!/usr/bin/env python3
"""Fetch, patch, build and start ONLYOFFICE Desktop Editors with the Japanese patches.

    python3 build.py fetch     # get ONLYOFFICE sdkjs and the desktop package (Linux or Mac)
    python3 build.py build     # apply patches/sdkjs/*.patch to the tag and build the editors;
                               # when the patches or the tag changed, apply them again
    python3 build.py install   # put the build into the unpacked package
    python3 build.py restore   # put the original editors back
    python3 build.py run [FILE...]
    python3 build.py menu      # add the patched app to the desktop menu, and open documents with it
    python3 build.py unmenu    # take it out of the menu and give the documents back
    python3 build.py all       # fetch, build, install and menu

Everything goes into work/ next to this file:

* work/sdkjs: ONLYOFFICE sdkjs at the tag of the desktop release, cloned
  with --depth 1 (about 320 MB)
* work/desktop: on Linux, the official package (onlyoffice-desktopeditors-x64.tar.xz,
  about 345 MB) unpacked. The original editors are kept in
  work/desktop/orig-sdkjs-word and work/desktop/orig-sdkjs-cell

On a Mac, the app is copied out of the official disk image
(ONLYOFFICE-arm.dmg or ONLYOFFICE-x86_64.dmg, about 550 MB; kept in work/)
into ~/Applications/Office.app, where the Finder and Spotlight find apps
(the app asks to be moved to an Applications folder when it starts from
anywhere else). It is named Office: the ONLYOFFICE name is not the name of
a modified build. An Office.app there that is not ONLYOFFICE is never
touched. Changing the app breaks its signature, so it is signed again for
this machine (an ad-hoc signature), and the quarantine mark of the download
is taken off. Which app opens a docx on a double-click is chosen in the
Finder ("Get Info", "Open with"); menu says how.

The menu entry is ja-office-fixes.desktop in ~/.local/share/applications
(or $XDG_DATA_HOME/applications). It lists the file types of the package's
own entry, so the app appears under "Open with" for all of them, and it
becomes the default app of the word-processing types (DOCUMENTS), so a
double-click on a docx opens it. The defaults go into ~/.config/mimeapps.list
with xdg-mime; unmenu takes them out again. These two files are the only
ones written outside work/.

Only the document (word) and spreadsheet (cell) editors are changed. The
presentation editor is the official one.

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

import hashlib
import os
import pathlib
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request

# The desktop release and the sdkjs tag it was built from (the header of its
# editors/sdkjs/word/sdk-all-min.js says "Version: 9.4.0 (build:129)")
VERSION = "9.4.0"
SDKJS_TAG = "v9.4.0.129"
MAC = sys.platform == "darwin"
RELEASE = f"https://github.com/ONLYOFFICE/DesktopEditors/releases/download/v{VERSION}"
if MAC:
    PACKAGE_URL = f"{RELEASE}/ONLYOFFICE-{'arm' if platform.machine() == 'arm64' else 'x86_64'}.dmg"
else:
    PACKAGE_URL = f"{RELEASE}/onlyoffice-desktopeditors-x64.tar.xz"

ROOT = pathlib.Path(__file__).resolve().parent
WORK = ROOT / "work"
SDKJS = WORK / "sdkjs"
PKG = WORK / "desktop"
# The name of the patched app on a Mac
APP_NAME = "Office"
if MAC:
    APP = pathlib.Path.home() / "Applications" / f"{APP_NAME}.app"
    EDITORS = APP / "Contents/Resources/editors/sdkjs"
else:
    APP = PKG / "opt/onlyoffice/desktopeditors"
    EDITORS = APP / "editors/sdkjs"
# The editors the patches change
PRODUCTS = ("word", "cell")
PATCHES = ROOT / "patches/sdkjs"
BRANCH = "ja-office-fixes"
# The patches_id() of the patches on BRANCH, kept inside the clone's .git
STAMP = SDKJS / ".git/ja-office-fixes-patches"
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
# The bundle identifier of the official Mac app, kept by the copy
MAC_BUNDLE_ID = "asc.onlyoffice.ONLYOFFICE"


def run(*cmd: str, cwd: pathlib.Path | None = None) -> None:
    subprocess.run(list(cmd), cwd=cwd, check=True)


def fetch() -> None:
    WORK.mkdir(exist_ok=True)
    if not SDKJS.exists():
        run("git", "clone", "--depth", "1", "--branch", SDKJS_TAG, "https://github.com/ONLYOFFICE/sdkjs", str(SDKJS))
    if MAC:
        ours_or_exit()
    if not APP.exists():
        archive = WORK / PACKAGE_URL.rsplit("/", 1)[1]
        if not archive.exists():
            print("downloading", PACKAGE_URL)
            part = archive.with_suffix(archive.suffix + ".part")
            urllib.request.urlretrieve(PACKAGE_URL, part)
            part.rename(archive)
        PKG.mkdir(exist_ok=True)
        if MAC:
            copy_app(archive)
        else:
            with tarfile.open(archive) as t:
                t.extractall(PKG, filter="tar")
    print("fetched", SDKJS, "and", APP)


def copy_app(dmg: pathlib.Path) -> None:
    """Copy the app out of the disk image as Office.app, name it Office, and
    sign it for this machine"""
    mount = WORK / "mount"
    mount.mkdir(exist_ok=True)
    APP.parent.mkdir(exist_ok=True)
    run("hdiutil", "attach", "-nobrowse", "-readonly", "-mountpoint", str(mount), str(dmg))
    try:
        apps = sorted(mount.glob("*.app"))
        if len(apps) != 1:
            sys.exit(f"expected one app in {dmg.name}, found {[a.name for a in apps]}")
        run("ditto", str(apps[0]), str(APP))
    finally:
        run("hdiutil", "detach", "-quiet", str(mount))
    # The name the Finder, the Dock and the menu bar show
    plist = APP / "Contents/Info.plist"
    for key in ("CFBundleName", "CFBundleDisplayName"):
        run("plutil", "-replace", key, "-string", APP_NAME, str(plist))
    sign()


def ours_or_exit() -> None:
    """Stop when ~/Applications/Office.app is some other app"""
    plist = APP / "Contents/Info.plist"
    if not APP.exists():
        return
    got = subprocess.run(["plutil", "-extract", "CFBundleIdentifier", "raw", str(plist)],
                         capture_output=True, text=True).stdout.strip()
    if got != MAC_BUNDLE_ID:
        sys.exit(f"{APP} is another app ({got or 'no bundle identifier'}); move it away first")


def sign() -> None:
    """Sign the changed app again for this machine (ad hoc) and take off the
    quarantine mark of the download, so macOS starts it"""
    if not MAC:
        return
    run("xattr", "-dr", "com.apple.quarantine", str(APP))
    run("codesign", "--force", "--deep", "--sign", "-", str(APP))


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(SDKJS), *args], capture_output=True, text=True, check=check)


def patches_id() -> str:
    """What the branch is made of: the tag and every patch, name and content"""
    h = hashlib.sha256(SDKJS_TAG.encode())
    for patch in sorted(PATCHES.glob("*.patch")):
        h.update(patch.name.encode() + b"\0" + patch.read_bytes())
    return h.hexdigest()


def build() -> None:
    want = patches_id()
    have = STAMP.read_text().strip() if STAMP.exists() else ""
    if git("branch", "--list", BRANCH).stdout.strip() and have == want:
        git("switch", "-q", BRANCH)
    else:
        if git("status", "--porcelain").stdout.strip():
            sys.exit(f"{SDKJS} has changes of its own; commit or drop them, then build again")
        if have:
            print("the patches or the tag changed: applying them again")
        if git("rev-parse", "-q", "--verify", f"refs/tags/{SDKJS_TAG}", check=False).returncode:
            run("git", "-C", str(SDKJS), "fetch", "--depth", "1", "origin", "tag", SDKJS_TAG)
        # The branch starts again from the official tag, whatever is checked out now
        run("git", "-C", str(SDKJS), "switch", "-q", "-C", BRANCH, SDKJS_TAG)
        STAMP.unlink(missing_ok=True)
        patches = sorted(str(p) for p in PATCHES.glob("*.patch"))
        # git am needs an identity for the commits it makes in the local clone
        try:
            run("git", "-C", str(SDKJS), "-c", "user.name=ja-office-fixes", "-c", "user.email=ja-office-fixes@localhost",
                "am", "-q", "--3way", *patches)
        except subprocess.CalledProcessError:
            # Leave the clone as it was, so the next run starts again from the tag
            git("am", "--abort", check=False)
            git("switch", "-q", "--detach", SDKJS_TAG)
            git("branch", "-D", BRANCH)
            raise
        STAMP.write_text(want + "\n")
    products = [arg for name in PRODUCTS for arg in ("--product", name)]
    run(sys.executable, "build.py", *products, "--desktop", cwd=SDKJS / "build")
    print("built", ", ".join(str(SDKJS / "deploy/sdkjs" / name) for name in PRODUCTS))


def install() -> None:
    if MAC:
        ours_or_exit()
    for name in PRODUCTS:
        editor = EDITORS / name
        orig = PKG / f"orig-sdkjs-{name}"
        if not orig.exists():
            orig.mkdir(parents=True)
            for f in editor.iterdir():
                if f.is_file():
                    shutil.copy2(f, orig / f.name)
        for script in ("sdk-all-min.js", "sdk-all.js"):
            shutil.copy2(SDKJS / "deploy/sdkjs" / name / script, editor / script)
        for cache in ("sdk-all.bin", "sdk-all.cache"):
            (editor / cache).unlink(missing_ok=True)
        print("installed the patched editor into", editor)
    sign()


def restore() -> None:
    if MAC:
        ours_or_exit()
    for name in PRODUCTS:
        editor = EDITORS / name
        orig = PKG / f"orig-sdkjs-{name}"
        if not orig.exists():
            continue
        (editor / "sdk-all.cache").unlink(missing_ok=True)
        for f in orig.iterdir():
            shutil.copy2(f, editor / f.name)
        print("restored the original editor into", editor)
    sign()


def start(files: list[str]) -> None:
    paths = [str(pathlib.Path(f).resolve()) for f in files]
    if MAC:
        # By its path, so the official app, if there is one, is not started
        run("open", "-a", str(APP), *paths)
        return
    env = dict(os.environ, LD_LIBRARY_PATH="./", QT_QPA_PLATFORM="xcb")
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
    if MAC:
        mac_menu()
        return
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
    print("added to the menu:", MENU)
    if shutil.which("xdg-mime"):
        run("xdg-mime", "default", MENU.name, *DOCUMENTS)
        print("documents (docx, doc, odt, rtf) now open in it with a double-click")
    else:
        print("xdg-mime (xdg-utils) is not installed: documents still open in the app they had")


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


def mac_menu() -> None:
    """The app is already in ~/Applications: say how to open documents with it"""
    print(APP_NAME, "is in", APP.parent)
    print("to open docx files with it on a double-click: select a docx in the Finder, File > Get Info,")
    print(f"choose {APP_NAME} under \"Open with\", and press \"Change All...\"")


def unmenu() -> None:
    if MAC:
        print(f"to remove {APP_NAME}, move {APP} to the Trash; work/ holds the rest")
        return
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
