#!/usr/bin/env python3
"""R&D multi-source scanner for Relic.

Fetches papers from ArXiv, Semantic Scholar, and HuggingFace daily papers.
Outputs a deduplicated JSON list to stdout.

Usage:
    python3 scripts/rd_scan.py [--days N]
    python3 scripts/rd_scan.py --days 1    # default: papers from last 1 day

Sources:
    - ArXiv: 3 keyword queries, filtered to last N days, sorted by submission date
    - Semantic Scholar: 2 relevance queries, year=current, with rate-limit sleep
    - HuggingFace daily_papers: today's curated 50 papers, pre-filtered by keyword

Output format (one JSON array):
    [{"source": str, "arxiv_id": str, "title": str, "abstract": str,
      "url": str, "published": str}, ...]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

ARXIV_NS = {"a": "http://www.w3.org/2005/Atom"}

ARXIV_QUERIES = [
    # title-focused to avoid noise from author names / broad field matches
    "ti:personality AND abs:LLM",
    "ti:personality AND abs:agent",
    "abs:biofeedback AND abs:personality",
    "ti:humanness OR abs:companion-AI OR abs:relational-agent",
]

SS_QUERIES = [
    "personality modeling language model",
    "companion AI relational humanness biofeedback",
]

HF_KEYWORDS = {
    "personality", "humanness", "biofeedback", "hrv", "companion",
    "relational agent", "big five", "trait inference", "multi-agent",
    "turing", "persona modeling", "character modeling",
}


def _fetch(url: str, headers: dict | None = None, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "Relic-RD/1.0"})
    return urllib.request.urlopen(req, timeout=timeout).read()


def _date_range(days: int) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    frm = (now - timedelta(days=days)).strftime("%Y%m%d")
    to = now.strftime("%Y%m%d")
    return frm, to


def scan_arxiv(days: int = 1, max_results: int = 5) -> list[dict]:
    frm, to = _date_range(days)
    papers: list[dict] = []
    for query in ARXIV_QUERIES:
        date_query = f"{query} AND submittedDate:[{frm} TO {to}]"
        params = urllib.parse.urlencode({
            "search_query": date_query,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        })
        url = f"https://export.arxiv.org/api/query?{params}"
        try:
            raw = _fetch(url)
            root = ET.fromstring(raw)
            for entry in root.findall("a:entry", ARXIV_NS):
                arxiv_url = entry.find("a:id", ARXIV_NS).text.strip()
                arxiv_id = arxiv_url.split("/abs/")[-1].split("v")[0]
                title_el = entry.find("a:title", ARXIV_NS)
                abstract_el = entry.find("a:summary", ARXIV_NS)
                published_el = entry.find("a:published", ARXIV_NS)
                papers.append({
                    "source": "arxiv",
                    "arxiv_id": arxiv_id,
                    "title": (title_el.text or "").strip().replace("\n", " "),
                    "abstract": (abstract_el.text or "").strip().replace("\n", " ")[:500],
                    "url": f"https://arxiv.org/abs/{arxiv_id}",
                    "published": (published_el.text or "")[:10],
                })
        except Exception as exc:
            print(f"[rd_scan] ArXiv error ({query[:40]}): {exc}", file=sys.stderr)
    return papers


def scan_semantic_scholar(days: int = 1, max_per_query: int = 5) -> list[dict]:
    now = datetime.now(timezone.utc)
    date_from = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    date_to = now.strftime("%Y-%m-%d")
    papers: list[dict] = []
    for i, query in enumerate(SS_QUERIES):
        if i > 0:
            time.sleep(3)  # respect rate limit: ~1 req/3sec for unauthenticated
        params = urllib.parse.urlencode({
            "query": query,
            "fields": "title,abstract,url,publicationDate,externalIds",
            "publicationDateOrYear": f"{date_from}:{date_to}",
            "limit": max_per_query,
        })
        url = f"https://api.semanticscholar.org/graph/v1/paper/search?{params}"
        try:
            raw = _fetch(url)
            data = json.loads(raw)
            for p in data.get("data", []):
                arxiv_id = p.get("externalIds", {}).get("ArXiv", "")
                papers.append({
                    "source": "semantic_scholar",
                    "arxiv_id": arxiv_id,
                    "title": (p.get("title") or "").strip(),
                    "abstract": (p.get("abstract") or "").strip()[:500],
                    "url": (
                        f"https://arxiv.org/abs/{arxiv_id}"
                        if arxiv_id
                        else p.get("url", "")
                    ),
                    "published": p.get("publicationDate") or str(p.get("year", "")),
                })
        except Exception as exc:
            print(f"[rd_scan] SemanticScholar error ({query[:40]}): {exc}", file=sys.stderr)
    return papers


def scan_huggingface(days: int = 1) -> list[dict]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    url = f"https://huggingface.co/api/daily_papers?date={today}"
    papers: list[dict] = []
    try:
        raw = _fetch(url)
        items = json.loads(raw)
        for item in items:
            pap = item.get("paper", {})
            title = (pap.get("title") or "").lower()
            summary = (pap.get("summary") or "").lower()
            kws = " ".join(k.lower() for k in (pap.get("ai_keywords") or []))
            combined = f"{title} {summary} {kws}"
            if any(kw in combined for kw in HF_KEYWORDS):
                arxiv_id = pap.get("id", "")
                papers.append({
                    "source": "huggingface",
                    "arxiv_id": arxiv_id,
                    "title": pap.get("title", "").strip(),
                    "abstract": (pap.get("summary") or "").strip()[:500],
                    "url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
                    "published": (pap.get("publishedAt") or "")[:10],
                    "upvotes": pap.get("upvotes", 0),
                })
    except Exception as exc:
        print(f"[rd_scan] HuggingFace error: {exc}", file=sys.stderr)
    return papers


def deduplicate(papers: list[dict]) -> list[dict]:
    seen_ids: set[str] = set()
    seen_titles: set[str] = set()
    result: list[dict] = []
    for p in papers:
        arxiv_id = p.get("arxiv_id", "").strip()
        title_key = p.get("title", "").lower()[:60]
        if arxiv_id and arxiv_id in seen_ids:
            continue
        if title_key in seen_titles:
            continue
        if arxiv_id:
            seen_ids.add(arxiv_id)
        seen_titles.add(title_key)
        result.append(p)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Relic R&D multi-source scanner")
    parser.add_argument("--days", type=int, default=1, help="ArXiv: papers from last N days (default: 1)")
    args = parser.parse_args()

    papers: list[dict] = []
    papers += scan_arxiv(days=args.days)
    papers += scan_semantic_scholar(days=args.days)
    papers += scan_huggingface(days=args.days)
    papers = deduplicate(papers)

    json.dump(papers, sys.stdout, ensure_ascii=False, indent=2)
    print(file=sys.stderr)
    print(f"[rd_scan] Total unique papers: {len(papers)}", file=sys.stderr)


if __name__ == "__main__":
    main()
