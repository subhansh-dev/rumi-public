"""
theory_schema.py — the one typed shape for a theory.

A theory dict arrives from LLM JSON with its list fields as **list, str or dict**,
depending on what the model felt like emitting. Consumers that assume a list then
do the wrong thing silently:

    len("Resonance tensor, affective momentum")   -> 34  (character count)
    for p in "Agents with higher APE will..."     -> 'A', 'g', 'e', ...
    for p in {"prediction1": "..."}               -> 'prediction1'

That is not a scoring problem, it is a missing schema. This module defines the
canonical shape and the one function that produces it:

    predictions      : list[dict]  {"statement", "type", "falsification", "measurement"}
    explains         : list[str]
    fails_to_explain : list[str]
    key_assumptions  : list[str]
    steps            : list[str]
    hidden_variables : list[str | dict]   (container always a list)
    mechanism        : str

`normalize_theory` is total and idempotent: it never raises on junk input and
normalizing twice is the same as normalizing once. Apply it at the two
boundaries (theory creation, report finalization) and consumers can trust `len()`
to mean "number of items".

The prediction-quality predicates live here too, so the discovery scorer and the
EMPC pipeline share one definition of a grounded prediction instead of drifting
apart.
"""
from __future__ import annotations

import re
from typing import Any

# Statement-bearing keys, in priority order.
_STATEMENT_KEYS = ("statement", "description", "prediction", "text", "claim", "value")
_TYPE_KEYS = ("type", "kind", "category")
_FALSIFICATION_KEYS = (
    "falsification", "falsified_if", "falsification_criteria",
    "refutation", "disproof",
)
# How the prediction would be measured. Prompted as "measurement" in theory
# generation and "test_method" in the prediction engine; both are canonicalised
# to "measurement" so the predicate has one thing to look at.
_MEASUREMENT_KEYS = (
    "measurement", "test_method", "method", "procedure",
    "operationalisation", "operationalization", "instrument",
)
_NAME_KEYS = ("name", "statement", "variable", "symbol", "description", "mechanism",
              "text", "reason", "observation", "label")

_QUANTITY_RE = re.compile(r"\d")

# A prediction is "operationalised" if it names how it would be measured.
# Stems and instrument names both count: "fMRI" is a measurement, and so is
# "spectroscopy". Kept deliberately broad so a domain-specific instrument is not
# penalised for being absent from this list's vocabulary.
_METHOD_WORDS = (
    "measure", "measured", "observe", "observed", "detect", "detected",
    "test", "tested", "experiment", "spectroscop", "imaging", "assay",
    "survey", "calibrat", "instrument", "sampl", "record", "monitor",
    "fmri", "eeg", "meg", "ecg", "mri", "pet scan", "qpcr", "pcr",
    "microscop", "chromatograph", "sequencing", "immuno", "sensor",
    "detector", "telescope", "spectrometer", "accelerometer", "telemetry",
    "questionnaire", "interview", "clinical trial", "benchmark",
    "dataset", "database", "regression", "meta-analysis", "statistical test",
)

_BULLET_RE = re.compile(r"^\s*(?:[-*\u2022]|\d{1,2}[.)])\s+")
_INLINE_NUMBERING_RE = re.compile(r"(?:^|\s)\d{1,2}[.)]\s+\S")


def _clean(text: Any) -> str:
    s = str(text or "").strip()
    s = _BULLET_RE.sub("", s)
    return s.strip()


def _first_str(record: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
    return ""


def _looks_like_record(value: dict) -> bool:
    """True when a dict is ONE record, not a mapping of id -> text."""
    return any(isinstance(value.get(k), str) and value.get(k, "").strip()
               for k in _STATEMENT_KEYS)


def _split_string(text: str) -> list[str]:
    """Split a multi-item string; a single sentence stays a single item."""
    stripped = text.strip()
    if not stripped:
        return []

    lines = [ln for ln in stripped.splitlines() if ln.strip()]
    if len(lines) > 1:
        items = [_clean(ln) for ln in lines]
        return [i for i in items if i]

    if len(_INLINE_NUMBERING_RE.findall(stripped)) >= 2:
        parts = re.split(r"(?:^|\s)\d{1,2}[.)]\s+", stripped)
        return [_clean(p) for p in parts if _clean(p)]

    return [_clean(stripped)]


def as_items(value: Any) -> list[Any]:
    """Coerce any list-ish field to a list of items, preserving item types.

    dict  -> values (or [dict] when the dict is itself one record)
    str   -> newline/numbering split (one sentence = one item)
    list  -> as-is
    None  -> []
    """
    if value is None:
        return []
    if isinstance(value, dict):
        if _looks_like_record(value):
            return [value]
        return [v for v in value.values() if v not in (None, "", [], {})]
    if isinstance(value, (list, tuple, set)):
        return list(value)
    if isinstance(value, str):
        return _split_string(value)
    return [value]


def normalize_predictions(value: Any) -> list[dict]:
    """Every prediction becomes
    {statement, type, falsification, measurement}; junk is dropped.

    Statements shorter than 3 characters are discarded, which is what keeps
    'A', 'g', 'e' (string iteration) and 'prediction1' (dict keys) out of the
    report.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for item in as_items(value):
        if isinstance(item, dict):
            record = dict(item)
            statement = _first_str(record, _STATEMENT_KEYS)
            record["statement"] = statement
            record["type"] = _first_str(record, _TYPE_KEYS)
            record["falsification"] = _first_str(record, _FALSIFICATION_KEYS)
            record["measurement"] = _first_str(record, _MEASUREMENT_KEYS)
        elif isinstance(item, str):
            statement = _clean(item)
            record = {"statement": statement, "type": "", "falsification": "",
                      "measurement": ""}
        else:
            continue

        statement = _clean(record.get("statement"))
        if len(statement) < 3:
            continue
        key = statement.casefold()
        if key in seen:
            continue
        seen.add(key)
        record["statement"] = statement
        out.append(record)
    return out


def normalize_str_list(value: Any) -> list[str]:
    """Always a list of non-empty strings."""
    out: list[str] = []
    for item in as_items(value):
        if isinstance(item, dict):
            text = _first_str(item, _NAME_KEYS)
        else:
            text = _clean(item)
        if text:
            out.append(text)
    return out


def normalize_hidden_variables(value: Any) -> list[Any]:
    """Always a list; item type is preserved (str stays str, dict stays dict)."""
    out: list[Any] = []
    for item in as_items(value):
        if isinstance(item, str):
            text = _clean(item)
            if text:
                out.append(text)
        elif isinstance(item, dict):
            record = dict(item)
            if not _first_str(record, _NAME_KEYS):
                continue
            out.append(record)
    return out


def normalize_theory(theory: Any) -> dict:
    """Return a copy of ``theory`` with every list field in canonical shape.

    Idempotent and total: unknown fields are preserved untouched, junk values
    collapse to empty containers instead of raising.
    """
    if not isinstance(theory, dict):
        return {}

    out = dict(theory)

    if "predictions" in out:
        out["predictions"] = normalize_predictions(out.get("predictions"))
    for field in ("explains", "fails_to_explain", "key_assumptions", "steps"):
        if field in out:
            out[field] = normalize_str_list(out.get(field))
    if "hidden_variables" in out:
        out["hidden_variables"] = normalize_hidden_variables(out.get("hidden_variables"))

    mechanism = out.get("mechanism")
    if isinstance(mechanism, (list, tuple)):
        out["mechanism"] = " ".join(str(m) for m in mechanism if m)
    elif mechanism is not None and not isinstance(mechanism, str):
        out["mechanism"] = str(mechanism)

    for field in ("name", "description", "type"):
        value = out.get(field)
        if value is not None and not isinstance(value, str):
            out[field] = str(value)

    if not isinstance(out.get("scores"), dict):
        out["scores"] = {}
    return out


# ── Shared prediction-quality predicates ──────────────────────────────────
# Used by discovery_scorer and empc_pipeline so the two can never disagree
# about what "grounded" means again.

def prediction_text(pred: Any) -> str:
    """The claim itself. Quantity is judged on this, never on the measurement."""
    if isinstance(pred, dict):
        return str(pred.get("statement") or pred.get("description")
                   or pred.get("prediction") or "")
    return str(pred or "")


def prediction_method_text(pred: Any) -> str:
    """Claim + how to measure it (canonical 'measurement', or the raw keys)."""
    text = prediction_text(pred)
    if isinstance(pred, dict):
        for key in _MEASUREMENT_KEYS:
            value = pred.get(key)
            if isinstance(value, str) and value.strip():
                text = f"{text} {value}"
                break
    return text


def prediction_has_quantity(pred: Any) -> bool:
    """A number appears in the statement (a direction is not a quantity)."""
    return bool(_QUANTITY_RE.search(prediction_text(pred)))


def prediction_has_method(pred: Any) -> bool:
    """The prediction names how it would be measured/observed/tested.

    The measurement may live in the statement or in the dedicated field, which
    is why this does not simply reuse prediction_text().
    """
    text = prediction_method_text(pred).lower()
    return any(word in text for word in _METHOD_WORDS)


def prediction_is_grounded(pred: Any) -> bool:
    return prediction_has_quantity(pred) and prediction_has_method(pred)
