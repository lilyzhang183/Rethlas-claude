#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROBLEM_FILE="${PROBLEM_FILE:-data/example.md}"
MODEL="${MODEL:-claude-opus-4-8}"
EFFORT="${EFFORT:-xhigh}"
REQUIRE_VERIFICATION="${REQUIRE_VERIFICATION:-1}"

if [[ "$PROBLEM_FILE" = /* ]]; then
  echo "PROBLEM_FILE must be relative to agents/generation: $PROBLEM_FILE" >&2
  exit 1
fi

if [[ "$PROBLEM_FILE" == ".." || "$PROBLEM_FILE" == ../* || "$PROBLEM_FILE" == */.. || "$PROBLEM_FILE" == */../* ]]; then
  echo "PROBLEM_FILE must not contain '..': $PROBLEM_FILE" >&2
  exit 1
fi

if [[ "$PROBLEM_FILE" != data/*.md ]]; then
  echo "PROBLEM_FILE must point to a markdown file under data/: $PROBLEM_FILE" >&2
  exit 1
fi

if [[ ! -f "$ROOT_DIR/$PROBLEM_FILE" ]]; then
  echo "Problem file not found: $ROOT_DIR/$PROBLEM_FILE" >&2
  exit 1
fi

# data/algebra/prob1.md → algebra/prob1
problem_rel="${PROBLEM_FILE#data/}"
problem_rel="${problem_rel%.md}"
problem_id="$(basename "$PROBLEM_FILE" .md)"
ref_dir="data/${problem_rel}.refs"
ref_prompt="Use reference_dir=${ref_dir} if it exists."

prepare_references() {
  local abs_ref_dir="$ROOT_DIR/$ref_dir"
  if [[ ! -d "$abs_ref_dir" ]]; then
    return
  fi

  local manifest_entries=()
  local pdf_count=0
  local extracted_at
  extracted_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  while IFS= read -r -d '' pdf; do
    pdf_count=$((pdf_count + 1))
    if ! command -v pdftotext >/dev/null 2>&1; then
      echo "WARNING: found PDF references, but pdftotext is not installed; PDFs will be ignored." >&2
      return
    fi

    local rel_pdf="${pdf#"$abs_ref_dir"/}"
    local txt="$abs_ref_dir/.extracted/${rel_pdf%.pdf}.txt"
    mkdir -p "$(dirname "$txt")"
    local extract_status="ok"
    if [[ ! -f "$txt" || "$pdf" -nt "$txt" ]]; then
      if ! pdftotext -layout "$pdf" "$txt"; then
        extract_status="extraction_failed"
      fi
    else
      extract_status="cached"
    fi

    local pdf_sha=""
    local txt_sha=""
    if command -v shasum >/dev/null 2>&1; then
      pdf_sha="$(shasum -a 256 "$pdf" | awk '{print $1}')"
      if [[ -f "$txt" ]]; then
        txt_sha="$(shasum -a 256 "$txt" | awk '{print $1}')"
      fi
    fi

    manifest_entries+=("{\"source_file\":\"$ref_dir/$rel_pdf\",\"source_sha256\":\"$pdf_sha\",\"text_file\":\"$ref_dir/.extracted/${rel_pdf%.pdf}.txt\",\"text_sha256\":\"$txt_sha\",\"extracted_at\":\"$extracted_at\",\"extractor\":\"pdftotext -layout\",\"status\":\"$extract_status\"}")
  done < <(find "$abs_ref_dir" -type f -iname '*.pdf' -not -path "$abs_ref_dir/.extracted/*" -print0)

  # Also list plain-text reference files (.md / .tex / .txt at top level)
  while IFS= read -r -d '' textref; do
    local rel_text="${textref#"$abs_ref_dir"/}"
    local text_sha=""
    if command -v shasum >/dev/null 2>&1; then
      text_sha="$(shasum -a 256 "$textref" | awk '{print $1}')"
    fi
    manifest_entries+=("{\"source_file\":\"$ref_dir/$rel_text\",\"source_sha256\":\"$text_sha\",\"text_file\":\"$ref_dir/$rel_text\",\"text_sha256\":\"$text_sha\",\"extracted_at\":\"$extracted_at\",\"extractor\":\"none\",\"status\":\"plain_text\"}")
  done < <(find "$abs_ref_dir" -maxdepth 1 -type f \( -iname '*.md' -o -iname '*.tex' -o -iname '*.txt' \) -print0)

  if [[ ${#manifest_entries[@]} -gt 0 ]]; then
    local manifest_path="$abs_ref_dir/reference_manifest.json"
    {
      printf '['
      local first=1
      for entry in "${manifest_entries[@]}"; do
        if [[ $first -eq 1 ]]; then
          first=0
        else
          printf ','
        fi
        printf '\n  %s' "$entry"
      done
      printf '\n]\n'
    } > "$manifest_path"
    echo "Wrote reference manifest: $manifest_path"
  fi

  if [[ $pdf_count -gt 0 ]]; then
    ref_prompt="Use reference_dir=${ref_dir} if it exists. PDF references have been extracted to ${ref_dir}/.extracted; read those extracted .txt files instead of the PDFs. A reference_manifest.json at ${ref_dir}/reference_manifest.json maps each source to its extracted text with sha256 hashes; cite files by stable manifest IDs (source_file + source_sha256) in your proof references."
  elif [[ ${#manifest_entries[@]} -gt 0 ]]; then
    ref_prompt="Use reference_dir=${ref_dir} if it exists. A reference_manifest.json at ${ref_dir}/reference_manifest.json lists each available reference file with sha256 hashes; cite files by stable manifest IDs."
  fi
}

prepare_references

LOG_DIR="${LOG_DIR:-$ROOT_DIR/logs/$problem_rel}"
mkdir -p "$LOG_DIR"

log_file="$LOG_DIR/${problem_id}.md"

if [[ "$REQUIRE_VERIFICATION" == "1" ]]; then
  run_mode="verified"
else
  run_mode="exploratory"
fi

# MODE_CEILING optionally caps the maximum accuracy mode the agent may
# enter (exploration | assembly | rigor | verification). When unset,
# the agent may progress sequentially through all four. When set, the
# agent self-declares transitions but may not move past the ceiling.
MODE_CEILING="${MODE_CEILING:-verification}"

prompt="Use CLAUDE.md exactly to solve the math problem in ${PROBLEM_FILE}. Use problem_id=${problem_rel}. run_mode=${run_mode}. mode_ceiling=${MODE_CEILING}. ${ref_prompt}"

CLAUDE_VERSION="$(claude --version 2>/dev/null || echo 'unknown')"

echo "========================================"
echo " Claude Code:  $CLAUDE_VERSION"
echo " Model:        $MODEL"
echo " Effort:       $EFFORT"
echo " Run mode:     $run_mode"
echo " Problem:      $PROBLEM_FILE"
echo " Problem ID:   $problem_rel"
echo " References:   $ref_dir"
echo " Log:          $log_file"
echo "========================================"
echo ""
echo "Running ${PROBLEM_FILE} -> $log_file"

START_EPOCH=$(date +%s)

elapsed_timer() {
  while true; do
    sleep 30
    local now=$(date +%s)
    local secs=$((now - START_EPOCH))
    printf "\r  [elapsed %02d:%02d:%02d] still running..." \
      $((secs/3600)) $(((secs%3600)/60)) $((secs%60))
  done
}
elapsed_timer &
TIMER_PID=$!
cleanup_timer() {
  kill "$TIMER_PID" 2>/dev/null || true
  wait "$TIMER_PID" 2>/dev/null || true
}
trap cleanup_timer EXIT

VERIFY_URL="${VERIFY_URL:-http://127.0.0.1:8091/health}"
if ! curl -sf "$VERIFY_URL" >/dev/null 2>&1; then
  if [[ "$REQUIRE_VERIFICATION" == "1" ]]; then
    echo "ERROR: verification service not reachable at ${VERIFY_URL%%/health*}" >&2
    echo "       The proof-writing discipline requires a verified outcome by default." >&2
    echo "       Either start the verification service first:" >&2
    echo "         cd agents/verification && uvicorn api.server:app --host 0.0.0.0 --port 8091" >&2
    echo "       or, for an exploratory unverified run, set REQUIRE_VERIFICATION=0." >&2
    exit 1
  else
    echo "WARNING: verification service not reachable at ${VERIFY_URL%%/health*}"
    echo "         REQUIRE_VERIFICATION=0 set; running in EXPLORATORY mode."
    echo "         The blueprint will NOT be renamed to blueprint_verified.md."
    echo ""
  fi
fi

claude_rc=0
(
  cd "$ROOT_DIR"
  claude \
    -p "$prompt" \
    --model "$MODEL" \
    --effort "$EFFORT" \
    --dangerously-skip-permissions
) >"$log_file" 2>&1 || claude_rc=$?

cleanup_timer
trap - EXIT

END_EPOCH=$(date +%s)
TOTAL=$((END_EPOCH - START_EPOCH))
printf "\n"

if [[ $claude_rc -ne 0 ]]; then
  echo "claude exited with code $claude_rc (see $log_file for details)"
fi

echo "Finished ${PROBLEM_FILE} -> $log_file"
printf "Total time: %02d:%02d:%02d\n" \
  $((TOTAL/3600)) $(((TOTAL%3600)/60)) $((TOTAL%60))
echo ""
echo "To view results in the browser, run:"
echo "  ./site/serve.sh"
echo "Then open http://localhost:3264"
