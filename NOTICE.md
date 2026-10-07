# NOTICE

## Based on ONLYOFFICE

The patches in `patches/sdkjs/` modify ONLYOFFICE sdkjs
(https://github.com/ONLYOFFICE/sdkjs), developed by Ascensio System SIA and
licensed under the GNU Affero General Public License v3.0. A program built
with them is a modified version of ONLYOFFICE.

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

## Trademarks

ONLYOFFICE is a trademark of Ascensio System SIA. This project is not
affiliated with, endorsed by or sponsored by Ascensio System SIA. The name
ONLYOFFICE is used only to say what the patches apply to.

No modified ONLYOFFICE binaries are distributed here. `build.py` downloads
the official release and applies the patches on the user's machine.

## Credits

The first patch is the change proposed to ONLYOFFICE in
https://github.com/ONLYOFFICE/sdkjs/pull/4885 by Yuito Murase (zeptometer),
with tests added.
