#!/bin/bash
# Dump approvals and changed files of merged PRs, one file per month, for the last N days.
# Only PRs into the default branch are included.
# Output: <out_dir>/YYYY-MM.json = [{number, author, mergedAt, files: [path], approvals: [{login, at}]}]
# Months before the current and previous month are not refetched if the file exists.

days=730
interval=1

help(){
    echo "Use:"
    echo "    $0 -r <org/repo> -o <out_dir> [-d days] [-i interval]"
}

while [[ $# > 0 ]]
do
    case "$1" in
        -r) repo=$2; shift ;;
        -o) out=$2; shift ;;
        -d) days=$2; shift ;;
        -i) interval=$2; shift ;;
        *) help; exit 1 ;;
    esac
    shift
done
[ -z "$repo" ] || [ -z "$out" ] && { help; exit 1; }

# Only PRs merged into the default branch count; backports to release branches are skipped.
base=$(gh repo view $repo --json defaultBranchRef -q .defaultBranchRef.name) || { echo "cannot get default branch of $repo"; exit 1; }

mkdir -p $out
set -o pipefail

fetch_once(){
    gh pr list -R $repo -B "$base" -L 10000 -s merged -S "merged:$1..$2" --json number,author,mergedAt,files,reviews |
        jq --indent 2 '[.[] | {number, author: .author.login, mergedAt, files: [.files[].path],
            approvals: [.reviews[] | select(.state == "APPROVED") | {login: .author.login, at: .submittedAt}]}]'
}

# Retry on GraphQL 5xx/timeouts; if a range keeps failing, split it in halves and merge.
fetch_range(){
    local a=$1 b=$2 attempt
    for attempt in 1 2 3
    do
        fetch_once $a $b && return 0
        echo "fetch $a..$b attempt $attempt failed" >&2
        sleep $((attempt * 10))
    done
    [ "$a" = "$b" ] && return 1
    local days=$(( ($(date -u -d $b +%s) - $(date -u -d $a +%s)) / 86400 ))
    local mid=$(date -u -d "$a +$((days / 2)) day" +%Y-%m-%d)
    local next=$(date -u -d "$mid +1 day" +%Y-%m-%d)
    echo "splitting $a..$b" >&2
    local left right
    left=$(fetch_range $a $mid) && right=$(fetch_range $next $b) || return 1
    jq -s --indent 2 'add' <<<"$left $right"
}
start=$(date -u -d "$days days ago" +%Y-%m-01)
this_month=$(date -u +%Y-%m)
prev_month=$(date -u -d "$(date -u +%Y-%m-01) -1 month" +%Y-%m)

# Drop months that left the window.
for f in $out/*.json
do
    [ -e "$f" ] || continue
    m=$(basename $f .json)
    [[ "$m" < "${start:0:7}" ]] && rm -f $f
done

month=$start
while [[ ! "${month:0:7}" > "$this_month" ]]
do
    ym=${month:0:7}
    next=$(date -u -d "$month +1 month" +%Y-%m-01)
    last=$(date -u -d "$next -1 day" +%Y-%m-%d)
    file=$out/$ym.json
    if [ ! -s $file ] || [[ "$ym" == "$this_month" || "$ym" == "$prev_month" ]]; then
        fetch_range $month $last > $file.tmp &&
            mv $file.tmp $file || { rm -f $file.tmp; echo "dump $repo $ym failed" >&2; exit 1; }
        sleep $interval
    fi
    month=$next
done
