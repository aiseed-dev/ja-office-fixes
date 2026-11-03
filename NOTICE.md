# NOTICE

## Based on ONLYOFFICE

The patches in `patches/sdkjs/` modify ONLYOFFICE sdkjs
(https://github.com/ONLYOFFICE/sdkjs), and the patches in `patches/web-apps/`
modify ONLYOFFICE web-apps (https://github.com/ONLYOFFICE/web-apps). Both are
developed by Ascensio System SIA and licensed under the GNU Affero General
Public License v3.0. A program built with them is a modified version of
ONLYOFFICE.

Modifications (2026-10-06):

- `word/Editor/Paragraph/RunContent/Text.js`, `common/editorscommon.js`:
  break opportunities between kana; one character that may not begin a line
  may hang past the line end; upright drawing of East Asian characters in
  vertical text.
- `common/commonDefines.js`: Word's standard Japanese kinsoku characters.
- `word/Editor/Run.js`, `word/Editor/Paragraph_Recalculate.js`,
  `word/Editor/Paragraph/RunContent/Base.js`: the hanging character and its
  place in the line alignment.
- `word/Editor/Table/TableCell.js`, `common/Drawings/Format/Shape.js`: the
  transform of vertical cells and text boxes passed to the text drawing.
- `tests/word/document-calculation/paragraph/paragraph-lines.js`: tests for
  Japanese line breaking.

Modifications (2026-10-08):

- `common/NumFormat.js`: the Japanese era format codes g, e and r, and
  G/標準 as General.
- `tests/cell/spreadsheet-calculation/NumFormatParse.js`: tests for them.
- `cell/model/FormulaObjects/textanddataFunctions.js`: ASC and JIS for
  Japanese text, bytes of code page 932 in LENB, LEFTB, RIGHTB, MIDB,
  REPLACEB, FINDB and SEARCHB, and full-width digits in VALUE.
- `tests/cell/spreadsheet-calculation/formula-tests/textAndDataTests.js`:
  tests for them; five ASC expectations that recorded the old output.
- `common/NumFormat.js`: Japanese numerals in [DBNum1] to [DBNum3], and the
  first year of an era as 元 with [$-ja-JP-x-gannen].

Modifications (2026-10-10 and 2026-10-11):

- `common/Drawings/Format/Format.js`, `common/Shapes/Serialize.js`,
  `common/Shapes/SerializeWriter.js`, `word/Editor/Styles.js`: the script
  fonts of the theme (a:font), used for East Asian text by its language.
- `common/libfont/map.js`, `common/libfont/textmeasurer.js`,
  `common/Drawings/TextDrawer.js`, `common/Drawings/Metafile.js`,
  `word/Drawing/Graphics.js`, `word/Editor/Styles.js`: the Latin text of a
  missing MS Gothic or MS Mincho in BIZ UDGothic or BIZ UDMincho.
- `common/apiCommon.js`, `word/api.js`: the Latin and East Asian fonts in
  the paragraph settings.
- `tests/word/styles/themeFonts.js`, `tests/word/styles/latinFonts.js`:
  tests for them.
- web-apps `apps/documenteditor/main/app/view/ParagraphSettingsAdvanced.js`,
  its template, `controller/Toolbar.js`, `controller/DocumentHolderExt.js`,
  `view/ParagraphSettings.js` and the en and ja locales: the Asian and Latin
  text fonts in the Font tab of the paragraph advanced settings.

Modifications (2026-10-31 and 2026-11-01):

- `word/Editor/Paragraph/RunContent/Text.js`,
  `word/Editor/Paragraph/TextShaper.js`: a quarter space between kanji or
  kana and Latin letters or digits; tests in
  `tests/word/document-calculation/paragraph/paragraph-lines.js`.
- `cell/model/FormulaObjects/textanddataFunctions.js`: NUMBERSTRING,
  DATESTRING and PHONETIC, DOLLAR (YEN) in the Japanese locale, and JIS
  kept as DBCS in files; `cell/model/FormulaObjects/_xlfnFunctions.js`: the
  empty DBCS stub removed; tests in
  `tests/cell/spreadsheet-calculation/formula-tests/textAndDataTests.js`
  and the function list in `tests/cell/spreadsheet-calculation/FormulaTrace.js`.
- web-apps `apps/spreadsheeteditor/main/resources/formula-lang/ja.json`: DBCS
  shown as JIS.

## Euro-Office

The same patches apply to Euro-Office (https://github.com/Euro-Office), a
fork of ONLYOFFICE licensed under the GNU Affero General Public License
v3.0. `build.py --target euro-office` builds it with them.

The downloads of the patched Euro-Office (the releases of this repository,
built by `.github/workflows/euro-office-release.yml`) are modified versions
of Euro-Office. They are not official Euro-Office builds. Each one has
JA-OFFICE-FIXES.txt, which says what was changed, when, and where the source
is: the patches of this repository at the commit it names, applied to the
Euro-Office commits in `build.py`; the rest is the official release of
https://github.com/Euro-Office/DesktopEditors.

The Flatpak download also has MIT Kerberos (krb5 1.22.2,
https://kerberos.org, built from its source by
`flatpak/io.github.aiseed_dev.JaOfficeFixes.yml`), as Euro-Office's Qt needs
libgssapi_krb5 and the Flatpak runtime lacks it. Its license is in the
Flatpak at /app/share/licenses/krb5/NOTICE.

## Trademarks

ONLYOFFICE is a trademark of Ascensio System SIA. This project is not
affiliated with, endorsed by or sponsored by Ascensio System SIA. The name
ONLYOFFICE is used only to say what the patches apply to.

No modified ONLYOFFICE binaries are distributed here: ONLYOFFICE's
additional terms ask to keep its logo and give no right to its name.
`build.py` downloads the official release and applies the patches on the
user's machine. Patched builds are offered only for Euro-Office (see above).

## Credits

The first patch is the change proposed to ONLYOFFICE in
https://github.com/ONLYOFFICE/sdkjs/pull/4885 by Yuito Murase (zeptometer),
with tests added.
