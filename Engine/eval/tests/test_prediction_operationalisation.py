"""
Tests for prediction operationalisation (no network required).

The failure being covered: winning theories carry predictions like

    "The resonance tensor will have a significant impact on the affective
     states, with a correlation of 0.5"

which has a number but no instrument, so it is not testable. predictive_power
and EMPC prediction grounding both (correctly) score it zero. The repair asks
once for the missing measurement instead of regenerating the theories.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from discovery.theory_competition import TheoryCompetition  # noqa: E402
from discovery.theory_schema import prediction_has_method  # noqa: E402

VAGUE = "The resonance tensor will raise affective momentum by a correlation of 0.5"
GROUNDED = ("The measured BOLD signal in the amygdala will rise by beta > 0.3 "
            "using fMRI")


def _theory(name, *predictions):
    return {"name": name, "predictions": [{"statement": p} for p in predictions]}


def _compete(llm_call):
    return TheoryCompetition(graph=None, llm_call=llm_call)


def test_measurement_is_attached_by_id():
    calls = []

    def fake_llm(prompt, max_tokens=None):
        calls.append(prompt)
        body = json.loads(prompt.split("PREDICTIONS:", 1)[1].split("Output JSON", 1)[0])
        return json.dumps({"measurements": [
            {"id": item["id"], "measurement": f"assay {item['id']}, threshold >0.{item['id'] + 1}"}
            for item in body
        ]})

    theories = _compete(fake_llm)._operationalise_predictions([
        _theory("A", VAGUE),
        _theory("B", VAGUE + " in cohort two"),
    ])

    assert len(calls) == 1
    for theory in theories:
        assert theory["predictions"][0]["measurement"].startswith("assay")
    assert all(prediction_has_method(t["predictions"][0]) for t in theories)


def test_already_grounded_predictions_are_not_sent():
    prompts = []

    def fake_llm(prompt, max_tokens=None):
        prompts.append(prompt)
        return json.dumps({"measurements": []})

    theories = [{"name": "A", "predictions": [{"statement": GROUNDED}]}]
    out = _compete(fake_llm)._operationalise_predictions(theories)

    assert out == theories
    assert prompts == []  # nothing missing -> no call at all


def test_ungrounded_predictions_are_sent_but_grounded_ones_are_not():
    prompts = []

    def fake_llm(prompt, max_tokens=None):
        prompts.append(prompt)
        return json.dumps({"measurements": [{"id": 0, "measurement": "qPCR, >2-fold"}]})

    theories = [{"name": "A", "predictions": [
        {"statement": GROUNDED},
        {"statement": VAGUE},
    ]}]
    _compete(fake_llm)._operationalise_predictions(theories)

    assert GROUNDED not in prompts[0]
    assert VAGUE in prompts[0]
    assert theories[0]["predictions"][0].get("measurement") is None
    assert theories[0]["predictions"][1]["measurement"] == "qPCR, >2-fold"


def test_empty_model_answer_leaves_theories_untouched():
    def fake_llm(prompt, max_tokens=None):
        return json.dumps({"measurements": [{"id": 0, "measurement": ""}]})

    theory = _theory("A", VAGUE)
    out = _compete(fake_llm)._operationalise_predictions([theory])
    assert out[0]["predictions"][0] == {"statement": VAGUE}


def test_model_failure_leaves_theories_untouched():
    def boom(prompt, max_tokens=None):
        raise RuntimeError("provider down")

    theory = _theory("A", VAGUE)
    out = _compete(boom)._operationalise_predictions([theory])
    assert out[0]["predictions"][0] == {"statement": VAGUE}


def test_no_llm_leaves_theories_untouched():
    theory = _theory("A", VAGUE)
    out = _compete(None)._operationalise_predictions([theory])
    assert out[0]["predictions"][0] == {"statement": VAGUE}


def test_repair_is_bounded_to_25_predictions():
    prompts = []

    def fake_llm(prompt, max_tokens=None):
        prompts.append(prompt)
        return json.dumps({"measurements": []})

    theories = [_theory(f"T{i}", VAGUE + f" in cohort {i}") for i in range(40)]
    _compete(fake_llm)._operationalise_predictions(theories)

    assert prompts[0].count('"statement"') == 25
