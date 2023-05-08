#!/bin/bash -x

years="2016 2017 2018 2019 2020 2021 2022 2023"
repos="sonic-net/sonic-buildimage"
months="01 02 03 04 05 06 07 08 09 10 11 12"
keys="additions,author,baseRefName,number,title,mergedAt"
interval=20
debug="#"
dump_type="prs"
bypass_year="n"

help(){
    echo "Use:"
    echo "    -i     # gh request interval, default $interval"
    echo "    -x     # if run gh command, default dry run"
    echo "    -y     # specify year list, default $years"
    echo "    -r     # repo list, default $repos"
    echo "    -t     # dump type[prs,reviews], default prs"
    echo "    -m     # dump by month, default by year"
}

while [[ $# > 0 ]]
do
    case "$1" in
        -r)
            repos=$2
            shift
            ;;
        -x)
            debug=""
            ;;
        -y)
            years=$2
            shift
            ;;
        -i)
            interval=$2
            shift
            ;;
        -t)
            dump_type=$2
            shift
            ;;
        -m)
            bypass_year="y"
            ;;
        -k)
            add_keys=$2
            shift
            ;;
        *)
            help
            exit 1
            ;;
    esac
    shift
done

[[ "$dump_type" == "reviews" ]] && keys="number,comments,latestReviews,reviews"
[[ "$dump_type" == "prs" ]] && keys+=$add_keys

echo years:    $years
echo repos:    $repos
echo months:    $months
echo keys:    $keys
echo interval:    $interval
echo debug:    $debug
echo dump:    $dump_type

delete_empty_file(){
    [ -n "$(find . -xtype f -name "*.json" -size -3c)" ] && rm $(find . -xtype f -name "*.json" -size -3c)
}

for year in $years
do
    echo year: $year
    mkdir -p $year
    for org_repo in $repos
    do
        repo=$(echo $org_repo | awk -F/ '{print$2}')
        org=$(echo $org_repo | awk -F/ '{print$1}')
        echo "    " repo: $repo
        if [[ "$bypass_year" == n ]];then
            delete_empty_file
            [ -f $year/$repo.$dump_type.json ] && continue
            eval $debug gh pr list -R $org_repo -L 10000 -s merged --json $keys -S "merged:$year-01-01..$year-12-31" | jq --indent 4 ".[] += {repo: \"$repo\"}" > $year/$repo.$dump_type.json
            delete_empty_file
            [ -f $year/$repo.$dump_type.json ] && sleep $interval && continue
        fi
        for month in $months
        do
            days=31
            [[ "$month" == "02" ]] && ([[ "$year" == "2016" ]] || [[ "$year" == "2020" ]]) && days=29
            [[ "$month" == "02" ]] && ([[ "$year" != "2016" ]] && [[ "$year" != "2020" ]]) && days=28
            [[ "$month" == "04" ]] || [[ "$month" == "06" ]] || [[ "$month" == "09" ]] || [[ "$month" == "11" ]] && days=30
            echo "        " $month $days
            [ -f $year/$repo.$month.$dump_type.json ] && continue
            # if the last day is not correct, download will fail.
            eval $debug gh pr list -R $org_repo -L 10000 -s merged --json $keys -S "merged:$year-$month-01..$year-$month-$days" | jq --indent 4 ".[] += {repo: \"$repo\"}" > $year/$repo.$month.$dump_type.json
            delete_empty_file
            sleep $interval && continue
        done    
    done
done
