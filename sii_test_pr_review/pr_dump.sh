#!/bin/bash

../sii_pr_review/pr_dump.sh -r sonic-net/sonic-mgmt -k ,files -y 2023 -m -t prs

../sii_pr_review/pr_dump.sh -r sonic-net/sonic-mgmt -k ,files -y 2023 -m -t reviews
