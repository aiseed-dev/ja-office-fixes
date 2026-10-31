#!/usr/bin/env python3
"""Fetch, patch, build and start ONLYOFFICE Desktop Editors or Euro-Office with the Japanese patches.

    python3 build.py fetch     # get ONLYOFFICE sdkjs, web-apps and the desktop package (Linux or Mac)
    python3 build.py build     # apply patches/sdkjs/*.patch and patches/web-apps/*.patch to the
                               # tag and build the editors; when the patches or the tag changed,
                               # apply them again
    python3 build.py install   # put the build into the unpacked package
    python3 build.py restore   # put the original editors back
    python3 build.py run [FILE...]
    python3 build.py menu      # add the patched app to the desktop menu, and open documents with it
    python3 build.py unmenu    # take it out of the menu and give the documents back
    python3 build.py all       # fetch, build, install and menu

With --target euro-office, each command works on Euro-Office 9.3.6 (Linux,
Mac or Windows) instead, in work/euro-office/; see "Euro-Office" below.

Everything goes into work/ next to this file:

* work/sdkjs: ONLYOFFICE sdkjs at the tag of the desktop release, cloned
  with --depth 1 (about 320 MB)
* work/web-apps: ONLYOFFICE web-apps (the screens of the editors) at the same
  tag, cloned with --depth 1 (about 1 GB), and the npm packages its build
  needs (about 120 MB). The original screen of the document editor is kept
  in work/desktop/orig-web-apps-documenteditor
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
* The web-apps build of the repository leaves the document editor's app.js
  as the loader of separate modules, while the release bundles them into
  app.js (the app ships only common/main/lib/util of the common modules).
  So app.js is bundled again with r.js, from ../apps/documenteditor/main/app.js
  as in the release, and the modules in app.js and code.js are the same ones
  as in the release. The build needs Node.js (node and npx on the PATH).
* The web-apps build counts its builds in build/*.json; the files are put
  back after it, so the clone has no changes of its own.
* Some web-apps files end lines with CR LF, so git am keeps the CRs.
* The app starts only from its own folder with LD_LIBRARY_PATH=./, as the
  ONLYOFFICE flatpak's launcher does. Without it, Qt cannot load its xcb
  plugin and the app stops at once.
* The release merges the common strings into each editor's locale files,
  which the build of the repository does not; install adds the patches'
  strings to the release's files instead of replacing them.

## Euro-Office

Euro-Office 9.3.6 is built from the commits its DesktopEditors tag v9.3.6
names (REFS). Everything goes into work/euro-office/:

* sdkjs, web-apps and sdkjs-forms at those commits, fetched with --depth 1,
  and the npm packages of the sdkjs and web-apps builds (about 115 MB)
* desktop: on Linux, the official package (euro-office-euro-office-9.3.6-0-x86_64.tar.xz,
  about 500 MB) unpacked; the app is in desktop/opt/euro-office/euro-office.
  On Windows, the official zip (Euro-Office-DesktopEditors-9.3.6-0-windows-x64.zip,
  about 1 GB) unpacked into desktop/Euro-Office, the folder the installer makes.
  On a Mac, the app of Euro-Office-DesktopEditors-9.3.6-0-macos-arm64.dmg (about
  970 MB) goes into ~/Applications/Office (Euro-Office).app, as for ONLYOFFICE;
  there is no Euro-Office for Intel Macs

The patches are the same for both. Some comments next to the changes are in
Russian in Euro-Office's sdkjs, where ONLYOFFICE has them in English, so git
am may drop up to two lines of context at each end of a hunk (-C1); the
commits in REFS are fixed, so the result is always the same.

* sdkjs builds with webpack (npm run build in build/, configured by
  environment variables). The release's document editor has the forms addon
  (sdkjs-forms) in it, so the build gets SDK_ADDONS too.
* web-apps builds with webpack as well; only the document editor's webpack
  config is run, not the whole pipeline (which builds every editor and the
  mobile ones).
* The app starts as its launcher (usr/bin/euro-office-euro-office) starts
  it: LD_LIBRARY_PATH with its folder and converter/, and libcef.so in
  LD_PRELOAD. The menu entry is ja-office-fixes-euro-office.desktop.
* The editors in the Windows zip are the same files as in the Linux package,
  as all of them are built once, on Linux. On Windows the menu is a shortcut
  in the Start menu, which PowerShell makes, and the clones are made without
  core.autocrlf, so the patches find the lines as they are.
* The Mac and Windows steps have not been run on a real Mac or Windows yet.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

def target_arg() -> str:
    """The value of --target (onlyoffice or euro-office)"""
    for i, arg in enumerate(sys.argv):
        if arg == "--target" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if arg.startswith("--target="):
            return arg.split("=", 1)[1]
    return "onlyoffice"


TARGET = target_arg()
if TARGET not in ("onlyoffice", "euro-office"):
    sys.exit(f"unknown target {TARGET}: use onlyoffice or euro-office")
EURO = TARGET == "euro-office"
MAC = sys.platform == "darwin"
WIN = sys.platform == "win32"
ARM = platform.machine().lower() in ("arm64", "aarch64")
if WIN and not EURO:
    sys.exit("on Windows, only the euro-office target works: add --target euro-office")
if EURO and MAC and not ARM:
    sys.exit("Euro-Office has a Mac app for Apple silicon only")

ROOT = pathlib.Path(__file__).resolve().parent
if EURO:
    # The desktop release and the commits its tag v9.3.6 names
    VERSION = "9.3.6"
    GITHUB = "https://github.com/Euro-Office"
    REFS = {"sdkjs": "40d9b7780f11a5cadc259f9b9815a364de8caa96",
            "web-apps": "ce0ba49545810a56a3878081ab762c6a7ae8dd4e",
            "sdkjs-forms": "5c2f5a010dae3581adda34d9bab20b1903c94081"}
    RELEASE = f"{GITHUB}/DesktopEditors/releases/download/v{VERSION}"
    if MAC:
        PACKAGE_URL = f"{RELEASE}/Euro-Office-DesktopEditors-{VERSION}-0-macos-arm64.dmg"
    elif WIN:
        PACKAGE_URL = f"{RELEASE}/Euro-Office-DesktopEditors-{VERSION}-0-windows-{'arm64' if ARM else 'x64'}.zip"
    else:
        PACKAGE_URL = f"{RELEASE}/euro-office-euro-office-{VERSION}-0-{'aarch64' if ARM else 'x86_64'}.tar.xz"
    WORK = ROOT / "work/euro-office"
else:
    # The desktop release and the sdkjs tag it was built from (the header of its
    # editors/sdkjs/word/sdk-all-min.js says "Version: 9.4.0 (build:129)")
    VERSION = "9.4.0"
    GITHUB = "https://github.com/ONLYOFFICE"
    REFS = {"sdkjs": "v9.4.0.129", "web-apps": "v9.4.0.129"}
    RELEASE = f"{GITHUB}/DesktopEditors/releases/download/v{VERSION}"
    if MAC:
        PACKAGE_URL = f"{RELEASE}/ONLYOFFICE-{'arm' if platform.machine() == 'arm64' else 'x86_64'}.dmg"
    else:
        PACKAGE_URL = f"{RELEASE}/onlyoffice-desktopeditors-x64.tar.xz"
    WORK = ROOT / "work"

SDKJS = WORK / "sdkjs"
WEBAPPS = WORK / "web-apps"
FORMS = WORK / "sdkjs-forms"
PKG = WORK / "desktop"
# The name of the patched app on a Mac
APP_NAME = "Office (Euro-Office)" if EURO else "Office"
if MAC:
    APP = pathlib.Path.home() / "Applications" / f"{APP_NAME}.app"
    EDITORS = APP / "Contents/Resources/editors/sdkjs"
elif WIN:
    # The official zip holds the app's folder as it is installed
    APP = PKG / "Euro-Office"
    EDITORS = APP / "editors/sdkjs"
elif EURO:
    APP = PKG / "opt/euro-office/euro-office"
    EDITORS = APP / "editors/sdkjs"
else:
    APP = PKG / "opt/onlyoffice/desktopeditors"
    EDITORS = APP / "editors/sdkjs"
# The package's own desktop entry
OWN_ENTRY = PKG / ("usr/share/applications/euro-office-euro-office.desktop" if EURO
                   else "usr/share/applications/onlyoffice-desktopeditors.desktop")
# The editors the patches change
PRODUCTS = ("word", "cell")
PATCHES = ROOT / "patches/sdkjs"
WEB_PATCHES = ROOT / "patches/web-apps"
# The screen of the document editor, and the files of it the build changes
WEB_EDITOR = EDITORS.parent / "web-apps/apps/documenteditor/main"
WEB_DEPLOY = WEBAPPS / "deploy/web-apps/apps/documenteditor/main"
WEB_FILES = ("app.js", "code.js")
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
MENU = (pathlib.Path(os.environ.get("XDG_DATA_HOME") or pathlib.Path.home() / ".local/share")
        / ("applications/ja-office-fixes-euro-office.desktop" if EURO else "applications/ja-office-fixes.desktop"))
# The bundle identifier of the official Mac app, kept by the copy
MAC_BUNDLE_ID = "asc.euro-office.Euro-Office" if EURO else "asc.onlyoffice.ONLYOFFICE"
# The shortcut in the Start menu on Windows
WIN_SHORTCUT = (pathlib.Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs"
                / "ja-office-fixes (Euro-Office).lnk")


def run(*cmd: str, cwd: pathlib.Path | None = None, env: dict[str, str] | None = None) -> None:
    # On Windows, npm and npx are npm.cmd and npx.cmd, which only a full path finds
    program = (shutil.which(cmd[0]) or cmd[0]) if WIN else cmd[0]
    subprocess.run([program, *cmd[1:]], cwd=cwd, check=True, env=dict(os.environ, **env) if env else None)


def fetch() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    for repo in (SDKJS, WEBAPPS, FORMS) if EURO else (SDKJS, WEBAPPS):
        if repo.exists():
            continue
        if EURO:
            # A commit, not a tag: fetch just that one
            run("git", "init", "-q", str(repo))
            # The patches need the files as they are, without CR LF from Git for Windows
            run("git", "-C", str(repo), "config", "core.autocrlf", "false")
            run("git", "-C", str(repo), "remote", "add", "origin", f"{GITHUB}/{repo.name}")
            run("git", "-C", str(repo), "fetch", "--depth", "1", "origin", REFS[repo.name])
            run("git", "-C", str(repo), "-c", "advice.detachedHead=false", "checkout", "-q", "FETCH_HEAD")
        else:
            run("git", "clone", "--depth", "1", "--branch", REFS[repo.name], f"{GITHUB}/{repo.name}", str(repo))
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
        elif WIN:
            with zipfile.ZipFile(archive) as z:
                z.extractall(APP)
        else:
            with tarfile.open(archive) as t:
                t.extractall(PKG, filter="tar")
    print("fetched", SDKJS, WEBAPPS, "and", APP)


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


def git(repo: pathlib.Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=check)


def patches_id(patches: pathlib.Path, ref: str) -> str:
    """What the branch is made of: the tag or commit and every patch, name and content"""
    h = hashlib.sha256(ref.encode())
    for patch in sorted(patches.glob("*.patch")):
        h.update(patch.name.encode() + b"\0" + patch.read_bytes())
    return h.hexdigest()


def apply_patches(repo: pathlib.Path, patches: pathlib.Path) -> None:
    """Put the clone on BRANCH: the tag or commit in REFS with the patches
    applied. The patches_id() of the patches on BRANCH is kept inside the
    clone's .git"""
    ref = REFS[repo.name]
    stamp = repo / ".git/ja-office-fixes-patches"
    want = patches_id(patches, ref)
    have = stamp.read_text().strip() if stamp.exists() else ""
    if git(repo, "branch", "--list", BRANCH).stdout.strip() and have == want:
        git(repo, "switch", "-q", BRANCH)
        return
    if git(repo, "status", "--porcelain", "--untracked-files=no").stdout.strip():
        sys.exit(f"{repo} has changes of its own; commit or drop them, then build again")
    if have:
        print(f"the patches or the tag of {repo.name} changed: applying them again")
    if git(repo, "rev-parse", "-q", "--verify", f"{ref}^{{commit}}", check=False).returncode:
        run("git", "-C", str(repo), "fetch", "--depth", "1", "origin", *(() if EURO else ("tag",)), ref)
    # The branch starts again from the official tag, whatever is checked out now
    run("git", "-C", str(repo), "switch", "-q", "-C", BRANCH, ref)
    stamp.unlink(missing_ok=True)
    files = sorted(str(p) for p in patches.glob("*.patch"))
    # git am needs an identity for the commits it makes in the local clone
    try:
        run("git", "-C", str(repo), "-c", "user.name=ja-office-fixes", "-c", "user.email=ja-office-fixes@localhost",
            "am", "-q", "--3way", "--keep-cr", "-C1", *files)
    except subprocess.CalledProcessError:
        # Leave the clone as it was, so the next run starts again from the tag
        git(repo, "am", "--abort", check=False)
        git(repo, "switch", "-q", "--detach", ref)
        git(repo, "branch", "-D", BRANCH)
        raise
    stamp.write_text(want + "\n")


# Bundle the document editor's app.js as the release does (see the notes above)
BUNDLE_APP = """
const rjs = require('./node_modules/requirejs/bin/r.js');
const options = Object.assign({}, require('./documenteditor.json').main.js.requirejs.options);
delete options.dir;
delete options.appDir;
options.name = '../apps/documenteditor/main/app.js';
options.out = '../deploy/web-apps/apps/documenteditor/main/app.js';
options.optimize = 'none';
rjs.optimize(options, () => {}, e => { console.error(String(e)); process.exit(1); });
"""


def build_web_apps() -> None:
    if not shutil.which("npx"):
        sys.exit("the web-apps build needs Node.js: put node and npx on the PATH")
    apply_patches(WEBAPPS, WEB_PATCHES)
    tools = WEBAPPS / "build"
    if EURO:
        if not (tools / "node_modules").exists():
            run("npm", "ci", "--no-audit", "--no-fund", "--omit=dev", cwd=tools)
        # Only the document editor, into deploy/ as the whole pipeline puts it
        run("npx", "webpack", "--config", "webpack.documenteditor.mjs", cwd=tools,
            env={"BUILD_ROOT": str(WEBAPPS / "deploy"), "THEME": "euro-office", "PRODUCT_VERSION": VERSION})
        print("built", WEB_DEPLOY)
        return
    if not (tools / "node_modules").exists():
        # --omit=dev: the test packages download PhantomJS, which the build does not use
        run("npm", "install", "--no-audit", "--no-fund", "--omit=dev", cwd=tools)
    try:
        run("npx", "grunt", "deploy-common-component", "--desktop=true", cwd=tools)
        run("npx", "grunt", "init-build-documenteditor", "deploy-app-main", "--desktop=true", cwd=tools)
        run("node", "-e", BUNDLE_APP, cwd=tools)
    finally:
        git(WEBAPPS, "checkout", "--", "build/common.json", "build/documenteditor.json")
    print("built", WEB_DEPLOY)


def build() -> None:
    apply_patches(SDKJS, PATCHES)
    if EURO:
        tools = SDKJS / "build"
        if not (tools / "node_modules").exists():
            run("npm", "ci", "--no-audit", "--no-fund", cwd=tools)
        # The release's document editor has the forms addon in it
        run("npm", "run", "build", cwd=tools,
            env={"SDK_PLATFORM": "desktop", "SDK_ADDONS": str(FORMS), "PRODUCT_VERSION": VERSION})
    else:
        products = [arg for name in PRODUCTS for arg in ("--product", name)]
        run(sys.executable, "build.py", *products, "--desktop", cwd=SDKJS / "build")
    print("built", ", ".join(str(SDKJS / "deploy/sdkjs" / name) for name in PRODUCTS))
    build_web_apps()


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
    orig = PKG / "orig-web-apps-documenteditor"
    if not orig.exists():
        orig.mkdir(parents=True)
        for name in WEB_FILES:
            shutil.copy2(WEB_EDITOR / name, orig / name)
        shutil.copytree(WEB_EDITOR / "locale", orig / "locale")
    for name in WEB_FILES:
        shutil.copy2(WEB_DEPLOY / name, WEB_EDITOR / name)
    # The release's strings, with the build's on top (see the notes above)
    for built in (WEB_DEPLOY / "locale").glob("*.json"):
        strings = json.loads((orig / "locale" / built.name).read_text(encoding="utf-8")) if (orig / "locale" / built.name).exists() else {}
        strings.update(json.loads(built.read_text(encoding="utf-8")))
        (WEB_EDITOR / "locale" / built.name).write_text(json.dumps(strings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("installed the patched screen into", WEB_EDITOR)
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
    orig = PKG / "orig-web-apps-documenteditor"
    if orig.exists():
        for name in WEB_FILES:
            shutil.copy2(orig / name, WEB_EDITOR / name)
        shutil.copytree(orig / "locale", WEB_EDITOR / "locale", dirs_exist_ok=True)
        print("restored the original screen into", WEB_EDITOR)
    sign()


def start(files: list[str]) -> None:
    paths = [str(pathlib.Path(f).resolve()) for f in files]
    if MAC:
        # By its path, so the official app, if there is one, is not started
        run("open", "-a", str(APP), *paths)
        return
    if WIN:
        subprocess.Popen([str(APP / "DesktopEditors.exe"), *paths], cwd=APP,
                         creationflags=subprocess.DETACHED_PROCESS)
        return
    env = dict(os.environ, **app_env())
    subprocess.Popen(["./DesktopEditors", *paths], cwd=APP, env=env, start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def app_env() -> dict[str, str]:
    """The environment the app needs (see the notes above)"""
    if EURO:
        return {"LD_LIBRARY_PATH": f"{APP}:{APP / 'converter'}", "LD_PRELOAD": str(APP / "libcef.so")}
    return {"LD_LIBRARY_PATH": "./", "QT_QPA_PLATFORM": "xcb"}


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
    if WIN:
        win_menu()
        return
    # The app needs its own folder as the working folder (Path) and
    # LD_LIBRARY_PATH, as start() gives it. The icon is a generic one from
    # the desktop theme: the ONLYOFFICE logo is a trademark of Ascensio
    # System SIA and is not used for a modified build.
    product = "Euro-Office" if EURO else "ONLYOFFICE Desktop Editors"
    env = dict(app_env(), LD_LIBRARY_PATH=str(APP)) if not EURO else app_env()
    entry = "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        "Name=ja-office-fixes (Euro-Office)" if EURO else "Name=ja-office-fixes",
        "GenericName=Office suite",
        "GenericName[ja]=オフィス",
        f"Comment={product} with the Japanese patches",
        f"Comment[ja]=日本語のパッチを当てた {product}",
        f"Path={APP}",
        f"Exec=env {' '.join(exec_arg(f'{k}={v}') for k, v in env.items())} {exec_arg(str(APP / 'DesktopEditors'))} %F",
        "Icon=x-office-document",
        "Terminal=false",
        "Categories=Office;WordProcessor;",
        f"MimeType={';'.join(mime_types())};",
        "StartupWMClass=Euro-Office" if EURO else "StartupWMClass=DesktopEditors",
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
    for line in OWN_ENTRY.read_text().splitlines():
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


def win_menu() -> None:
    """A shortcut in the Start menu, made by PowerShell; say how to open documents with it"""
    script = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:LNK); "
              "$s.TargetPath = $env:EXE; $s.WorkingDirectory = $env:DIR; $s.Save()")
    run("powershell", "-NoProfile", "-Command", script,
        env={"LNK": str(WIN_SHORTCUT), "EXE": str(APP / "DesktopEditors.exe"), "DIR": str(APP)})
    print("added to the Start menu:", WIN_SHORTCUT.stem)
    print("to open docx files with it on a double-click: right-click a docx, Open with > Choose another app,")
    print(f"More apps > Look for another app on this PC, choose {APP / 'DesktopEditors.exe'}, and tick \"Always\"")


def unmenu() -> None:
    if MAC:
        print(f"to remove {APP_NAME}, move {APP} to the Trash; work/ holds the rest")
        return
    if WIN:
        WIN_SHORTCUT.unlink(missing_ok=True)
        print("removed from the Start menu:", WIN_SHORTCUT.stem)
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
    # Without --target and its value (target_arg() read them)
    args, skip = [], False
    for arg in sys.argv[1:]:
        if skip or arg.startswith("--target="):
            skip = False
        elif arg == "--target":
            skip = True
        else:
            args.append(arg)
    cmd, rest = (args[0], args[1:]) if args else ("", [])
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
