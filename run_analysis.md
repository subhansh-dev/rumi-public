# RUMI Run Analysis â€” The Numbers Behind the Article

Compiled from `Engine/eval/leaderboard.json` (51 graded runs), `Dataset/discovery_archive.json`
(48 runs backfilled with external scores), and the raw run JSON/txt reports. All numbers below
are reproducible from this folder. Last updated: 2026-11-04.

---

## 1. Headline statistics (n = 51 externally graded runs)

| Metric | Value |
|---|---|
| Average external score | **52.0 / 100** |
| Average internal (self) score | 58.9 / 100 (min 0, max 83.8) |
| Average gap (internal âˆ’ external) | **+1.1** |
| Runs where self-score was LOWER than external | **26 / 51** |
| Runs where self-score overshot external by 10+ | 16 / 51 |
| Biggest self-inflation | **+38.0** (internal 70.7 vs external 32.7) |
| Flags: `no_citations` | **51 / 51 runs** |
| Flags: `ungrounded_claims` | **35 / 51 runs** |

### External grade distribution â€” the headline

| Grade | Count |
|---|---|
| A | **0** |
| B | **0** |
| C | 45 |
| D | 0 |
| F | 6 |

> Across 51 runs, RUMI never earned a grade better than C **against its own frozen,
> external evaluation harness**. Every "A" it ever gave itself was self-reported.

### The three mis-calibration regimes (article framing)
1. **Inflation regime:** e.g. run 22: internal 83.8 â†’ external 58.5 (+25.3)
2. **Under-reporting regime:** 26 runs score *themselves lower* than the frozen judge
3. **Collapse regime:** run `1782654718`: external **2.9/100 (F)** with flags
   `no_claims`, `incomplete_structure`, `internal_score: null` â€” a run that
   fell apart so early the self-scorer had nothing to grade

---

## 2. Worst self-score cases (candidates for the article table)

| Run | Internal | External | Gap |
|---|---|---|---|
| 45 | 70.7 | 32.7 | **+38.0** |
| 22 | 83.8 | 58.5 | +25.3 |
| 1  | 82.8 | 60.6 | +22.2 |
| 14 | 80.1 | 59.7 | +20.4 |
| 31 | 75.2 | 55.3 | +19.9 |
| 3  | 79.1 | 60.5 | +18.6 |

## 3. Per-domain run counts

| Domain | Runs |
|---|---|
| drug_discovery | 21 |
| space_astronomy | 7 |
| neuroscience | 7 |
| general | 6 |
| physics | 6 |
| materials_science | 2 |
| mathematics | 1 |
| computer_science | 1 |

## 4. Runtime distribution (from .txt report headers)

Runs ranged from **0.2 h to 21.2 h** wall-clock per discovery â€” examples:
`1781790378` 10.8h, `1781789821` 21.2h (21 hours of autonomous "discovery"),
`1780871296` 0.2h (the quick/collapsed end).

---

## 5. The Gold List â€” concrete artifacts worth quoting

### G1. Iteration is a coin flip on whether it helps
- `1781548521` (proteasome/molecular glue): pass1 **65 â†’ pass2 80.1** âœ” improved
- `1781551204` (molecular glue neo-substrates): pass1 **83.8 â†’ pass2 65.2** âœ˜ REGRESSED

The self-refinement loop improved scores about half the time it was tried.

### G2. Textbook science won tournaments that were supposed to produce novelty
Winner names in the theory tournaments include **"Î›CDM Cold Dark Matter Halo"** and
**"Standard Î›CDM with Peculiar Velocity Corrections"** â€” i.e. the standard cosmological
model itself. At least 6 runs carried a `NULL HYPOTHESIS CHECK: WARNING`, forcing a
score cap at 64.

### G3. Schema leakage in winner names
One theory "won" a tournament with the literal variable name
**`percolation_threshold_pc`** â€” raw code identifiers leaking into narrative output.

### G4. Evidence dimension = 0 everywhere
In **all 67 scored runs** the minimum `evidence_strength` sub-score found was **0** â€”
the pipeline fetched up to 100+ real papers and then scored zero weight to them.
Combined with `no_citations` in 51/51 validated runs: **RUMI retrieves papers,
then ignores them.**

### G5. Winner-name comedy (self-assessment in action)
One drug_discovery run's tournament winner:
**"Positive Feedback Loop in Research Focus"** â€” the AI named an abstract
meta-process as the winning theory for why Alzheimer's trials fail.

### G6. Real computation artifacts exist (it isn't all theater)
- Papers actually retrieved: 105 & 100 in two inspected runs (`1781146480`, `1781216474`)
- Reflexion self-modification patches actually applied: ~8 runs show `patches_applied=1`
  gated by the frozen regression harness (`eval/tests/`)

### G7. The tamper-evidence artifact for the article
`Engine/eval/ledger.jsonl` â€” every external evaluation appends a hash-chained row
(SHA-256 of previous row + data) so scores cannot be rewritten after the fact.

---

## 6. Honest-corrections log (things we initially got wrong)
1. "Internal inflates by 14â€“22 points" â€” TRUE for the top leaderboard rows only.
   Across all 51 runs the average gap is +1.1, with 26 runs under-reporting.
   The correct claim: **self-scoring is unreliable in both directions**, with
   multi-tens-of-points excursions up (+38) â€” not a uniform +20 bias.
2. "Score of record ships inside every report JSON" â€” design intent, but the 48
   pre-harness runs have external scores backfilled into the archive instead.
3. The first quick-look audit (which found "everything is theater") applied to
   `rumi-demo/`, not the real engine. The real engine does retrieve, enrich, and
   mechanically verify â€” the failure mode is disconnect between retrieval and reasoning.

---

## 7. Where G5/G1 point (the research paper's actual contribution)
- Phenomenon: **retrievalâ€“reasoning dissociation** â€” a grounded-looking agent where
  real retrieval exists structurally upstream, but downstream reasoning cites none of it.
- Fix under test: claim â†’ citation binding at generation time, validated by the frozen harness.
- Until fixed, every "80/100 (A)" generated by any self-scoring pipeline should be
  treated the way we treat a defendant's own courtroom testimony lol.

For hand-verification next: sample ~10 claims from 3 runs, try to find them in the
fetched paper abstracts, and log supported/unsupported/contradicted â€” that sample
becomes the article's claim-support table.

## 8. Control test -- validating the harness

To check that the harness can distinguish good from bad (and that no_citations is a
real finding rather than a detector blind spot), a RUMI-shaped control report was
constructed with 5 papers, proper [1]-[5] citations resolving to those papers,
claim sentences carrying citations, a named winner, mechanism steps, and predictions.
It was run through the same frozen harness.

| Metric | Control (well-cited) | RUMI (avg, n=51) |
|---|---|---|
| citation_validity | 1.0 | 0 (no citations) |
| claim_support_rate | 1.0 | null (no claims detected) |
| novelty_vs_archive | 1.0 | ~0.0-0.5 |
| structure_completeness | 0.429 | ~0.14 |
| External score | 68.6 (B) | 52.0 (C) |
| Grade | B | C |

The control scored a B -- the first B grade the harness has ever produced. RUMI runs
score C. The harness correctly distinguishes a well-cited, well-structured report
from RUMI's output. The no_citations finding is confirmed real, not a detector artifact.

One harness limitation noted: score_consistency never fires on real RUMI data because
the report format stores dimension scores as top-level keys rather than under the
scores/weights_used sub-dicts the metric expects. This does not affect the main
findings but means the inflation audit is effectively disabled in practice.

For hand-verification next: sample ~10 claims from 3 runs, try to find them in the
fetched paper abstracts, and log supported/unsupported/contradicted -- that sample
becomes the article's claim-support table.