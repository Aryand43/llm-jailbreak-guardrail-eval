#!/usr/bin/env bash
# More target models for Experiment 2: generate, guard, translate, judge and analyze each one with the
# same items, guard (Llama Guard 3 1B), judge (Qwen 2.5 7B) and thresholds as the main run. All share
# runs/experiment2-12gb (files are keyed by model name), so nothing from the main run is redone.
# Each step resumes where it stopped, so the script is safe to re-run. A failed target does not stop
# the others. Roughly 3 to 5 hours per target on a 12 GB card: run it overnight.
#
#   HF_TOKEN=... bash scripts/run_targets_gpu.sh            (all targets)
#   TARGETS="mistral7b" HF_TOKEN=... bash scripts/run_targets_gpu.sh   (just one)
#
# Results: runs/experiment2-12gb/ablations/target_<name>[_dialogue_calib]/, copied to
# results/experiment2-12gb/ablations/ and pushed at the end.
set -uo pipefail
cd "$(dirname "$0")/.."

: "${HF_TOKEN:?set HF_TOKEN (Hugging Face token)}"
export UV_NO_SYNC=1
export VLLM_USE_FLASHINFER_SAMPLER="${VLLM_USE_FLASHINFER_SAMPLER:-0}"
RUN=runs/experiment2-12gb
[ -f "$RUN/items.jsonl" ] || { echo "no $RUN/items.jsonl: run the main Experiment 2 first" >&2; exit 1; }
TARGETS="${TARGETS:-mistral7b qwen25_7b gemma2_2b}"

FAILED=()
step() {  # step <name> <command...>
  local name=$1; shift
  echo; echo "=================== $name"
  if "$@"; then echo "--- $name: ok"; return 0; fi
  echo "--- $name: FAILED" >&2; FAILED+=("$name"); return 1
}
pilot() { uv run python scripts/pilot.py "$@"; }

for t in $TARGETS; do
  cfg=configs/targets/$t.yaml
  model=$(uv run python -c "import yaml,sys; print(yaml.safe_load(open(sys.argv[1]))['target'])" "$cfg")
  if ! uv run python -c "from huggingface_hub import auth_check; auth_check('$model')" >/dev/null 2>&1; then
    echo "--- no access to $model: accept its licence at https://huggingface.co/$model" >&2
    FAILED+=("$t (no Hugging Face access)"); continue
  fi
  step "$t generate" pilot generate --config "$cfg" \
    && step "$t guard" pilot guard --config "$cfg" \
    && step "$t translate" pilot translate --config "$cfg" \
    && step "$t judge" pilot judge --config "$cfg" \
    && step "$t analyze" pilot analyze --config "$cfg" \
    && step "$t analyze (dialogue calibration)" pilot analyze --config "$cfg" \
         --calibrate-on dialogues --tag "target_${t}_dialogue_calib"
done

# Save and push the aggregate results (no response text is in these files).
mkdir -p results/experiment2-12gb/ablations
cp -r "$RUN"/ablations/target_* results/experiment2-12gb/ablations/ 2>/dev/null
git add results/experiment2-12gb/ablations
if git commit -qm "Add Experiment 2 results for more target models" && git push -q; then
  echo; echo "results pushed to GitHub"
else
  echo; echo "results saved in results/experiment2-12gb/ablations (push them yourself if git push failed)"
fi

echo
if [ ${#FAILED[@]} -eq 0 ]; then echo "ALL TARGETS DONE"; else printf 'FAILED: %s\n' "${FAILED[@]}"; exit 1; fi
