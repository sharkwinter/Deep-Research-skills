#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dump an .xlsx / .docx questionnaire into the normalized text view used to
author a spec.

Usage:
  dump_xlsx.py <file.xlsx> [<file2.xlsx> ...]
  dump_xlsx.py <file.docx>

xlsx : prints each sheet row by row (newlines shown as ⏎), columns joined by " | ".
docx : prints paragraphs and tables in document order.

Dependency-free: reads the OOXML zip with the standard library only
(zipfile + xml.etree), so no openpyxl / python-docx install is required.

Notes / limits:
- Cell dates come out as their raw serial number (number-format styles are not
  resolved). If that matters, open `--openpyxl` mode after `pip install openpyxl`.
- Merged cells report their value only in the top-left cell (normal for OOXML).
Read-only: never writes the input.
"""
import sys
import zipfile
from xml.etree import ElementTree as ET

SEP = " | "
M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PR = "{http://schemas.openxmlformats.org/package/2006/relationships}"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"


# --------------------------------------------------------------------------- xlsx
def _shared_strings(z):
    try:
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return ["".join(t.text or "" for t in si.iter(M + "t")) for si in root.findall(M + "si")]


def _sheet_list(z):
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    out = []
    sheets_node = wb.find(M + "sheets")
    for sh in (sheets_node if sheets_node is not None else []):
        tgt = rels.get(sh.get(R + "id"), "")
        tgt = tgt[1:] if tgt.startswith("/") else tgt
        if tgt and not tgt.startswith("xl/"):
            tgt = "xl/" + tgt
        out.append((sh.get("name") or "Sheet", tgt))
    return out


def _col_index(ref):
    n = 0
    for ch in ref:
        if ch.isalpha():
            n = n * 26 + (ord(ch.upper()) - 64)
        else:
            break
    return max(n - 1, 0)


def read_xlsx(path):
    """-> [(sheet_name, rows)] with rows = [[str, ...], ...]."""
    sheets = []
    with zipfile.ZipFile(path) as z:
        ss = _shared_strings(z)
        for name, spath in _sheet_list(z):
            if not spath:
                continue
            root = ET.fromstring(z.read(spath))
            data = root.find(M + "sheetData")
            rows = []
            for row in (data if data is not None else []):
                cells = {}
                for c in row.findall(M + "c"):
                    ref = c.get("r") or ""
                    ci = _col_index(ref) if ref else len(cells)
                    if c.get("t") == "inlineStr":
                        node = c.find(M + "is")
                        val = "".join(t.text or "" for t in node.iter(M + "t")) if node is not None else ""
                    else:
                        v = c.find(M + "v")
                        val = (v.text or "") if v is not None else ""
                        if c.get("t") == "s":
                            try:
                                val = ss[int(val)]
                            except (ValueError, IndexError):
                                pass
                    cells[ci] = val
                if cells:
                    rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
            rows = [r for r in rows if any(x.strip() for x in r)]
            sheets.append((name, rows))
    return sheets


def do_xlsx(path):
    for name, rows in read_xlsx(path):
        print(f"===== {name} =====")
        for r in rows:
            while r and r[-1] == "":
                r.pop()
            if r:
                print(SEP.join(x.replace("\n", "⏎").strip() for x in r))
        print(f"----- {len(rows)} non-empty row(s) -----")


# --------------------------------------------------------------------------- docx
def read_docx(path):
    """-> [('p', text) | ('table', rows)] in document order."""
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    # Word stores text boxes twice (mc:Choice + mc:Fallback); drop the fallback
    # copy or every such paragraph comes out duplicated.
    for parent in root.iter():
        for fb in list(parent.findall(MC + "Fallback")):
            parent.remove(fb)
    body = root.find(W + "body")
    out = []
    for el in (body if body is not None else []):
        if el.tag == W + "p":
            txt = "".join(t.text or "" for t in el.iter(W + "t")).strip()
            if txt:
                out.append(("p", txt))
        elif el.tag == W + "tbl":
            rows = []
            for tr in el.findall(W + "tr"):
                cells = ["".join(t.text or "" for t in tc.iter(W + "t")).replace("\n", "⏎").strip()
                         for tc in tr.findall(W + "tc")]
                if any(cells):
                    rows.append(cells)
            if rows:
                out.append(("table", rows))
    return out


def do_docx(path):
    n, ti = 0, 0
    for kind, payload in read_docx(path):
        if kind == "p":
            print(payload)
            n += 1
        else:
            ti += 1
            print(f"===== table {ti} =====")
            for row in payload:
                print(SEP.join(row))
                n += 1
    print(f"----- {n} non-empty paragraph/row(s) -----")


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    for path in argv:
        print(f"\n########## {path} ##########")
        low = path.lower()
        try:
            if low.endswith((".xlsx", ".xlsm")):
                do_xlsx(path)
            elif low.endswith((".docx",)):
                do_docx(path)
            else:
                print(f"unsupported extension: {path}", file=sys.stderr)
        except (zipfile.BadZipFile, KeyError, ET.ParseError) as e:
            print(f"cannot read {path}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
