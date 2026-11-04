"""
Tests for the theory schema normaliser (no network required).

Regression cover for the four silent failures it replaces:

  * `len("Resonance tensor, ...")` == 34 → simplicity floored at 10
  * `len("Observations 1-6, ...")` == 35 → explanatory_power clamped at 100
  * `for p in "Agents with higher APE..."` → predictions 'A', 'g', 'e' (520 of them)
  * `for p in {"prediction1": "..."}` → predictions 'prediction1'
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from discovery.discovery_scorer import DiscoveryScorer  # noqa: E402
from discovery.empc_pipeline import EMPCPipeline  # noqa: E402
from discovery.theory_schema import (  # noqa: E402
    as_items,
    normalize_predictions,
    normalize_theory,
    prediction_has_method,
    prediction_has_quantity,
    prediction_is_grounded,
)

QUANT_PRED = "The measured cross-section should be 2.4 +/- 0.3 nb at 8 TeV"
VAGUE_PRED = "The effect should become stronger under load"
STR_PREDS = "Agents with higher APE values will exhibit more adaptive behaviour"


def _scorer():
    return DiscoveryScorer()


# ── predictions: three shapes, one canonical result ───────────────────────
def test_string_predictions_do_not_leak_characters():
    preds = normalize_predictions(STR_PREDS)
    assert len(preds) == 1
    assert preds[0]["statement"] == STR_PREDS
    assert [p["statement"] for p in preds] != ["A", "g", "e"]


def test_dict_predictions_do_not_leak_keys():
    preds = normalize_predictions({"prediction1": QUANT_PRED, "prediction2": VAGUE_PRED})
    assert [p["statement"] for p in preds] == [QUANT_PRED, VAGUE_PRED]
    assert "prediction1" not in [p["statement"] for p in preds]


def test_list_of_strings_becomes_statements():
    preds = normalize_predictions([QUANT_PRED, VAGUE_PRED])
    assert len(preds) == 2
    assert all(isinstance(p, dict) for p in preds)
    assert preds[0]["statement"] == QUANT_PRED


def test_placeholder_fragments_are_dropped():
    assert normalize_predictions(["A", "g", "e", ""]) == []
    assert normalize_predictions({"prediction1": "x"}) == []


def test_predictions_are_deduplicated():
    preds = normalize_predictions([QUANT_PRED, QUANT_PRED.upper()])
    assert len(preds) == 1


# ── hidden variables / explains: containers, not characters ───────────────
def test_hidden_variables_string_is_one_item():
    hvs = normalize_theory({"hidden_variables": "Resonance tensor, affective momentum"})
    assert isinstance(hvs["hidden_variables"], list)
    assert len(hvs["hidden_variables"]) == 1


def test_explains_string_is_one_item():
    t = normalize_theory({"explains": "Observations 1-6, knowledge gaps 1-6"})
    assert len(t["explains"]) == 1


# ── the scoring consequences ─────────────────────────────────────────────
def test_simplicity_not_floored_by_string_length():
    theory = {
        "name": "T",
        "description": "x",
        "hidden_variables": "Resonance tensor, affective momentum",
        "key_assumptions": "The tensor is second order and the field is scalar",
    }
    simplicity = _scorer().score(theory)["scores"]["simplicity"]
    # Old behaviour: 80 - 4*34 - 3*45 → floor 10
    assert simplicity > 10, simplicity


def test_explanatory_not_saturated_by_string_length():
    theory = {"name": "T", "description": "x", "explains": "Observations 1-6, knowledge gaps 1-6"}
    explanatory = _scorer().score(theory)["scores"]["explanatory_power"]
    # Old behaviour: 40 + 6*35 → clamp 100
    assert explanatory < 100, explanatory


def test_predictive_power_is_quality_gated_not_a_counter():
    s = _scorer()
    vague = [{"statement": f"{VAGUE_PRED} in sample {chr(97 + i)}"} for i in range(6)]
    quantified_only = [{"statement": f"Effect of {i} should be 0.{i} units"} for i in range(6)]
    grounded = [{"statement": f"{QUANT_PRED} (run {i})"} for i in range(6)]

    vague_score = s._score_predictive(vague)
    quantified_score = s._score_predictive(quantified_only)
    grounded_score = s._score_predictive(grounded)

    # The old formula gave 100 for six vague predictions.
    assert vague_score < 40, vague_score
    assert vague_score < quantified_score < grounded_score
    assert grounded_score >= 90, grounded_score


def test_predictive_power_rewards_nothing_when_empty():
    assert _scorer()._score_predictive([]) == 10.0


# ── shared quality predicates ────────────────────────────────────────────
def test_quality_predicates():
    assert prediction_has_quantity(QUANT_PRED)
    assert prediction_has_method(QUANT_PRED)          # "measured"
    assert prediction_is_grounded(QUANT_PRED)

    assert not prediction_has_quantity(VAGUE_PRED)
    assert not prediction_is_grounded(VAGUE_PRED)


def test_measurement_field_counts_as_the_method():
    pred = {"statement": "The effect will be 0.4 units larger", "measurement": "fMRI BOLD, beta > 0.3"}
    assert prediction_has_quantity(pred)
    assert prediction_has_method(pred)        # method lives in its own field
    assert prediction_is_grounded(pred)


def test_test_method_is_canonicalised_to_measurement():
    preds = normalize_predictions([{
        "statement": QUANT_PRED,
        "test_method": "liquid chromatography, 5 ppm detection limit",
    }])
    assert preds[0]["measurement"] == "liquid chromatography, 5 ppm detection limit"
    assert prediction_has_method(preds[0])


def test_string_predictions_get_an_empty_measurement_field():
    pred = normalize_predictions([QUANT_PRED])[0]
    assert pred["measurement"] == ""


# ── EMPC: grounding can finally be non-zero ──────────────────────────────
def test_empc_grounds_quantified_measurable_predictions():
    theories = [{"name": "T", "predictions": [
        {"statement": QUANT_PRED},
        {"statement": VAGUE_PRED},
    ]}]
    out = EMPCPipeline()._ground_predictions(theories, None)
    assert len(out["predictions"]) == 2
    assert out["grounding_score"] == 0.5


def test_empc_does_not_explode_a_string_prediction():
    theories = [{"name": "T", "predictions": STR_PREDS}]
    out = EMPCPipeline()._ground_predictions(theories, None)
    assert len(out["predictions"]) == 1


def test_empc_does_not_explode_dict_predictions():
    theories = [{"name": "T", "predictions": {"prediction1": QUANT_PRED}}]
    out = EMPCPipeline()._ground_predictions(theories, None)
    assert len(out["predictions"]) == 1
    assert out["predictions"][0]["prediction"] == QUANT_PRED


# ── idempotence / totality ───────────────────────────────────────────────
def test_normalize_is_idempotent():
    raw = {
        "name": "T",
        "predictions": {"prediction1": QUANT_PRED},
        "explains": "Observations 1-6",
        "hidden_variables": "a, b",
        "key_assumptions": ["x", "y"],
        "steps": "one step",
    }
    once = normalize_theory(raw)
    twice = normalize_theory(once)
    assert once == twice


def test_normalize_survives_junk():
    assert normalize_theory(None) == {}
    assert normalize_theory("not a theory") == {}
    assert normalize_theory({"predictions": 42})["predictions"] == []
    assert as_items(None) == []


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
