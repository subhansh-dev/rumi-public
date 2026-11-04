"""
score_of_record.py — the one number a reader should quote.

A finished report contains four different quality numbers, all on a 0-100 scale
and none of them labelled as authoritative:

    discovery_scoring.discovery_score         (pipeline grades itself)
    discovery_scoring.domain_weighted_score   (same score, re-weighted)
    refinement.scoring.overall_score          (an LLM rates its own work)
    external_eval.external_score              (frozen harness, out of reach)

Quoting any of the first three as "the score" is a claim the pipeline can make
about itself. The external harness is the only measurement the pipeline cannot
influence, so it is the score of record. The others are kept — they are useful
diagnostics — but they are labelled as such.

`score_of_record` is pure and total: it never raises, and a missing or junk
number degrades to a labelled fallback instead of a confident headline.
"""
from __future__ import annotations

from typing import Any


def _number(value: Any) -> float | None:
    """Accept a real number only. Booleans and numeric strings are not scores."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def score_of_record(report: dict) -> dict:
    """Return the authoritative score block for a finished report."""
    report = report if isinstance(report, dict) else {}
    external = report.get("external_eval") or {}
    self_scoring = ((report.get("phases") or {}).get("discovery_scoring") or {})
    refinement = ((report.get("refinement") or {}).get("scoring") or {})

    diagnostics = {
        "self_reported": {
            "value": _number(self_scoring.get("discovery_score")),
            "grade": self_scoring.get("grade"),
            "domain_weighted": _number(self_scoring.get("domain_weighted_score")),
            "source": "discovery_scorer (pipeline, self-scored)",
        },
        "refinement": {
            "value": _number(refinement.get("overall_score")),
            "grade": refinement.get("grade"),
            "source": "refinement_pipeline (LLM self-rating)",
        },
    }

    external_value = _number(external.get("external_score"))
    if external_value is not None:
        return {
            "value": round(external_value, 1),
            "grade": external.get("grade"),
            "source": "external_harness",
            "verified": True,
            "definition": "eval/harness.py — independent, frozen scorer",
            "flags": list(external.get("flags") or []),
            "diagnostics": diagnostics,
        }

    # No external measurement: fall back to the self score, but never present it
    # as verified. If that is missing too, there is no score of record at all —
    # in particular, the refinement self-rating never becomes the headline.
    self_value = diagnostics["self_reported"]["value"]
    return {
        "value": round(self_value, 1) if self_value is not None else None,
        "grade": diagnostics["self_reported"]["grade"],
        "source": "self_reported",
        "verified": False,
        "definition": ("discovery_scorer — self-scored; no external measurement "
                       "present, so this number is not independently verified"),
        "flags": ["unverified_self_score"],
        "diagnostics": diagnostics,
    }
