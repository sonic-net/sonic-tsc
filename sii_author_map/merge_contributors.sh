#!/bin/bash
csv=author.csv

./json2csv.sh contributors.json > tmp.csv
while IFS= read -r line;do
    id=$(echo $line | awk -F, '{print$1}')
    if grep "^$id," tmp.csv 2>/dev/null; then
        continue
    fi

    echo $line >> tmp.csv
done < $csv

sort tmp.csv > tmp
mv tmp $csv
rm tmp.csv
