#!/bin/bash


../sii_pr_review/pr_dump.sh -r sonic-net/sonic-mgmt -k ,files -m -t prs "$@"

../sii_pr_review/pr_dump.sh -r sonic-net/sonic-mgmt -k ,files -m -t reviews "$@"
