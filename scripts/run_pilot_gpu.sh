#!/usr/bin/env bash
# Pilot on one NVIDIA GPU: >= 24 GB with configs/pilot.yaml, 12 GB with configs/pilot_12gb.yaml. Each stage is its own process so the
# GPU holds one model at a time. Safe to re-run: every stage resumes where it stopped.
#
# One-time setup on the GPU machine:
#   1. Accept the licences for meta-llama/Llama-3.1-8B-Instruct and meta-llama/Llama-Guard-3-8B
#      on huggingface.co, then: export HF_TOKEN=...
#   2. sudo apt install -y build-essential   (Triton needs a C compiler to build GPU kernels)
#   3. uv sync && uv pip install vllm
#   4. uv run python scripts/fetch_data.py
set -euo pipefail
cd "$(dirname "$0")/.."
CONFIG="${CONFIG:-configs/pilot.yaml}"   # configs/pilot_12gb.yaml on a 12 GB card

: "${HF_TOKEN:?set HF_TOKEN (Hugging Face token with access to the Llama models)}"
command -v cc >/dev/null || { echo "no C compiler: sudo apt install -y build-essential" >&2; exit 1; }
# `uv pip install vllm` changes pinned packages (e.g. numpy); stop `uv run` from reverting them.
export UV_NO_SYNC=1
# FlashInfer's sampler JIT-compiles with nvcc, which WSL/consumer setups lack; vLLM's PyTorch
# sampler gives the same sampling without it. Override with VLLM_USE_FLASHINFER_SAMPLER=1.
export VLLM_USE_FLASHINFER_SAMPLER="${VLLM_USE_FLASHINFER_SAMPLER:-0}"
python_check='import vllm, torch; assert torch.cuda.is_available(), "no CUDA GPU"; print("vllm", vllm.__version__, "|", torch.cuda.get_device_name(0))'
uv run python -c "$python_check"

# SMOKE=1 runs 5 items per role with 8 samples each (minutes) into runs/smoke. Do this first.
if [ "${SMOKE:-0}" = "1" ]; then
  RUN_DIR="${RUN_DIR:-runs/smoke}"; EXTRA=(--n 8); BUILD=(--limit 5)
else
  RUN_DIR="${RUN_DIR:-$(uv run python -c "import yaml,sys; print(yaml.safe_load(open(sys.argv[1]))['run_dir'])" "$CONFIG")}"; EXTRA=(); BUILD=()
fi
[ -f "$RUN_DIR/items.jsonl" ] || uv run python scripts/pilot.py build --config "$CONFIG" --run-dir "$RUN_DIR" "${BUILD[@]}"
uv run python scripts/pilot.py generate --config "$CONFIG" --run-dir "$RUN_DIR" "${EXTRA[@]}"
uv run python scripts/pilot.py guard    --config "$CONFIG" --run-dir "$RUN_DIR"
uv run python scripts/pilot.py judge    --config "$CONFIG" --run-dir "$RUN_DIR"
uv run python scripts/pilot.py analyze  --config "$CONFIG" --run-dir "$RUN_DIR"
