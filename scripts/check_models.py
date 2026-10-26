#!/usr/bin/env python3
"""Check every model in configs/experiment.yaml against OpenRouter's public catalogue.

    uv run python scripts/check_models.py
"""

from pathlib import Path

import yaml

from harmfloor.openrouter import OpenRouterClient, check_models

CONFIG = Path(__file__).resolve().parents[1] / "configs" / "experiment.yaml"


def main() -> None:
    groups = yaml.safe_load(CONFIG.read_text())["models"]
    slugs = [s for group in groups.values() for s in group]
    with OpenRouterClient(api_key="unused") as client:
        rows = check_models(client.list_models(), slugs)
    print("| model | served | temperature | top_p | seed | $/M in | $/M out |")
    print("|---|---|---|---|---|---|---|")
    yes = lambda b: "yes" if b else "NO"
    for r in rows:
        if not r.available:
            print(f"| {r.slug} | NO | | | | | |")
            continue
        print(f"| {r.slug} | yes | {yes(r.temperature)} | {yes(r.top_p)} | {yes(r.seed)} "
              f"| {r.prompt_usd_per_m} | {r.completion_usd_per_m} |")


if __name__ == "__main__":
    main()
