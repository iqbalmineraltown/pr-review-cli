#!/bin/bash
# Wrapper script to run PR Review CLI

cd ~/projects/pr-review-cli
PYTHONPATH="$PWD:$PYTHONPATH" python3 -m pr_review.main "$@"
