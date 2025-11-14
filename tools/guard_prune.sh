#!/usr/bin/env bash
set -euo pipefail
RUN="${RUN:-/Volumes/122/runs/blueprint_mid_m2_v2}"
SNAP_KEEP="${SNAP_KEEP:-3}"
CKPT_KEEP="${CKPT_KEEP:-2}"
INTERVAL="${INTERVAL:-6000}"
log(){ printf "[%s] %s\n" "$(date '+%F %T')" "$*"; }
prune_instance_dir() {
  local D="$1"; local S_DIR="$D/snapshots"; local C_DIR="$D/checkpoints"
  if [ -d "$S_DIR" ]; then
    local EARLIEST; EARLIEST="$(ls -trd "$S_DIR"/snapshot_* 2>/dev/null | head -n1 || true)"
    local N_NEWEST=$(( SNAP_KEEP>0 ? SNAP_KEEP-1 : 0 ))
    local NEWEST_LIST=""; [ "$N_NEWEST" -gt 0 ] && NEWEST_LIST="$(ls -td "$S_DIR"/snapshot_* 2>/dev/null | head -n "$N_NEWEST" || true)"
    local COUNT=0; COUNT="$(ls -1d "$S_DIR"/snapshot_* 2>/dev/null | wc -l | tr -d ' ')"
    if [ "$COUNT" -ge 1 ]; then
      local PRUNED=0
      for s in "$S_DIR"/snapshot_*; do
        [ -e "$s" ] || continue
        if [ -n "$EARLIEST" ] && [ "$s" = "$EARLIEST" ]; then continue; fi
        if printf '%s\n' $NEWEST_LIST | grep -qx "$s"; then continue; fi
        rm -rf "$s" && PRUNED=$((PRUNED+1))
      done
      [ "$PRUNED" -gt 0 ] && log "Prune snapshots: $D → -$PRUNED"
    fi
  fi
  if [ -d "$C_DIR" ]; then
    ls -td "$C_DIR"/checkpoint_iter*_t*.pkl 2>/dev/null | grep -v regrets | \
    tail -n +$((CKPT_KEEP+1)) | xargs -r rm -f
  fi
}
log "START guard_prune: RUN='$RUN' SNAP_KEEP=$SNAP_KEEP CKPT_KEEP=$CKPT_KEEP INTERVAL=$INTERVAL"
while true; do
  FOUND=0
  for d in "$RUN"/instance_*; do
    [ -d "$d" ] || continue
    FOUND=1
    prune_instance_dir "$d"
  done
  if [ "$FOUND" -eq 0 ] && [ -d "$RUN" ]; then
    prune_instance_dir "$RUN"
  fi
  sleep "$INTERVAL"
done
