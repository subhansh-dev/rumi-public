"""
Tests for the score of record (no network required).

The failure being covered: a report carried four 0-100 numbers and the terminal
printed the one the pipeline gave itself. The external harness score is the only
measurement the pipeline cannot influence, so it must be the headline.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from discovery.score_of_record import score_of_record  # noqa: E402


def _report(external=None, self_score=12.1, refinement=73, grade="F"):
    report = {"phases": {"discovery_scoring": {"discovery_score": self_score,
                                               "grade": grade,
                                               "domain_weighted_score": 50.0}}}
    if external is not None:
        report["external_eval"] = external
    if refinement is not None:
        report["refinement"] = {"scoring": {"overall_score": refinement, "grade": "B"}}
    return report


def test_external_harness_is_the_score_of_record():
    out = score_of_record(_report(external={
        "external_score": 51.0, "grade": "C", "flags": ["no_citations"]}))
    assert out["value"] == 51.0
    assert out["grade"] == "C"
    assert out["source"] == "external_harness"
    assert out["verified"] is True
    assert out["flags"] == ["no_citations"]


def test_diagnostics_are_retained_but_not_the_headline():
    out = score_of_record(_report(external={"external_score": 51.0, "grade": "C"}))
    assert out["diagnostics"]["self_reported"]["value"] == 12.1
    assert out["diagnostics"]["self_reported"]["domain_weighted"] == 50.0
    assert out["diagnostics"]["refinement"]["value"] == 73


def test_missing_external_eval_falls_back_to_a_flagged_self_score():
    out = score_of_record(_report())
    assert out["value"] == 12.1
    assert out["source"] == "self_reported"
    assert out["verified"] is False
    assert "unverified_self_score" in out["flags"]


def test_refinement_self_rating_never_becomes_the_headline():
    out = score_of_record(_report(self_score=None, refinement=73))
    assert out["value"] is None
    assert out["source"] == "self_reported"
    # ... even though it is the only number present
    assert out["diagnostics"]["refinement"]["value"] == 73


def test_junk_scores_are_rejected():
    for junk in (True, "51", None, [], {}):
        out = score_of_record(_report(external={"external_score": junk,
                                                "grade": "C"}))
        assert out["source"] == "self_reported", junk
        assert out["value"] == 12.1, junk


def test_empty_report_does_not_crash():
    out = score_of_record({})
    assert out["value"] is None
    assert out["source"] == "self_reported"
    assert out["verified"] is False


def test_non_dict_input_does_not_crash():
    assert score_of_record(None)["value"] is None
    assert score_of_record("nope")["value"] is None


def test_zero_is_a_real_score_not_a_missing_value():
    out = score_of_record(_report(external={"external_score": 0, "grade": "F"}))
    assert out["value"] == 0.0
    assert out["source"] == "external_harness"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
