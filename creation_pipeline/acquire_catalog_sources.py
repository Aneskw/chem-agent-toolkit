#!/usr/bin/env python3
"""Acquire publicly reachable paper full text and build an extraction manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import ssl
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent
OUT = HERE / "acquired"
USER_AGENT = "ChemSkillNet-source-acquirer/1.0"


def ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    cafile = "/etc/ssl/cert.pem"
    if Path(cafile).is_file():
        context.load_verify_locations(cafile=cafile)
    return context


def get(url: str, limit: int = 50_000_000) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, context=ssl_context(), timeout=35) as response:
        data = response.read(limit + 1)
        return data, response.headers.get_content_type()


def clean_html(data: bytes) -> bool:
    sample = data[:5000].lower()
    return b"<html" in sample or b"<!doctype" in sample or b"<article" in sample


def candidates(row: dict) -> list[tuple[str, str]]:
    paper_id = row["paper_id"]
    url = row.get("url", "")
    parsed = urllib.parse.urlsplit(url)
    output: list[tuple[str, str]] = []
    if parsed.netloc.endswith("arxiv.org"):
        ident = parsed.path.rstrip("/").split("/")[-1]
        output.append((f"https://arxiv.org/pdf/{ident}.pdf", "arxiv_pdf"))
    if parsed.netloc == "openreview.net":
        query = urllib.parse.parse_qs(parsed.query)
        if query.get("id"):
            output.append((f"https://openreview.net/pdf?id={query['id'][0]}", "openreview_pdf"))
    if "proceedings.mlr.press" in parsed.netloc and parsed.path.endswith(".html"):
        output.append((url, "pmlr_html"))
    if "papers.nips.cc" in parsed.netloc and "-Abstract.html" in parsed.path:
        output.append((url.replace("-Abstract.html", ".pdf"), "neurips_pdf"))
    if "jcheminf.biomedcentral.com/articles/" in url:
        output.append((url.rstrip("/") + ".pdf", "bmc_pdf"))
    if "nature.com/articles/" in url:
        output.append((url.rstrip("/") + ".pdf", "nature_pdf"))
    if "chemrxiv.org/engage/chemrxiv/article-details/" in url:
        ident = parsed.path.rstrip("/").split("/")[-1]
        output.append((f"https://chemrxiv.org/engage/api-gateway/chemrxiv/assets/orp/resource/item/{ident}/content", "chemrxiv_api"))
    doi = row.get("doi", "").strip()
    if doi:
        encoded = urllib.parse.quote(doi, safe="")
        # OpenAlex and Unpaywall expose OA locations even when the catalog URL is
        # a publisher landing page.  The mailto parameter keeps the request in
        # their polite pool and avoids treating a transient rate limit as a
        # permanent missing source.
        output.append((f"https://api.openalex.org/works/https://doi.org/{encoded}?mailto=chem.skillnet@example.org", "openalex_record"))
        output.append((f"https://api.unpaywall.org/v2/{encoded}?email=chem.skillnet@example.org", "unpaywall_record"))
        output.append((f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:{encoded}&format=json", "europepmc_search"))
        if "onlinelibrary.wiley.com" in url:
            output.append((url.replace("/abs/", "/pdf/") if "/abs/" in url else url.replace("/abstract/", "/pdf/"), "wiley_pdf"))
    # Keep order but remove duplicate URLs.
    seen = set()
    return [(u, k) for u, k in output if not (u in seen or seen.add(u))]


def openalex_links(data: bytes) -> list[tuple[str, str]]:
    try:
        record = json.loads(data)
    except json.JSONDecodeError:
        return []
    links = []
    for location in record.get("locations", []) or []:
        for key in ("pdf_url", "landing_page_url"):
            value = location.get(key)
            if value:
                links.append((value, "openalex_" + key))
    return links


def unpaywall_links(data: bytes) -> list[tuple[str, str]]:
    try:
        record = json.loads(data)
    except json.JSONDecodeError:
        return []
    links = []
    for location in [record.get("best_oa_location"), *(record.get("oa_locations") or [])]:
        if not location:
            continue
        for key in ("url_for_pdf", "url"):
            value = location.get(key)
            if value:
                links.append((value, "unpaywall_" + key))
    return links


def valid_document(data: bytes, content_type: str) -> str | None:
    if data.startswith(b"%PDF-"):
        return ".pdf"
    if clean_html(data) or "html" in content_type:
        return ".html"
    return None


def main() -> int:
    rows = [json.loads(line) for line in (HERE / "papers.jsonl").read_text().splitlines() if line.strip()]
    results = []
    manifest_jobs = []
    for row in rows:
        paper_id = row["paper_id"]
        target = OUT / paper_id
        target.mkdir(parents=True, exist_ok=True)
        queue = candidates(row)
        acquired = None
        attempted = []
        while queue and acquired is None:
            url, kind = queue.pop(0)
            try:
                data, content_type = get(url)
                if kind == "openalex_record":
                    queue[0:0] = openalex_links(data)
                    attempted.append({"url": url, "kind": kind, "status": "metadata"})
                    continue
                if kind == "unpaywall_record":
                    queue[0:0] = unpaywall_links(data)
                    attempted.append({"url": url, "kind": kind, "status": "metadata"})
                    continue
                if kind == "europepmc_search":
                    attempted.append({"url": url, "kind": kind, "status": "metadata"})
                    continue
                suffix = valid_document(data, content_type)
                if not suffix:
                    attempted.append({"url": url, "kind": kind, "status": "not_document", "content_type": content_type})
                    continue
                destination = target / f"paper{suffix}"
                destination.write_bytes(data)
                acquired = {"url": url, "kind": kind, "path": str(destination.relative_to(HERE)),
                            "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
                attempted.append({"url": url, "kind": kind, "status": "acquired"})
            except Exception as error:  # Keep the 52-paper sweep moving.
                attempted.append({"url": url, "kind": kind, "status": "error", "error": str(error)[:240]})
        if acquired:
            manifest_jobs.append({"paper_id": paper_id, "source_type": "paper", "title": row["title"],
                                  "sources": [{"path": acquired["path"], "role": "paper",
                                               "url": acquired["url"], "sha256": acquired["sha256"]}]})
        results.append({"paper_id": paper_id, "title": row["title"], "source_url": row.get("url", ""),
                        "status": "acquired" if acquired else "source_missing",
                        "acquired": acquired, "attempts": attempted})
        print(json.dumps({"paper_id": paper_id, "status": results[-1]["status"],
                          "source": acquired["kind"] if acquired else None}, ensure_ascii=False), flush=True)
    report = {"total": len(rows), "acquired": sum(x["status"] == "acquired" for x in results),
              "source_missing": sum(x["status"] == "source_missing" for x in results), "papers": results}
    (HERE / "acquisition_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    manifest = {"max_context_chars": 120000, "jobs": manifest_jobs}
    (HERE / "acquired_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "finished", "report": str(HERE / "acquisition_report.json"),
                      "manifest": str(HERE / "acquired_manifest.json"),
                      "acquired": report["acquired"], "source_missing": report["source_missing"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
