#!/bin/bash

years="2016 2017 2018 2019 2020 2021 2022"
repos="sonic-net/sonic-buildimage"
months="01 02 03 04 05 06 07 08 09 10 11 12"
keys="additions,author,baseRefName,number,title,mergedAt"
interval=20
dump_type="prs"
bypass_year="n"

help(){
    echo "Use:"
    echo "    -i     # gh request interval, default $interval"
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

echo ============================================================================
echo years:    $years
echo repos:    $repos
echo months:   $months
echo keys:     $keys
echo interval: $interval
echo dump:     $dump_type

dump_by_year(){
    year=$1
    org_repo=$2
    repo=$(echo $org_repo | awk -F/ '{print$2}')
    org=$(echo $org_repo | awk -F/ '{print$1}')
    start=$year-01-01
    end=$year-12-31
    file_by_year=$year/$repo.$dump_type.json
    pr_count=$(gh pr list -R $org_repo -L 10000 -s merged --json number -S "merged:$start..$end" | jq length)
    echo "    pr count: $pr_count"
    (( $pr_count >= 1000 )) && echo "    dump by month!" && return 1
    [[ $pr_count == 0 ]] && echo "    no pr found!" && return 0
    [[ "$bypass_year" == y ]] && echo "    dump by month!" && return 1
    { gh pr list -R $org_repo -L 10000 -s merged --json $keys -S "merged:$start..$end" | jq --indent 4 "[.[] | . += {repo: \"$repo\", author: .author.login}] | sort_by(-.number)" > $file_by_year && sleep $interval; } || return $?
    [[ "$(cat $file_by_year | jq length)" != "$pr_count" ]] && echo "    pr count not match! $(cat $file_by_year | jq length) $pr_count" && return 1
    return 0
}

dump_by_10day(){
    a=$year/$repo.$month.a.$dump_type.json
    b=$year/$repo.$month.b.$dump_type.json
    c=$year/$repo.$month.c.$dump_type.json

    echo "            dump by 10 days"
    gh pr list -R $org_repo -L 10000 -s merged --json $keys -S "merged:$year-$month-01..$year-$month-10" | jq --indent 4 "[.[] | . += {repo: \"$repo\", author: .author.login}]" > $a
    echo "            $year-$month-01..$year-$month-10,$(cat $a | jq length)"
    sleep 10
    gh pr list -R $org_repo -L 10000 -s merged --json $keys -S "merged:$year-$month-11..$year-$month-20" | jq --indent 4 "[.[] | . += {repo: \"$repo\", author: .author.login}]" > $b
    echo "            $year-$month-11..$year-$month-20,$(cat $b | jq length)"
    sleep 10
    gh pr list -R $org_repo -L 10000 -s merged --json $keys -S "merged:$year-$month-21..$end"            | jq --indent 4 "[.[] | . += {repo: \"$repo\", author: .author.login}]" > $c
    echo "            $year-$month-21..$end,$(cat $c | jq length)"
    jq -s 'add sort_by(-.number)' --indent 4 $a $b $c > $file_by_month
}

for year in $years
do
    echo year: $year
    mkdir -p $year
    for org_repo in $repos
    do
        repo=$(echo $org_repo | awk -F/ '{print$2}')
        org=$(echo $org_repo | awk -F/ '{print$1}')
        echo "    repo: $repo"
        # try dump by year when bypass_year==n and no monthly dump files
        dump_by_year $year $org_repo && continue

        # try dump by month, when dump by year failed
        for month in $months
        do
            file_by_month=$year/$repo.$month.$dump_type.json
            start=$year-$month-01
            [[ $start > $(date -I) ]] && break
            # if the last day is not correct, download will fail.
            end=$(date -d "$year/$month/1 + 1 month -1 day" "+%Y-%m-%d")
            pr_count=$(gh pr list -R $org_repo -L 10000 -s merged --json number -S "merged:$start..$end" | jq length)
            echo "        $start,$end,$pr_count"
            gh pr list -R $org_repo -L 10000 -s merged --json $keys -S "merged:$start..$end" | jq --indent 4 "[.[] | . += {repo: \"$repo\", author: .author.login}] | sort_by(-.number)" > $file_by_month
            sleep $interval
            [[ "$(cat $file_by_month | jq length)" != "$pr_count" ]] && echo "        pr count not match! $(cat $file_by_year | jq length) $pr_count" || continue

            # try dump by 10 days, when dump by month failed
            dump_by_10day
        done    
        jq -s 'add | sort_by(-.number)' --indent 4 $year/$repo.*.$dump_type.json > $file_by_year
        rm $year/$repo.*.$dump_type.json
    done
done
