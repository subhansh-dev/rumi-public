"""
Tests for the EMPC evidence extractor (no network required).

The failure being covered is a real one: reports with ~100 papers and ~80
abstracts were producing 1-5 findings, because the old extractor required two
topic keywords per sentence, only recognised a physics unit list, and had a
hardcoded condensed-matter pattern block.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from discovery.empc_pipeline import EMPCPipeline  # noqa: E402

TOPIC = "affective architecture and emotional state regulation"


def _pipeline():
    return EMPCPipeline()


def _paper(title, abstract, citations=0):
    return {"title": title, "abstract": abstract, "citation_count": citations}


def _extract(papers, topic=TOPIC):
    return _pipeline()._extract_evidence(papers, topic)


def _types(result):
    return [f["type"] for f in result["findings"]]


# ── classification ────────────────────────────────────────────────────────
def test_number_with_unit_is_a_measurement():
    out = _extract([_paper(
        "Signal study",
        "The measured response amplitude was 2.4 nb at the detector and remained stable.",
    )])
    assert "measurement" in _types(out)


def test_percentage_and_fold_change_count_as_measurements():
    out = _extract([
        _paper("A", "Accuracy improved by 18 % across all emotional conditions in the sample."),
        _paper("B", "The response was 2.3 fold higher for emotional stimuli than for neutral ones."),
    ])
    assert _types(out).count("measurement") == 2


def test_number_with_topic_keyword_is_a_claim():
    out = _extract([_paper(
        "State count",
        "The system produced 12 distinct emotional states during the trial session.",
    )])
    assert "claim" in _types(out)


def test_p_value_sentence_is_kept_as_a_claim():
    out = _extract([_paper(
        "Significance",
        "The difference was significant at p < 0.05 in the emotional condition overall.",
    )])
    assert out["findings"], "a p-value sentence must not be discarded"
    assert "claim" in _types(out)


def test_qualitative_empirical_sentence_is_a_comparison():
    out = _extract([_paper(
        "Qualitative",
        "We examined how emotional regulation changed under cognitive load in participants.",
    )])
    assert "comparison" in _types(out)


def test_irrelevant_sentence_is_dropped():
    out = _extract([_paper(
        "Irrelevant",
        "Acknowledgements and funding details are listed at the end of this document.",
    )])
    assert out["findings"] == []


def test_equation_is_extracted_once_per_paper():
    out = _extract([_paper(
        "Model",
        "We fit lambda = 0.75 under load. The same lambda = 0.75 held at rest as well.",
    )])
    assert _types(out).count("equation") == 1


# ── corpus assembly ───────────────────────────────────────────────────────
def test_one_verbose_paper_cannot_fill_the_corpus():
    verbose = " ".join(
        f"Condition {i} measured 5 % change in the emotional response."
        for i in range(20)
    )
    out = _extract([_paper("Verbose", verbose)])
    assert len(out["findings"]) <= 5


def test_round_robin_covers_multiple_sources():
    verbose = " ".join(
        f"Condition {i} measured 5 % change in the emotional response."
        for i in range(20)
    )
    papers = [_paper("Verbose", verbose)]
    papers += [_paper(f"Small {i}",
                      f"We measured {i + 1} % change in the emotional response.")
               for i in range(5)]
    out = _extract(papers)
    sources = {f["source"] for f in out["findings"]}
    assert len(sources) >= 6, sources


def test_global_cap_is_forty():
    papers = [
        _paper(f"Paper {i}", " ".join(
            f"Trial {j} at site {i} measured {j + 1} % change in the emotional response."
            for j in range(10)
        ))
        for i in range(60)
    ]
    out = _extract(papers)
    assert len(out["findings"]) == 40


def test_empty_corpus_does_not_crash():
    out = _extract([])
    assert out["findings"] == []
    assert out["quality_score"] == 0
    assert out["total_papers"] == 0


def test_papers_without_abstracts_are_counted_but_produce_nothing():
    out = _extract([_paper("Title only", ""), _paper("Also empty", "   ")])
    assert out["findings"] == []
    assert out["total_papers"] == 2


def test_malformed_papers_are_skipped():
    out = _extract([None, "not a dict", {"title": None, "abstract": None}])
    # Only the dict survives; the string and None are dropped outright.
    assert out["total_papers"] == 1
    assert out["findings"] == []


# ── quality is coverage-weighted, not a raw count ─────────────────────────
def test_spread_coverage_scores_higher_than_one_verbose_paper():
    # Relevant papers that yield no finding: these set the coverage denominator.
    barren = [_paper(f"Affective architecture note {i}",
                     "Acknowledgements and funding details are listed at the end of this document.")
              for i in range(15)]

    spread = [_paper(f"Affective architecture S{i}",
                     f"We measured {i + 1} % change in the emotional response.")
              for i in range(10)]
    concentrated = [_paper(f"Affective architecture C{i}", " ".join(
        f"Trial {j} at site {i} measured {j + 1} % change in the emotional response."
        for j in range(5)
    )) for i in range(2)]

    spread_out = _extract(spread + barren)
    concentrated_out = _extract(concentrated + barren)

    assert len(spread_out["findings"]) == len(concentrated_out["findings"]) == 10
    assert spread_out["relevant_papers"] >= 25
    assert spread_out["quality_score"] > concentrated_out["quality_score"]


def test_measurement_evidence_outscores_domain_evidence():
    def corpus(sentence):
        return [_paper(f"Affective architecture P{i}", sentence.format(i=i + 1))
                for i in range(10)]

    measurements = _extract(corpus("We measured {i} % change in the emotional response."))
    domains = _extract(corpus(
        "The affective architecture framework connects emotional state regulation."))

    assert measurements["by_type"]["measurements"] == 10
    assert domains["by_type"]["measurements"] == 0
    assert measurements["quality_score"] > domains["quality_score"]


# ── the actual production failure ────────────────────────────────────────
def test_realistic_social_science_abstract_yields_evidence():
    """This abstract shape produced zero findings under the old extractor."""
    out = _extract([_paper(
        "Can machines handle emotions?",
        "In the reported analysis, we investigate how different automated "
        "translation methods render emotional content in English. Using emotion "
        "and sentiment analysis, 206 English translations of reviews were "
        "examined for the frequency of words related to basic emotions and "
        "respective sentiment scores. Correspondence analysis revealed clear "
        "distinctions between the translation systems.",
    )], topic="emotions and sentiment")
    assert len(out["findings"]) >= 2, out["findings"]
    assert out["quality_score"] > 0


def test_by_type_counts_match_findings():
    out = _extract([_paper(
        "Mixed",
        "The measured response was 2.4 nb at the detector. "
        "The system produced 12 distinct emotional states during the trial. "
        "We examined how emotional regulation changed under load.",
    )])
    counts = out["by_type"]
    assert sum(counts.values()) == len(out["findings"])


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
