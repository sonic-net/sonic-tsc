#!/bin/bash

gh repo list sonic-net -L 100 --public --json name | jq -r ".[].name" | grep -v SONiC | grep -v DASH | grep -v sonic-mgmt$ | grep -v .github | awk '{print "sonic-net/"$1}' > repos
echo opencomputeproject/sai >> repos
