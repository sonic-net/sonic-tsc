#!/bin/bash

gh issue list -L 10000 -s all -R sonic-net/sonic-buildimage --json number,author,state,createdAt,labels | jq --indent 4 > issues.json
./parse_issues.py issues.json
