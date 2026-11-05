# RumI dataset — 51 graded runs of an autonomous discovery engine, scored against its own external judge

[![LinkedIn](https://img.shields.io/badge/follow-%40subhansh--kumar67-0A66C2?logo=linkedin)](https://linkedin.com/in/subhansh-kumar67)
[![The engine](https://img.shields.io/badge/engine-RUMI%20v2%20(discovery%20pipeline)-crimson?logo=github)](https://github.com/subhansh-dev/rumi)
[![Graded runs](https://img.shields.io/badge/discovery_runs-51-blue)](run_analysis.md)
[![External grades](https://img.shields.io/badge/external_grades-0%20A%20%3A%200%20B%20%3A%2045%20C%20%3A%206%20F-8a2c2c)](run_analysis.md)
[![Anti-vibes](https://img.shields.io/badge/self--score_jitter-%2B38%20to%20%2D53-orange)](run_analysis.md)
[![Tamper-evidence](https://img.shields.io/badge/eval_ledger-hash--chained%20append--only-2d6a4f)](Engine/eval/ledger.jsonl)

I built RUMI — an autonomous scientific discovery engine that runs 16 phases from knowledge-graph construction to adversarial theory tournaments and even rewrites its own code. I also built its external evaluation harness, then let it grade itself, then let the harness grade the same runs, and compared.

This repo is what made that comparison possible. These are the artifacts from the paper (link here when it's live): all discovery-run reports, both scoring systems, and the frozen judge that produced the verdicts.

## A note on what's here

* **`Dataset/`** — every discovery run I logged: 51 runs in `Engine/eval/leaderboard.json`, 48+ archived runs with external scores, ~140 raw JSON + text reports. These are *raw outputs* and report *generated* content — not verified science. A big part of the story is that some of it is confidently wrong and confidently scored.
* **`Engine/discovery/`** — the full discovery pipeline (retrieval, knowledge graph, algorithms, the works), same code that generated the reports.
* **`Engine/eval/`** — the frozen evaluation harness: 6 deterministic metrics, A–F grading, flags for invalid citations / ungrounded claims / rediscovery of the archive, and a hash-chained append-only ledger so nobody (including me) can quietly change a past score. The agent is forbidden from touching `eval/` in its own self-modification loop.
* **`run_analysis.md`** — the compiled numbers, grouped tables, and a corrections log where I clean up the errors I made along the way.

## Headline numbers

* **0 A's. 0 B's. 45 C's. 6 F's.** Every A the engine gave itself was self-reported.
* Average external score: **52.0** — C grade.
* Its own score agrees with the judge either way on average (+1.1 gap), which is the problem: self-score is *unreliable in both directions*, with excitations up to **+38 points** — and it swings down 20 points below the judge on other runs.
* `no_citations` flag hits **51/51 runs.** It fetches real papers. It scores them 0/100 on evidence. Hmm.
* Scope note: this is a single-lab, single-developer artifact. If any of this looks like a demo, it's because the demo ran for 21 hours straight. Bug fixes and repro procedures live in the paper.

## tl;dr before you open the Dataset folder

RUMI runs a 16-phase autonomous discovery pipeline over retrieved research: it picks a research question, walks real citation networks, builds a persistent knowledge graph, mines gaps / anomalies / hidden variables, generates and falsifies mechanisms, runs a theory tournament, tries to beat itself in a second pass (sometimes successfully: pass 1 → 80, sometimes it gets worse: 83.8 → 65.2), and writes a report. Alongside it runs a self-scoring layer that judges its own quality — accuracy 0/100 so far on the frozen external metrics, apparently.

Everything in this repo is a *measurement artifact*, not a claim. The interesting finding isn't that an AI "discovered things" — it's precisely *which* self-assessments failed and *how*.

## How to run it

Everything you need to run the discovery pipeline is in `Engine/`:

```bash
# 1. Clone this repo:
git clone https://github.com/subhansh-dev/rumi-public
cd rumi-public/Engine

# 2. Install dependencies:
pip install -r requirements.txt

# 3. Add your (free-tier) API keys:
mkdir config
cp api_keys.md config/  # see api_keys.md for the full provider list
# Create config/api_keys.json from the example:
# cp config/api_keys.json.example config/api_keys.json
# Then fill in your keys (all providers have free tiers — see Engine/api_keys.md)

# 4. Run a discovery (grab a coffee, or 21 hours of coffee):
python run_discovery.py "your research topic" --mode full

# 5. Then judge it with the frozen harness:
python -m eval.harness data/discovery_v2_<timestamp>.json
```

The pipeline runs entirely from `Engine/` — `discovery/` has all 101 modules, `eval/` has the frozen judge, and `run_discovery.py` is the entrypoint. No other repos or packages needed beyond the Python dependencies above.

## Data provenance

* No API keys, tokens, or private data are included. The engine's owndat config file is intentionally absent.
* Run reports are LLM generation artifacts — treat them accordingly. The point of the paper is measuring when and how they fail.
* Copyright: the reports reference ~100 papers per run. Only metadata (title/abstract/urls) is stored in these JSONs, no full texts.

## Links

* The RUMI engine: [github.com/subhansh-dev/rumi](https://github.com/subhansh-dev/rumi)
* The related Luka spin-off: [github.com/subhansh-dev/luka](https://github.com/subhansh-dev/luka)
* Contact: [linkedin.com/in/subhansh-kumar67](https://linkedin.com/in/subhansh-kumar67) · subhansh.dev@gmail.com

Built by Subhansh Kumar. Data compiled November 2026.
