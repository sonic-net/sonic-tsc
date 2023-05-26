#!/bin/bash -ex

git pull
cd ../sonic-contributor-map
git pull
cd -
cp ../sonic-contributor-map/contributors.json sii_author_map/
cd sii_author_map
./merge_contributors.sh 1>/dev/null
git diff author.csv

if git diff author.csv | grep diff ;then
    set -e
    echo "author.csv changed"
    git diff author.csv

    git add author.csv
    git commit -m "author.csv changed"
    git push
    cd ..

    sleep 1
    ./kusto.py sii_author_clear
    sleep 1
    ./kusto.py sii_author_import

    i=1
    while true; do
        echo "sleep 20, $i"
        sleep 20
        ./kusto.py sii_author | jq '.data[0].Count'
        [[ "$(./kusto.py sii_author | jq '.data[0].Count')" != "0" ]] && break
        ((i++))
    done
    ./kusto.py sii_org > Sii_org.csv
    ./kusto.py sii_person > Sii_author.csv
else
    echo "Nothing changed."
    exit 0
fi
