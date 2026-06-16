"""Hybrid Retriever — sparse (keyword) + dense (TF-IDF cosine) + structural rerank.

Retrieves similar problems from the problem bank with evidence budget control.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_BANK_DIR = Path(__file__).resolve().parent.parent / "data" / "problem_bank"

# Evidence budget per route
EVIDENCE_BUDGET: dict[str, dict[str, int]] = {
    "simple":        {"similar_cases": 0, "templates": 1, "precompute": 1},
    "standard":      {"similar_cases": 1, "templates": 1, "precompute": 1},
    "complex":       {"similar_cases": 2, "templates": 2, "precompute": 2},
    "safe_fallback": {"similar_cases": 2, "templates": 2, "precompute": 2},
}

_bank_cache: list[dict[str, Any]] | None = None


def _load_problem_bank() -> list[dict[str, Any]]:
    """Load all problem bank JSONL files."""
    global _bank_cache
    if _bank_cache is not None:
        return _bank_cache

    entries: list[dict[str, Any]] = []
    if not _BANK_DIR.is_dir():
        _bank_cache = entries
        return entries

    for jsonl_file in sorted(_BANK_DIR.glob("*.jsonl")):
        with open(jsonl_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    _bank_cache = entries
    return entries


def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: split on non-alphanumeric + CJK char splitting."""
    text = text.lower()
    # Split CJK characters individually
    tokens = []
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            tokens.append(ch)
        elif ch.isalnum():
            tokens.append(ch)
        else:
            tokens.append(" ")
    joined = "".join(tokens)
    return [t for t in joined.split() if len(t) > 0]


def _sparse_score(query_tokens: list[str], doc_tokens: list[str]) -> float:
    """BM25-like sparse score (simplified)."""
    if not query_tokens or not doc_tokens:
        return 0.0
    doc_counter = Counter(doc_tokens)
    doc_len = len(doc_tokens)
    avg_dl = 100  # assumed average
    k1, b = 1.5, 0.75
    score = 0.0
    for qt in set(query_tokens):
        tf = doc_counter.get(qt, 0)
        if tf == 0:
            continue
        idf = math.log(1 + (100 - tf + 0.5) / (tf + 0.5))
        tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avg_dl))
        score += idf * tf_norm
    return score


def _dense_score(query_tokens: list[str], doc_tokens: list[str]) -> float:
    """TF-IDF cosine similarity (simplified)."""
    if not query_tokens or not doc_tokens:
        return 0.0
    query_counter = Counter(query_tokens)
    doc_counter = Counter(doc_tokens)
    all_tokens = set(query_counter.keys()) | set(doc_counter.keys())
    dot = sum(query_counter.get(t, 0) * doc_counter.get(t, 0) for t in all_tokens)
    norm_q = math.sqrt(sum(v ** 2 for v in query_counter.values()))
    norm_d = math.sqrt(sum(v ** 2 for v in doc_counter.values()))
    if norm_q == 0 or norm_d == 0:
        return 0.0
    return dot / (norm_q * norm_d)


def _structural_boost(query: str, entry: dict[str, Any]) -> float:
    """Boost score if structural features match."""
    boost = 0.0
    entry_domain = entry.get("domain", "")
    entry_type = entry.get("problem_type", "")

    # Domain keyword overlap
    domain_keywords = {
        "微积分": ["积分", "微分", "导数", "极限"],
        "线性代数": ["矩阵", "特征值", "行列式"],
        "偏微分方程": ["偏微分", "PDE", "热方程"],
    }
    for domain, kws in domain_keywords.items():
        if any(kw in query for kw in kws) and entry_domain == domain:
            boost += 0.3
            break

    return min(boost, 0.5)


def retrieve_similar(
    query: str,
    route: str = "standard",
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Retrieve similar problems from the problem bank.

    Args:
        query: Problem text to search for.
        route: Pipeline route (for evidence budget).
        top_k: Maximum results to return.

    Returns:
        List of similar problem dicts, limited by evidence budget.
    """
    bank = _load_problem_bank()
    if not bank:
        return []

    budget = EVIDENCE_BUDGET.get(route, EVIDENCE_BUDGET["standard"])
    max_cases = budget["similar_cases"]
    if max_cases == 0:
        return []

    query_tokens = _tokenize(query)

    scored: list[tuple[float, dict[str, Any]]] = []
    for entry in bank:
        entry_text = entry.get("problem", "")
        entry_tokens = _tokenize(entry_text)

        sparse = _sparse_score(query_tokens, entry_tokens)
        dense = _dense_score(query_tokens, entry_tokens)
        structural = _structural_boost(query, entry)

        combined = 0.4 * sparse + 0.4 * dense + 0.2 * structural
        if combined > 0:
            scored.append((combined, entry))

    scored.sort(key=lambda x: -x[0])
    results = [entry for _, entry in scored[:max_cases]]

    return results
