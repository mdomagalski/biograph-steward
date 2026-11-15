#!/bin/sh
# Replays the exact fixed argument vector on the private synthetic-header FASTAs.
# MMseqs2 release18-8cc5c; binary SHA256:
# b7ef6e0e33df5dd4fa9cf988cbd8b4988c11a3a1255d2c377f13e1bb40c157fb
set -eu
: "${MMSEQS2_BIN:?Set MMSEQS2_BIN to the pinned CPU executable}"
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 "$MMSEQS2_BIN" easy-search \
  query.fasta target.fasta matches.private.tsv tmp \
  --threads 2 -s 7.5 -e 0.001 --min-seq-id 0.3 -c 0.8 --cov-mode 0 \
  --alignment-mode 3 --max-seqs 5000 --split-memory-limit 8G \
  --format-output query,target,fident,alnlen,qcov,tcov,evalue,bits,qlen,tlen
