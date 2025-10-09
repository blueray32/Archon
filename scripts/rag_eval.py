#!/usr/bin/env python3
"""
RAG Evaluation Harness (lightweight)

Runs top-k retrieval for a set of queries and prints JSON results that are
easy to diff across weighting/threshold changes.

Usage:
  python scripts/rag_eval.py --api http://localhost:8181 --k 10 \
    --query "embedding model" --query "pydantic test model"
"""

import argparse
import json
import sys
from urllib import request


def rag_query(api: str, query: str, k: int) -> dict:
    url = f"{api.rstrip('/')}/api/rag/query"
    payload = json.dumps({"query": query, "match_count": k}).encode()
    req = request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8181", help="Backend API base URL")
    ap.add_argument("--k", type=int, default=10, help="Top-k results per query")
    ap.add_argument("--query", action="append", default=["test"], help="Query string (repeatable)")
    args = ap.parse_args()

    out = {}
    for q in args.query:
        try:
            data = rag_query(args.api, q, args.k)
            results = data.get("results", [])
            out[q] = [
                {
                    "id": r.get("id"),
                    "sim": r.get("similarity_score"),
                    "src": (r.get("metadata") or {}).get("source_id"),
                }
                for r in results
            ]
        except Exception as e:
            out[q] = {"error": str(e)}

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)

