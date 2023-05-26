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

    ./kusto.py sii_author_clear
    ./kusto.py sii_author_import

    i=0
    while true; do
        ((i++))
        echo sleep 20, $i
        sleep 20
        ./kusto.py sii_author
        [[ "$(./kusto.py sii_author)" != "0" ]] && break
    done
else
    echo "Nothing changed."
    exit 0
fi
