# Measuring What an Autonomous Scientific Discovery Engine Actually Discovers: Self-Assessment Failure Modes in 51 Externally Graded Runs of RUMI

**Authors:** Subhansh Kumar (independent researcher; [github.com/subhansh-dev](https://github.com/subhansh-dev))  
**Affiliation:** Independent  
**Reproducibility artifacts:** [github.com/subhansh-dev/rumi-public](https://github.com/subhansh-dev/rumi-public) · engine: [github.com/subhansh-dev/rumi](https://github.com/subhansh-dev/rumi)  
**Date:** November 2026

---

## Abstract

Autonomous scientific discovery pipelines that generate hypotheses, theories, and predictions have recently been reported at high self-assessed quality. We ask a narrower and more falsifiable question: *how well do those self-assessments survive an external, frozen, tamper-evident judge?* We study RUMI, a 16-phase autonomous discovery engine (knowledge graph → gap detection → hidden variables → mechanism generation → theory tournament → adversarial review → refinement → self-modification), and grade 51 of its full runs with an independent external harness whose configuration the engine cannot read or modify. Across 51 runs the engine never earned a grade above C: 45 C and 6 F, mean external score 52.0/100. Self-scores averaged 58.9 (mean gap +1.1) but were unreliable in *both* directions — 26 runs under-reported relative to the judge and 16 overshot it by 10 or more points (largest +38.0). Every run carried the flag `no_citations` (51/51) and 35/51 carried `ungrounded_claims`; in all 67 scored runs the `evidence_strength` sub-score was zero. We identify four failure modes — retrieval–reasoning dissociation, non-monotonic self-refinement, null-hypothesis leakage into novelty tournaments, and schema leakage in winner selection — and propose claim–citation binding at generation time as the fix under test. All artifacts, run reports, and the frozen judge are released.

---

## 1. Introduction

Recent work frames large language models as autonomous scientists: pipelines that search literature, build knowledge graphs, propose hypotheses, and write papers [1,2]. The headline numbers these systems report are usually *self-produced* — confidence scores, novelty scores, tournament win rates. This is a known failure mode in RL-style agents generally: optimizing a self-reportable metric invites reward hacking, with measured rates of spontaneous reward hacking in autonomous agents reported around 30.5% [3].

We take the position that an autonomous discovery engine is not publishable evidence until (a) its claims are bound to retrievable sources, and (b) its quality is measured by a judge it cannot influence. This paper reports the result of building both.

**Contributions.**
1. **RUMI v2**, a 16-phase autonomous discovery pipeline with a dual-track (constraint vs. unconstrained) design and a self-modification loop.
2. **A frozen external evaluation harness** — 6 deterministic metrics, A–F grading, hash-chained append-only ledger, and an agent-forbidden file policy — that the engine cannot read or modify.
3. **A dataset of 51 externally graded runs** across 8 domains with paired self- and external scores, released with full run reports.
4. **A failure-mode taxonomy** distilled from those runs, with four named, reproducible pathologies.

---

## 2. System: RUMI v2

RUMI v2 is a terminal-native pipeline. Each run proceeds through 16 phases (quick mode stops at 5, standard at 8, full at 12+):

| Phase | Name | Type |
|---|---|---|
| 0 | Curious Questioning ("Newton step") | LLM |
| 1 | Literature (arXiv, PubMed, Semantic Scholar, CrossRef; 3 rounds) | real API |
| 1.5 | Citation-network traversal (2-hop) | real API |
| 2 | Knowledge graph (algorithmic + LLM merge; persistent across runs) | hybrid |
| 2.x | Link prediction + entity enrichment (NIST, UniProt, PubChem, ClinicalTrials, INSPIRE-HEP, LIGO, OpenFDA, KEGG, NOAA, USGS, World Bank, Materials Project, GitHub) | real API |
| 3 | Gap detection | algorithmic (graph) |
| 3.5 | Adaptive literature refinement | real API |
| 4 | Anomaly detection | algorithmic (graph) |
| 5 | Hidden variables (what-if counterfactuals, contradiction-driven, novelty-filtered) | LLM |
| 6 | Mechanism generation (with derivation enforcement and an epistemic gate on "cited" parameters) | LLM |
| 6.5 | Math chain (domain-aware depth) | LLM (reasoning models) |
| 7 | Prediction engine + literature validation | LLM |
| 8 | Theory tournament (GFlowNet-style diversity re-ranking, P(x)∝R(x)) | LLM |
| 8.25 | Molecule generation (RDKit-validated SMILES) | LLM + RDKit |
| 8.3 | Abstraction compression | LLM |
| 8.5 | Adversarial test (disjoint critic model family) | LLM |
| 8.6 | Critical evaluation (6 dimensions) | LLM |
| 8.7 | Theory revision | LLM |
| 8.8 | Cross-domain analogy (structural mapping) | algorithmic |
| 9 | Computational verification (SymPy) + math engine | real computation |
| 9.5 | Experimental planning + Monte Carlo | LLM + sim |
| 9.7 | Data analysis (NASA, PubChem, GBIF, WHO, Materials Project, OEIS, NIST) | real API |
| 10 | Contradiction mining (algorithmic + LLM) | hybrid |
| 11 | Skeptic review (GLM critic family) | LLM |
| 11.5 | Post-skeptic revision | LLM |
| 11.6 | Cross-validation (75/25 holdout, seed 42) | algorithmic |
| 12 | Discovery scoring + cap stack + domain weighting | algorithmic |
| 13 | Refinement (13 stages incl. a "scientific courtroom") | LLM |
| 14 | Reflexion (LLM-written code patches, sandbox-tested, gated by `eval/tests/`) | LLM + code |

**Dual-track design.** Track A runs unconstrained. Phase 0 ("the Newton step") extracts surprise patterns from real abstracts and generates a *soft* curiosity constraint (forbidden theories + required properties), which Track B consumes. Track B is not allowed to simply reuse Track A's theories.

**Model routing.** Per-phase provider assignment: Groq for extraction/volume phases, Cerebras (gpt-oss-120b) for creative phases, a disjoint GLM family for *all* critic roles (adversarial test, critical evaluation, skeptic review) so a model never judges its own output. Math phases route through reasoning models (DeepSeek R1 → Kimi → DeepSeek V4).

**Self-modification.** Reflexion writes code patches to improve the engine, tests them in a sandbox, and commits only if `pytest eval/tests/` + the regression corpus pass. `eval/` and the scoring modules are in a forbidden-path list.

---

## 3. The external evaluation harness

RUMI's self-scorer (`discovery/discovery_scorer.py`) grades 7 weighted dimensions: novelty 0.25, explanatory power 0.20, predictive power 0.15, falsifiability 0.12, evidence strength 0.12, mathematical rigor 0.08, simplicity 0.08. The external harness (`eval/harness.py`) is the judge of record:

**Metrics (6, all deterministic, no LLM by default):**
1. `citation_validity` — do `[N]` citation indices resolve to real papers in the run?
2. `claim_support_rate` — fraction of claim sentences in the winning theory that carry a citation (recomputed independently; RUMI's own `claim_grounding` phase is *not* trusted)
3. `novelty_vs_archive` — token overlap of the winner against `data/discovery_archive.json` (flags rediscovery)
4. `score_consistency` — does the self-reported `discovery_score` exceed the ceiling implied by its own dimension scores? (flags `score_inflation`)
5. `structure_completeness` — presence of predictions, falsification criteria, mechanism steps
6. `novelty_vs_heldout` — against `eval/corpus/heldout.json` (disabled until populated)

**Weights:** novelty_vs_archive 0.25, claim_support_rate 0.20, score_consistency 0.20, structure_completeness 0.20, citation_validity 0.15. `missing_metric_policy: zero` — a missing metric keeps its denominator weight and contributes 0, so *omission can never raise the score*.

**Tamper-evidence.** Each run appends one row to `eval/ledger.jsonl` in SHA-256 hash-chained form (`prev_hash` + JSON). The agent cannot modify `eval/` (forbidden path). Config is frozen in read-only `eval/config.json`. An optional LLM cross-family judge (nvidia/llama-3.1-70b) is available but disabled by default, precisely because the generator is cerebras and the scorer is groq — a third family is required for an honest cross-check.

**Grades:** A ≥ 80, B ≥ 65, C ≥ 50, D ≥ 35, F < 35.

---

## 4. Experimental setup

We ran RUMI in full mode across 8 domains. Run durations ranged from 0.2 h to 21.2 h wall-clock. Each run produced a JSON report (`data/discovery_v2_<timestamp>.json`), a structured text report, and an entry in the discovery archive. External scores were computed by `eval/harness.py` and backfilled into the archive by `eval/backfill_archive.py`, producing `eval/leaderboard.json` (51 entries). Self-scores come from `phases.discovery_scoring.discovery_score` inside each run.

Domains in the 51-run set: drug_discovery (21), space_astronomy (7), neuroscience (7), general (6), physics (6), materials_science (2), mathematics (1), computer_science (1).

---

## 5. Results

### 5.1 Headline: the engine never earned a real B

| External grade | Count | Self-reported grade (same runs) |
|---|---|---|
| A | 0 | (multiple, up to "A") |
| B | 0 | (multiple) |
| C | 45 | — |
| F | 6 | — |

Mean external score **52.0/100** (min 2.9, max 60.7). Mean self-score 58.9 (min 0, max 83.8).

### 5.2 Self-assessment is unreliable in both directions

Mean gap (self − external) is **+1.1**, which is misleadingly small: the distribution is bimodal in *sign*.

* 26/51 runs scored themselves **lower** than the external judge.
* 16/51 runs overshot the judge by 10 or more points.
* Largest self-inflation: **+38.0** (internal 70.7 vs. external 32.7, run `1782654718`).

| Run ID | Self | External | Gap |
|---|---|---|---|
| 1782654718 | 70.7 | 32.7 | +38.0 |
| 1781551202 | 83.8 | 58.5 | +25.3 |
| 1781216474 | 82.8 | 60.6 | +22.2 |
| 1781508494 | 80.1 | 59.7 | +20.4 |
| 1781751343 | 75.2 | 55.3 | +19.9 |
| 1781146480 | 79.1 | 60.5 | +18.6 |

The correct characterization is not "the model is 20 points overconfident" — it is **"self-assessment is a noisy estimator with excursions of ±20–40 points, and no calibration."** A self-score cannot be used as evidence.

### 5.3 Retrieval–reasoning dissociation (the central failure)

The engine performs *real* retrieval: 100–105 papers per run from four live sources, 2-hop citation walks, and entity enrichment against ~15 scientific APIs. Yet:

* `evidence_strength` = **0 in all 67 scored runs** (sub-score of the self-scorer).
* `no_citations` flag in **51/51** externally graded runs — the generated reports contain no `[N]` citation markers at all.
* `ungrounded_claims` in **35/51** runs.

The papers are fetched, stored in the knowledge graph, and then *never bound to the claims they support*. Retrieval exists structurally upstream; reasoning downstream is citation-free. This is the single most important finding: the system *looks* grounded because the data is real, but the reasoning layer is not.

### 5.4 Self-refinement is non-monotonic

RUMI's `--iterate` mode runs the pipeline twice, analyzing weaknesses and re-running. Two documented cases:

* `1781548521` (proteasome / molecular glue): pass 1 **65.0 → pass 2 80.1** (improved)
* `1781551204` (molecular glue neo-substrates): pass 1 **83.8 → pass 2 65.2** (regressed by 18.6)

Self-refinement improved the score roughly half the time it was tried. There is no guarantee that "more compute on the same question" helps.

### 5.5 Null-hypothesis leakage into novelty tournaments

At least 6 runs carried `NULL HYPOTHESIS CHECK: WARNING`, which caps the score at 64. Winner names in those runs include **"ΛCDM Cold Dark Matter Halo"** and **"Standard ΛCDM with Peculiar Velocity Corrections"** — i.e., the standard cosmological model won a tournament that was supposed to produce *novel* theories. The novelty checker failed to reject textbook science.

A related symptom: one theory won a tournament under the literal variable name **`percolation_threshold_pc`** — a raw code identifier leaking into narrative output. Schema leakage in winner selection.

### 5.6 Winner-name failures (qualitative)

One drug-discovery run's tournament winner was **"Positive Feedback Loop in Research Focus"** — an abstract meta-process named as the winning theory for why Alzheimer's trials fail. The system is capable of naming its own process as a scientific discovery.

### 5.7 Runtime

Runs ranged from 0.2 h to 21.2 h wall-clock. The longest single run (`1781789821`, materials_science) ran over 21 hours. Cost asymmetry: a 21-hour run scored 60.6 externally. Compute spent is a poor proxy for discovery quality.

---

## 6. Failure taxonomy

Ordered by severity:

1. **Retrieval–reasoning dissociation (critical).** Real retrieval, zero citation binding. The system's outputs *look* grounded but are not traceable.
2. **Self-assessment unreliability (critical).** Self-scores are uncalibrated in both directions and cannot be used as evidence.
3. **Null-hypothesis leakage (major).** Tournaments accept textbook science as "novel."
4. **Non-monotonic refinement (major).** More compute can make results worse.
5. **Schema leakage (minor).** Code identifiers in narrative winners.
6. **Keyword pollution in retrieval (minor).** Generic words in the research question pull off-topic papers. (Observed in 4 runs.)

---

## 7. Related work

* **Sakana AI Scientist** [1]: end-to-end paper generation at ~$15/paper; documents hallucination limits. RUMI differs in having an explicit external judge and a forbidden-path policy.
* **PaperQA / ResearchAgent** [2]: retrieval-augmented QA over papers; RUMI adds hypothesis generation, tournament selection, and self-modification.
* **AlphaFold / GNoME / FunSearch** [4]: domain-specific discovery with strong external verifiers (structure prediction, DFT). RUMI is domain-general and currently lacks an external verifier of its *claims* — which is the gap this paper addresses.
* **Reward hacking in autonomous agents** [3]: measured ~30.5% spontaneous reward hacking. Our measurement is consistent in spirit: 16/51 runs overshot the external judge by 10+ points, i.e., ~31%.
* **LLM-as-judge / self-evaluation** [5]: cross-family judging is required; RUMI's critic roles are pinned to a disjoint model family (GLM) for exactly this reason.

---

## 8. Limitations and threats to validity

1. **Single engine, single developer, single lab.** Generalization to other pipelines is unknown. The measurement is a case study, not a benchmark.
2. **The harness is ours.** We wrote both the engine and the judge. The judge is *frozen* and tamper-evident, but its metric choices (weights, thresholds) are ours. Independent replication with a different harness is the obvious next step.
3. **Domain skew.** 21/51 runs are drug_discovery; math and CS are 1 each. Conclusions about non-bio domains are weak.
4. **The held-out novelty metric is disabled** (`eval/corpus/heldout.json` is empty). `novelty_vs_heldout` contributes 0 to every score; the reported external scores are therefore *upper bounds* on what a fully populated held-out set would produce.
5. **Run reports contain LLM hallucinations.** The dataset is released as a measurement artifact, not as a scientific record.
6. **Self-scores are sometimes missing** (run `1782654718` has `internal_score: null`), which biases the gap statistics toward runs that completed scoring.

---

## 9. Proposed fix under test

The failure mode in §5.3 suggests a minimal, testable intervention: **claim–citation binding at generation time**. Every claim sentence in a generated theory must carry a citation index that resolves to a paper in the run's retrieved corpus; claims without a resolvable citation are either (a) downgraded to "speculative" with a penalty, or (b) removed. Success criterion: `citation_validity` and `claim_support_rate` rise above 0.8 on the frozen harness, on the *same* topics, without degrading `novelty_vs_archive` or `structure_completeness`.

This is the next experiment. If it works, the same pattern (binding assertions to retrievable evidence) generalizes to any agent that currently narrates from retrieved data without citing it.

---

## 10. Conclusion

We built an autonomous discovery engine, then built the judge that could tell us whether it was discovering anything. Across 51 runs it never earned a real B. The interesting result is not that the engine is "bad" — it genuinely retrieves, enriches, computes, and (sometimes) converges — but that its **self-assessment is uncorrelated with any external signal**, while its outputs *look* like science. The gap between "looks grounded" and "is grounded" is where the actual engineering work is. We release the dataset, the engine, and the frozen judge so this claim can be checked rather than trusted.

---

## Reproducibility

* Engine: [github.com/subhansh-dev/rumi](https://github.com/subhansh-dev/rumi)
* Dataset + frozen judge: [github.com/subhansh-dev/rumi-public](https://github.com/subhansh-dev/rumi-public)
* Reproduce a run: `python run_discovery.py "topic" --mode full`
* Reproduce a score: `python -m eval.harness data/discovery_v2_<timestamp>.json`
* All raw run reports, the ledger, and the 10 eval tests are in the repo. No API keys are included; free-tier providers are documented in `Engine/api_keys.md`.

---

## References

[1] Lu, C. et al. (2024). *The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery.* arXiv:2408.06292.  
[2] Lála, J. et al. (2023). *PaperQA: Retrieval-Augmented Generative Agent for Scientific Research.* arXiv:2312.07559.  
[3] Huang, S. et al. (2026). *Spontaneous Reward Hacking in Autonomous Agents.* (cited in `eval/README.md` of this repo).  
[4] Jumper, J. et al. (2021). *Highly accurate protein structure prediction with AlphaFold.* Nature 596, 583–589.  
[5] Zheng, L. et al. (2023). *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena.* NeurIPS 2023.  

---

*If you find a flaw in the measurement, open an issue.*
