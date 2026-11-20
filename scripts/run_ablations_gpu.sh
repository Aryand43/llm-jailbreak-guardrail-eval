#!/usr/bin/env bash
# All Experiment 2 ablations on one GPU, in one go. Reuses the response pools in runs/experiment2-12gb
# (nothing is generated again). Each step resumes where it stopped, so the script is safe to re-run.
# A failed step does not stop the others; a summary at the end lists what failed.
#
#   HF_TOKEN=... bash scripts/run_ablations_gpu.sh
#
# Needs: the main Experiment 2 run finished (runs/experiment2-12gb), and the Llama Guard 3 8B licence
# accepted on Hugging Face. Results: runs/experiment2-12gb/ablations/<name>/, copied to
# results/experiment2-12gb/ablations/ and pushed at the end.
set -uo pipefail
cd "$(dirname "$0")/.."

: "${HF_TOKEN:?set HF_TOKEN (Hugging Face token with access to the Llama Guard models)}"
export UV_NO_SYNC=1
export VLLM_USE_FLASHINFER_SAMPLER="${VLLM_USE_FLASHINFER_SAMPLER:-0}"
RUN=runs/experiment2-12gb
BASE=configs/experiment2_12gb.yaml
[ -f "$RUN/samples.jsonl" ] || { echo "no $RUN/samples.jsonl: run the main Experiment 2 first" >&2; exit 1; }

FAILED=()
step() {  # step <name> <command...>
  local name=$1; shift
  echo; echo "=================== $name"
  if "$@"; then echo "--- $name: ok"; return 0; fi
  echo "--- $name: FAILED" >&2; FAILED+=("$name"); return 1
}
has_access() {  # gated Hugging Face repos (Llama Guard) need an approved licence request
  uv run python -c "from huggingface_hub import auth_check; auth_check('$1')" >/dev/null 2>&1
}
pilot() { uv run python scripts/pilot.py "$@"; }

# 1. Guardrail size: Llama Guard 3 8B (FP8). If FP8 loading runs out of memory, fall back to 4-bit.
echo; echo "=================== guard 8B (fp8)"
if ! has_access meta-llama/Llama-Guard-3-8B; then
  echo "--- no access to meta-llama/Llama-Guard-3-8B: request it at https://huggingface.co/meta-llama/Llama-Guard-3-8B" >&2
  echo "--- skipping the guard-size ablation; re-run this script once access is approved" >&2
  FAILED+=("guard 8B (no Hugging Face access)")
elif pilot guard --config configs/ablations/guard_llamaguard8b.yaml; then
  step "analyze guard 8B" pilot analyze --config configs/ablations/guard_llamaguard8b.yaml
else
  echo "--- FP8 failed (usually out of memory); retrying with the pre-quantized 4-bit AWQ copy"
  step "guard 8B (4-bit AWQ)" pilot guard --config configs/ablations/guard_llamaguard8b_awq.yaml \
    && step "analyze guard 8B (4-bit AWQ)" pilot analyze --config configs/ablations/guard_llamaguard8b_awq.yaml
fi

# 2. Guardrail context: the 1B guard reads the whole dialogue.
step "guard session" pilot guard --config configs/ablations/guard_session.yaml \
  && step "analyze session" pilot analyze --config configs/ablations/guard_session.yaml

# 3. Second judge from another family (Mistral 7B).
step "judge Mistral" pilot judge --config configs/ablations/judge_mistral.yaml \
  && step "analyze judge Mistral" pilot analyze --config configs/ablations/judge_mistral.yaml

# 4. Judge reads the original language instead of the translation.
step "judge native" pilot judge --config configs/ablations/judge_native.yaml \
  && step "analyze judge native" pilot analyze --config configs/ablations/judge_native.yaml

# 5-6. Analysis only (no model): permuted labels, thresholds calibrated on benign dialogues.
step "permuted labels" pilot analyze --config "$BASE" --permute-labels --tag permuted
step "dialogue calibration" pilot analyze --config "$BASE" --calibrate-on dialogues --tag dialogue_calib

# Save and push the aggregate results (no response text is in these files).
mkdir -p results/experiment2-12gb
cp -r "$RUN/ablations" results/experiment2-12gb/
git add results/experiment2-12gb/ablations
if git commit -qm "Add Experiment 2 ablation results" && git push -q; then
  echo; echo "results pushed to GitHub"
else
  echo; echo "results saved in results/experiment2-12gb/ablations (push them yourself if git push failed)"
fi

echo
if [ ${#FAILED[@]} -eq 0 ]; then echo "ALL ABLATIONS DONE"; else printf 'FAILED: %s\n' "${FAILED[@]}"; exit 1; fi
