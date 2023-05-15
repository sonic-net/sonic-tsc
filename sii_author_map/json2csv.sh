cat $1 | jq -r '.[] | "\(.Id),\(.Name),\(.Organization)"'
