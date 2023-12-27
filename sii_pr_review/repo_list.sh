#!/bin/bash

gh repo list sonic-net -L 100 --visibility=public --json name | jq -r ".[].name" | grep -v SONiC | grep -v DASH | grep -v sonic-mgmt$ | grep -v sonic-tsc | grep -v .github | awk '{print "sonic-net/"$1}' > repos
echo opencomputeproject/sai >> repos
sort repos >> tmp
mv tmp repos
