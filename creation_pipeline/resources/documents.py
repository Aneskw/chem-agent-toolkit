"""Text extraction only: no OCR, code execution or visual interpretation."""
from __future__ import annotations

import csv
import io
import json
import sqlite3
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser
from pathlib import Path

if not __package__:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = "creation_pipeline.resources"

from creation_pipeline.models import BlockedError


class HTMLText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip, self.parts, self.links = 0, [], []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav"):
            self.skip += 1
        if tag in ("p", "div", "h1", "h2", "h3", "li", "br", "section"):
            self.parts.append("\n")
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "meta" and attrs.get("name") == "citation_pdf_url":
            self.links.append(attrs.get("content", ""))

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def xml_member(archive, name, limit):
    if limit is not None and archive.getinfo(name).file_size > limit:
        raise ValueError("Expanded document part exceeds source_bytes")
    return ET.fromstring(archive.read(name))


def read_text(path, limit):
    path = Path(path)
    if limit is not None and path.stat().st_size > limit:
        raise ValueError("Source exceeds source_bytes")
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise BlockedError("PDF text reading needs pypdf; OCR is not provided") from exc
        try:
            pages = [page.extract_text() or "" for page in PdfReader(path).pages]
        except Exception as exc:
            raise BlockedError("PDF text extraction failed; original/page rendering remains available: " + type(exc).__name__) from exc
        if not any(p.strip() for p in pages):
            raise BlockedError("PDF has no extractable text; OCR is not provided")
        return "\n".join(f"[page {i+1}]\n{p}" for i, p in enumerate(pages))
    if suffix == ".xlsx":
        return "First worksheet values only; no chart or visual interpretation:\n" + json.dumps(table_rows(path, limit), ensure_ascii=False)
    if suffix == ".docx":
        with zipfile.ZipFile(path) as archive:
            tree = xml_member(archive, "word/document.xml", limit)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        return "\n".join("".join(p.itertext()) for p in tree.findall(".//w:p", ns))
    if suffix in (".sqlite", ".sqlite3", ".db"):
        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            rows = connection.execute("SELECT sql FROM sqlite_master WHERE type IN ('table','view')").fetchall()
            return "Schema only, no data rows:\n" + "\n".join(r[0] or "" for r in rows)
        finally:
            connection.close()
    text = path.read_text(encoding="utf-8-sig")
    if suffix == ".ipynb":
        notebook = json.loads(text)
        return "\n\n".join(f"[cell {i+1} {c.get('cell_type')}]\n" +
            ("".join(c.get("source", [])) if isinstance(c.get("source", []), list) else c["source"])
            for i, c in enumerate(notebook.get("cells", [])) if c.get("cell_type") in ("markdown", "code"))
    if suffix in (".html", ".htm"):
        if any(s in text.lower() for s in ("recaptcha/chall", "verify you are human", "cf-chl-")):
            raise BlockedError("Access challenge page is not source material")
        parser = HTMLText()
        parser.feed(text)
        body = "\n".join(p.strip() for p in "".join(parser.parts).splitlines() if p.strip())
        links = list(dict.fromkeys(parser.links))
        return body + ("\n[linked resources; resolve relative to original URL]\n" + "\n".join(links) if links else "")
    if suffix == ".xml":
        tree = ET.fromstring(text)
        return "\n".join(t.strip() for t in tree.itertext() if t.strip())
    return text


def table_rows(path, limit):
    path = Path(path)
    if limit is not None and path.stat().st_size > limit:
        raise ValueError("Table exceeds source_bytes")
    if path.suffix.lower() == ".xlsx":
        with zipfile.ZipFile(path) as archive:
            ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            strings = []
            if "xl/sharedStrings.xml" in archive.namelist():
                strings = ["".join(n.itertext()) for n in xml_member(archive, "xl/sharedStrings.xml", limit)]
            sheets = sorted(n for n in archive.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"))
            if not sheets:
                raise ValueError("No XLSX worksheet")
            rows = []
            for row in xml_member(archive, sheets[0], limit).findall(".//m:row", ns):
                cells = {}
                for cell in row.findall("m:c", ns):
                    column = 0
                    for letter in cell.attrib["r"]:
                        if not letter.isalpha():
                            break
                        column = column * 26 + ord(letter.upper()) - 64
                    value = cell.findtext("m:v", "", ns)
                    if cell.attrib.get("t") == "s":
                        value = strings[int(value)]
                    elif cell.attrib.get("t") == "inlineStr":
                        value = "".join(cell.itertext())
                    cells[column - 1] = value
                rows.append([cells.get(i, "") for i in range(max(cells, default=-1) + 1)])
    else:
        rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig")),
                               delimiter="\t" if path.suffix.lower() == ".tsv" else ","))
    if not rows:
        return []
    headings = [s.strip().lower() for s in rows[0]]
    if len(headings) != len(set(headings)):
        raise ValueError("Ambiguous duplicate table headings; provide an explicit source list")
    return [dict(zip(headings, row)) for row in rows[1:]]


if __name__ == "__main__":
    import sys
    try:
        Path(sys.argv[2]).write_text(read_text(sys.argv[1], None), encoding="utf-8")
    except Exception as exc:
        print(type(exc).__name__ + ": " + str(exc)[:1000], file=sys.stderr)
        raise SystemExit(1)
