# No real API keys in this repository.

## RUMI engine configuration

The engine reads provider API keys from `config/api_keys.json` (NOT included here).
Create your own `config/api_keys.json` -- see the RUMI engine repo for the full schema:
https://github.com/subhansh-dev/rumi

## Providers used (all have free tiers)

The engine routes across 4 providers with automatic fallback. Every provider below
has a free tier (or free credits) -- no paid subscription is required to run RUMI.

1. **Groq** -- `llama-3.3-70b-versatile` (3 API keys, fast fallback, 30 req/min free)
2. **Cerebras** -- `gpt-oss-120b` (6 API keys, primary for creative phases, fast fallback)
3. **NVIDIA NIM** -- `nvidia/llama-3.1-nemotron-ultra-253b-v1` (free API key; also hosts Kimi K2.6, GLM 5.1, and DeepSeek V4 Pro via the same key)
4. **Fireworks** -- `accounts/fireworks/models/deepseek-r1` ($6 free credits, temporary)

Routing chain: Cerebras -> Groq -> NVIDIA NIM -> Fireworks.
Math phases route through reasoning models hosted on NVIDIA NIM.
Critic/adversarial phases are pinned to GLM 5.1 (hosted on NVIDIA NIM, a disjoint
model family) to avoid self-preference bias.

## Notes

- Groq keys 1 & 2 were dead (401) during the original runs; key 3 worked.
- Fireworks credits ($6) are temporary and may be exhausted.
- Xiaomi MiMo was disabled in later runs due to rate-limiting.
- 13 of 17 keys were healthy (82%) as of the last run (June 2026).
