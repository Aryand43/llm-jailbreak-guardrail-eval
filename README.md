# harmfloor

Bound-based evaluation of residual jailbreak harm across attack taxonomies, benchmarks and guardrails (ACL revision of *On the Limits of Support-Preserving Alignment and Bounded Filtering*).

Start with [docs/METHODOLOGY.md](docs/METHODOLOGY.md).

Integration is being prepared on `aniket`, with Aryan as supervisor. See the
[handoff and remaining decisions](docs/INTEGRATION_STATUS.md),
[loader API](docs/DATA_LOADERS.md), and [annotation workflow](docs/ANNOTATION.md).
Aryan approved the pilot protocol on 2026-10-27. See the
[accepted pilot decisions](docs/PILOT_CASE_REVIEW_2026-10-28.md) for the current
100-case selection: 76 harmful, 23 separate over-refusal and 1 excluded.
The report records validation results, remaining rubric questions and experiment prerequisites.

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest
uv run python scripts/fetch_data.py     # raw datasets into data/raw/ (pinned, checksummed)
uv run python scripts/check_models.py   # which configured models OpenRouter serves
```

## Layout

| Path | What it is |
|---|---|
| `docs/METHODOLOGY.md` | Research method: bounds, hypotheses, experiments, open decisions |
| `configs/taxonomy.yaml` | Unified attack families and harm domains, with crosswalks from each benchmark |
| `configs/benchmarks.yaml` | Dataset registry: source, licence, status |
| `configs/experiment.yaml` | Models, budgets, defenses, judges |
| `harmfloor/schema.py` | Record format every loader and run emits |
| `harmfloor/taxonomy.py` | Label mapping; loaders must map labels through this |
| `harmfloor/bounds.py` | Ceiling, floor and bound decomposition estimators |
| `harmfloor/plots.py` | Paper figures |
| `harmfloor/data/` | Benchmark loaders (one module per source) and the annotation gate |
| `data/annotations/` | Our reviewed labels, one JSONL per source; unreviewed items are held out |
| `harmfloor/openrouter.py` | OpenRouter client; logs tokens and cost per call to `runs/` |

## Rules

- Never commit API keys. Put `OPENROUTER_API_KEY` in `.env` (gitignored).
- Raw datasets go in `data/raw/<source>/` (gitignored); record the source and licence in `configs/benchmarks.yaml`.
- Map labels only through `harmfloor/taxonomy.py`. If a label has no mapping, add it to `configs/taxonomy.yaml` with `review: true`.
