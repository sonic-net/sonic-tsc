#!/bin/bash
author_list=author.list
csv=author.csv
unknown=author.unknown

while IFS= read -r line;do
    [ -z "$line" ] && continue

    if echo $line | grep @; then
        echo $line >> $unknown; continue
    fi

    if grep "$line" $csv 2>/dev/null; then
        grep "$line" $csv >> $csv.tmp
        continue
    fi

    gh api /users/$line -q ". | {login,name,company}" > tmp
    sleep 1
    name=$(cat tmp | jq -r ".name")
    id=$(cat tmp | jq -r ".login")
    company=$(cat tmp | jq -r ".company" | sed 's/,/ /g')

    echo $id,$name,$company >> $csv.tmp

done < $author_list
