#!/bin/bash

repos="sonic-net/sonic-mgmt"
clone="n"

help(){
    echo "Use:"
    echo "    -r    # repo list, default $repos"
    echo "    -c    # force reclone repo."
}

while [[ $# > 0 ]]
do
    case "$1" in
        -r)
            repos=$2
            shift
            ;;
        -c)
            clone="y"
            ;;
        *)
            help
            exit 1
            ;;
    esac
    shift
done

for repo in $repos;do
    
    repo_base=$(echo $repo | awk -F/ '{print$2}')
    ignore=${repo_base}_ignore
    list=${repo_base}_hld.list
    csv=${repo_base}_hld.csv
    folder="docs/testplan"
    rm -f $csv.tmp
    echo repo: $repo_base
    echo csv: $csv
    echo list: $list
    echo ignore: $ignore
    echo folder: $folder
    [[ "$clone" == "y" ]] && rm -rf $repo_base
    [ -d $repo_base ] || git clone https://github.com/$repo

    cd $repo_base
    find $folder/ -xtype f -size +10c | grep -v -f ../$ignore > ../$list

    while IFS= read -r line;do
        if grep "$line" ../$csv 2> /dev/null | grep -v ,, > /dev/null ;then
            grep "$line" ../$csv | grep -v ,, >> ../$csv.tmp
            continue
        fi
        sha=$(git log --oneline --follow "$line" | tail -n 1 | awk '{print$1}')
        gh pr list -R $repo -L 1 -s merged --json author,mergedAt -S "$sha" > tmp && sleep 1
        author=$(cat tmp | jq -r ".[].author.login")
        mergedAt=$(cat tmp | jq -r ".[].mergedAt")
        if [ -z "$author" ];then
            pr=$(git show $sha | head -n 5 | grep -Eo "(#[0-9]*)" | grep -Eo [0-9]*)
            if [ -z $pr ];then
                author=$(git show $sha -s --format="%an<%ae>")
                mergedAt=$(date -d @$(git show $sha -s --format="%ct") +%FT%TZ)
                echo == $author,$mergedAt
            else
                gh pr list -R $repo -L 1 -s merged --json author,mergedAt -S "number $pr" > tmp && sleep 1
                author=$(cat tmp | jq -r ".[].author.login")
                mergedAt=$(cat tmp | jq -r ".[].mergedAt")
                echo == $pr,$author,$mergedAt
            fi
        fi
        echo $repo_base,$line,$author,$mergedAt >> ../$csv.tmp
    done <../$list

    cd ..
    mv $csv.tmp $csv
done
