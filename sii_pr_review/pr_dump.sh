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

dump_adaptive_by_month(){
    local month_last_day=${end:8:2}
    local start_day=1
    local end_day
    local range_start
    local range_end
    local step
    local idx=0
    local tmp_file
    local result
    local ok
    local -a tmp_files=()

    echo "            dump by adaptive chunk: 10 -> 5 -> 3"

    while (( start_day <= month_last_day ))
    do
        ok="n"
        for step in 10 5 3
        do
            end_day=$(( start_day + step - 1 ))
            (( end_day > month_last_day )) && end_day=$month_last_day
            range_start=$(printf "%s-%s-%02d" "$year" "$month" "$start_day")
            range_end=$(printf "%s-%s-%02d" "$year" "$month" "$end_day")
            tmp_file="$year/$repo.$month.$idx.$dump_type.json"

            result=$(gh pr list -R "$org_repo" -L 10000 -s merged --json "$keys" -S "merged:$range_start..$range_end")
            if [[ -n "$result" ]]; then
                printf '%s\n' "$result" | jq --indent 4 "[.[] | . += {repo: \"$repo\", author: .author.login}]" > "$tmp_file" || return $?
                echo "            $range_start..$range_end,$(jq length "$tmp_file")"
                sleep "$interval"
                tmp_files+=("$tmp_file")
                idx=$(( idx + 1 ))
                start_day=$(( end_day + 1 ))
                ok="y"
                break
            fi

            echo "            range failed with ${step}-day window, fallback"
        done

        [[ "$ok" == "y" ]] || return 1
    done

    jq -s 'add | sort_by(-.number)' --indent 4 "${tmp_files[@]}" > "$file_by_month" || return $?
    rm -rf "${tmp_files[@]}"
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
            if [[ "$dump_type" != "reviews" || ( "$repo" != "sonic-buildimage" && "$repo" != "sonic-mgmt" ) ]]; then
                gh pr list -R $org_repo -L 10000 -s merged --json $keys -S "merged:$start..$end" | jq --indent 4 "[.[] | . += {repo: \"$repo\", author: .author.login}] | sort_by(-.number)" > $file_by_month
                sleep $interval
                [[ "$(cat $file_by_month | jq length)" != "$pr_count" ]] && echo "        pr count not match! $(cat $file_by_month | jq length) $pr_count" || continue
            fi

            # for each remaining range: try 10 days, fallback to 5 days, then 3 days
            dump_adaptive_by_month || return $?
            continue
        done    
        if [[ "$repo" != "sonic-buildimage" && "$repo" != "sonic-mgmt" ]]; then
            jq -s 'add | sort_by(-.number)' --indent 4 $year/$repo.*.$dump_type.json > $file_by_year
            rm $year/$repo.*.$dump_type.json -rf
        else
            rm $file_by_year -rf
        fi
    done
done
