"""
empc_pipeline.py - Evidence Mechanism Equation Prediction Pipeline
Enforces strict scientific reasoning chain at each stage.
"""
import re

from discovery.theory_schema import (
    normalize_predictions,
    prediction_has_method,
    prediction_has_quantity,
    prediction_is_grounded,
)

# ── Evidence-extraction vocabulary ────────────────────────────────────────
# Deliberately domain-agnostic. The previous extractor was tuned to
# condensed-matter physics ("filling factor", "braiding", "anyonic") and
# returned 1-5 findings from ~100 papers in every other domain.
_STOPWORDS = frozenset("""
the and for with that this from are has was were been have will would could
should into over such than them then they using which when where what does
more most only also their there these those upon within between other some
very both each your ours across among during about above after again against
because before below further here once same too under until while
""".split())

# Stemmed on purpose: "measur" matches measure/measured/measurement.
_EMPIRICAL_VERBS = (
    "observ", "measur", "found", "report", "determin", "demonstrat",
    "show that", "showed", "shown", "results indicate", "we show",
    "evidence suggest", "associated with", "correlat", "predict",
    "estimat", "reveal", "identif", "support", "indicat", "examin",
    "investigat", "assess", "compar",
)

# A number with a unit, a percentage, an error bar or a fold change.
# Multi-character units come first so "TeV" is not read as "T"; the trailing
# single-letter class covers "3 m", "5 s", "2 K" without matching "206 papers".
_UNIT_PATTERN = (
    r"(?:%|±|percent\b|fold\b|ppm\b|ppb\b|"
    r"TeV\b|GeV\b|MeV\b|keV\b|meV\b|eV\b|"
    r"THz\b|GHz\b|MHz\b|kHz\b|Hz\b|"
    r"GPa\b|MPa\b|kPa\b|Pa\b|"
    r"nm\b|µm\b|um\b|mm\b|cm\b|km\b|pm\b|"
    r"fs\b|ps\b|ns\b|µs\b|ms\b|min\b|hr\b|yr\b|"
    r"kDa\b|Da\b|mol\b|"
    r"mL\b|µL\b|dL\b|"
    r"mM\b|µM\b|nM\b|pM\b|"
    r"nb\b|pb\b|fb\b|"
    r"dB\b|°C\b|Ω\b|ohm\b|"
    r"[sKVAWJgLMNTm]\b)"
)
_NUMBER_WITH_UNIT_RE = re.compile(r"\d[\d\.,]*\s?" + _UNIT_PATTERN)

_EQUATION_RE = re.compile(r"([A-Za-z_][\w]*\s*=\s*[\d\.eE\+\-]+[\w\s/\*]*)")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[a-z]{4,}")


def _stems(text: str) -> set[str]:
    """Crude 5-character stemming: emotion/emotional/emotions all become 'emoti'.

    Exact-token matching was why a topic word in the singular never matched the
    plural or adjectival form in an abstract, which starved most papers.
    """
    return {word[:5] for word in _WORD_RE.findall(text)}

_EVIDENCE_LIMIT = 40
_PER_PAPER_LIMIT = 5

# How much a finding is worth as grounding. A measurement is the real thing; a
# topical statement ("domain") only shows the paper is on subject.
_EVIDENCE_WEIGHTS = {
    "measurement": 1.0,
    "equation": 0.9,
    "claim": 0.7,
    "comparison": 0.5,
    "domain": 0.3,
}


class EMPCPipeline:
    """Evidence -> Mechanism -> Equation -> Prediction pipeline."""

    def __init__(self, llm_call=None):
        self.llm_call = llm_call

    def run(self, topic, domain, papers, mechanisms, theories):
        """Run the full EMPC pipeline."""
        result = {"evidence": {}, "mechanisms": {}, "equations": {},
                  "predictions": {}, "grounding_scores": {}, "chain_integrity": 0.0}
        evidence = self._extract_evidence(papers, topic)
        result["evidence"] = evidence
        mech = self._ground_mechanisms(mechanisms, evidence)
        result["mechanisms"] = mech
        eqs = self._ground_equations(mechanisms, theories, mech)
        result["equations"] = eqs
        preds = self._ground_predictions(theories, eqs)
        result["predictions"] = preds
        result["grounding_scores"] = {
            "evidence_quality": evidence.get("quality_score", 0),
            "mechanism_grounding": mech.get("grounding_score", 0),
            "equation_grounding": eqs.get("grounding_score", 0),
            "prediction_grounding": preds.get("grounding_score", 0),
        }
        scores = list(result["grounding_scores"].values())
        result["chain_integrity"] = round(sum(scores) / len(scores), 3) if scores else 0
        return result

    @staticmethod
    def _paper_findings(combined, abstract, title, topic_kw, citations):
        """Classify one paper's text into typed findings (per-paper capped).

        measurement : a number AND a unit / percentage / fold change
        claim       : a number AND (a topic keyword OR an empirical verb)
        comparison  : an empirical verb AND a topic keyword
        domain      : >= 2 topic keywords

        The cap is what stops one verbose abstract from dominating the corpus.
        """
        out = []
        source = title[:60]

        equation = _EQUATION_RE.search(combined)
        if equation:
            out.append({"type": "equation", "finding": equation.group(0)[:100],
                        "source": source, "citations": citations})

        for sentence in _SENTENCE_RE.split(abstract):
            if len(out) >= _PER_PAPER_LIMIT:
                break
            text = sentence.strip()
            if len(text) < 30:
                continue
            low = text.lower()
            keywords = len(topic_kw & _stems(low))
            has_number = bool(re.search(r"\d", low))
            has_unit = bool(_NUMBER_WITH_UNIT_RE.search(low))
            has_verb = any(verb in low for verb in _EMPIRICAL_VERBS)

            if has_number and has_unit:
                finding_type = "measurement"
            elif has_number and (keywords >= 1 or has_verb):
                finding_type = "claim"
            elif has_verb and keywords >= 1:
                finding_type = "comparison"
            elif keywords >= 2:
                finding_type = "domain"
            else:
                continue

            out.append({"type": finding_type, "finding": text[:200],
                        "source": source, "citations": citations})
        return out

    def _extract_evidence(self, papers, topic):
        """Stage 1: extract typed findings from the literature.

        Papers are ranked by topical overlap, then findings are taken
        round-robin so breadth of coverage, not document order, decides what
        gets in. Quality is coverage-weighted, so 40 findings from one paper
        still scores low.
        """
        papers = [p for p in (papers or []) if isinstance(p, dict)]
        topic_kw = {w[:5] for w in _WORD_RE.findall((topic or "").lower())
                    if w not in _STOPWORDS}

        ranked = []
        relevant = 0
        for p in papers:
            title = str(p.get("title") or "")
            abstract = str(p.get("abstract") or "")
            combined = f"{title} {abstract}".lower()
            overlap = len(topic_kw & _stems(combined))
            if overlap >= 2:
                relevant += 1
            citations = p.get("citation_count", 0) or 0
            local = self._paper_findings(combined, abstract, title, topic_kw, citations)
            if local:
                ranked.append((overlap, citations, local))

        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)

        findings, seen = [], set()
        depth = 0
        while len(findings) < _EVIDENCE_LIMIT and any(
                depth < len(local) for _, _, local in ranked):
            for _, _, local in ranked:
                if depth >= len(local):
                    continue
                candidate = local[depth]
                key = candidate["finding"][:80].lower()
                if key in seen:
                    continue
                seen.add(key)
                findings.append(candidate)
                if len(findings) >= _EVIDENCE_LIMIT:
                    break
            depth += 1

        distinct_sources = len({f["source"] for f in findings})
        coverage = min(1.0, distinct_sources / max(1, min(relevant, 25)))
        rigor = (sum(_EVIDENCE_WEIGHTS.get(f["type"], 0.3) for f in findings)
                 / len(findings)) if findings else 0.0
        quality = min(1.0, 0.5 * coverage + 0.5 * rigor)

        return {
            "findings": findings,
            "total_papers": len(papers),
            "relevant_papers": relevant,
            "quality_score": round(quality, 3),
            "by_type": {
                "measurements": sum(1 for f in findings if f["type"] == "measurement"),
                "claims": sum(1 for f in findings if f["type"] == "claim"),
                "equations": sum(1 for f in findings if f["type"] == "equation"),
                "comparisons": sum(1 for f in findings if f["type"] == "comparison"),
                "domain": sum(1 for f in findings if f["type"] == "domain"),
            },
        }

    def _ground_mechanisms(self, mechanisms, evidence):
        grounded = []
        ungrounded = []
        ev_text = " ".join(f.get("finding","") for f in evidence.get("findings",[])).lower()
        ev_words = set(w for w in ev_text.split() if len(w) > 4)
        for m in (mechanisms or []):
            if not isinstance(m, dict): continue
            desc = str(m.get("description") or m.get("mechanism") or "").lower()
            # Also include derivation, steps, and mathematical_model in the check
            derivation = m.get("derivation", "")
            if isinstance(derivation, list):
                derivation = " ".join(str(d) for d in derivation)
            steps_text = " ".join(str(s) for s in (m.get("steps") or []))
            math_model = m.get("mathematical_model", "")
            full_text = desc + " " + str(derivation) + " " + steps_text + " " + str(math_model)
            mech_words = set(w for w in full_text.lower().split() if len(w) > 4)
            overlap = len(ev_words & mech_words)
            # Grounding criteria: word overlap OR has structured derivation OR has math model
            has_derivation = any(kw in full_text.lower() for kw in [
                "therefore", "thus", "it follows", "substituting", "solving",
                "deriving", "from this", "we obtain", "we get", "yielding",
                "step 1", "step 2", "step 3", "starting from", "governing equation",
            ])
            has_math = bool(math_model) and len(str(math_model)) > 10
            is_grounded = overlap >= 2 or len(desc) > 200 or (has_derivation and has_math)
            entry = {"name": m.get("name","?"), "evidence_refs": overlap,
                     "has_derivation": has_derivation, "has_math": has_math,
                     "is_grounded": is_grounded}
            (grounded if is_grounded else ungrounded).append(entry)
        score = len(grounded) / max(1, len(grounded) + len(ungrounded))
        return {"grounded_mechanisms": grounded, "ungrounded_mechanisms": ungrounded, "grounding_score": round(score, 3)}

    def _ground_equations(self, mechanisms, theories, mech_grounding):
        equations = []
        for source in [(mechanisms or []), (theories or [])]:
            for item in source:
                if not isinstance(item, dict): continue
                desc = str(item.get("description") or "") + " " + str(item.get("mathematical_model") or "")
                # Also read derivation field (LLM stores derivations here)
                derivation = item.get("derivation", "")
                if isinstance(derivation, str):
                    desc += " " + derivation
                elif isinstance(derivation, list):
                    for d in derivation:
                        if isinstance(d, dict):
                            desc += " " + str(d.get("step", "")) + " " + " ".join(str(c) for c in d.get("content", []))
                        else:
                            desc += " " + str(d)
                for match in re.finditer(r"([A-Za-z_][\w]*)\s*=\s*([^,.;\n]{5,80})", desc):
                    var, expr = match.group(1), match.group(2).strip()
                    has_nums = any(c.isdigit() for c in expr)
                    equations.append({"variable": var, "expression": expr[:60], "has_numbers": has_nums, "is_grounded": has_nums})
        grounded = [e for e in equations if e.get("is_grounded")]
        score = len(grounded) / max(1, len(equations)) if equations else 0
        return {"equations": equations[:20], "grounded_equations": grounded, "grounding_score": round(score, 3)}

    def _ground_predictions(self, theories, eq_grounding):
        predictions = []
        for t in (theories or []):
            if not isinstance(t, dict):
                continue
            # Canonical shape first: a str would otherwise be iterated
            # character-by-character and a dict would yield its keys.
            for p in normalize_predictions(t.get("predictions")):
                pred = p.get("statement", "")
                if not pred:
                    continue
                has_nums = prediction_has_quantity(p)
                has_method = prediction_has_method(p)
                predictions.append({
                    "prediction": pred[:200],
                    "has_numbers": has_nums,
                    "has_test_method": has_method,
                    "is_grounded": prediction_is_grounded(p),
                })
        grounded = [p for p in predictions if p.get("is_grounded")]
        score = len(grounded) / max(1, len(predictions)) if predictions else 0
        return {"predictions": predictions, "grounded_predictions": grounded, "grounding_score": round(score, 3)}
