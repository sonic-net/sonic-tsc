#!/bin/bash
# Generate per-repo CODEOWNERS-style data using sonic-pipelines/scripts/code-owners.

repos=$(grep -v "^\s*#" "$(dirname "$0")/repos" | grep -v "^\s*$")
tool_dir=""
max_owners=1000
half_life_days=180
min_score=0.5
min_raw=50
use_reviews=1

help(){
    echo "Use:"
    echo "    -r    # repo list (space separated), default: enabled entries in the 'repos' file"
    echo "    -t    # path to sonic-pipelines/scripts/code-owners, default: clone it"
    echo "    -m    # max owners per folder, default $max_owners (keep all contributors for approver qualification)"
    echo "    -l    # recency half-life in days, default $half_life_days (0 disables)"
    echo "    -s    # drop owners with final score below this, default $min_score (0 keeps all)"
    echo "    -w    # drop owners with raw decayed change weight below this, default $min_raw (0 ignores)"
    echo "    -R    # skip approval history (change score only)"
    echo "Set GITHUB_API_TOKENS (comma separated) to avoid API rate limits."
}

while [[ $# > 0 ]]
do
    case "$1" in
        -r) repos=$2; shift ;;
        -t) tool_dir=$2; shift ;;
        -m) max_owners=$2; shift ;;
        -l) half_life_days=$2; shift ;;
        -s) min_score=$2; shift ;;
        -w) min_raw=$2; shift ;;
        -R) use_reviews=0 ;;
        *) help; exit 1 ;;
    esac
    shift
done

base=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
trap 'rm -rf $work' EXIT

if [ -z "$tool_dir" ]; then
    git clone --depth 1 https://github.com/yijingyan2/sonic-pipelines $work/sonic-pipelines
    tool_dir=$work/sonic-pipelines/scripts/code-owners
fi

if command -v uv >/dev/null; then
    uv venv -q $work/venv && uv pip install -q -p $work/venv/bin/python "$tool_dir" || exit 1
else
    python3 -m venv $work/venv && $work/venv/bin/pip install -q "$tool_dir" || exit 1
fi

run_codeowners(){
    local output=$1
    shift
    local attempt=1
    local max_attempts=4
    local delay=15

    while ! $work/venv/bin/codeowners-cli "$@" > "$output"; do
        if [ $attempt -ge $max_attempts ]; then
            return 1
        fi
        echo "codeowners-cli attempt $attempt failed; retrying in ${delay}s" >&2
        sleep $delay
        attempt=$((attempt + 1))
        delay=$((delay * 2))
    done
}

for repo in $repos
do
    name=$(echo $repo | awk -F/ '{print$2}')
    out=$base/$name
    mkdir -p $out
    # Full history is required to count contributions.
    git clone -q https://github.com/$repo $work/$name || { echo "clone $repo failed"; continue; }

    args=(--repo $work/$name --contributors_file $out/contributors.yaml --max_owners $max_owners --full_tree --half_life_days $half_life_days)
    [ -f $out/folder_presets.yaml ] && args+=(--folder_presets_file $out/folder_presets.yaml)

    # New contributors default to available_to_review: false. On the first run for
    # a repo, enable every resolved GitHub user, then rerun; later edits are kept.
    if [ ! -f $out/contributors.yaml ]; then
        run_codeowners /dev/null "${args[@]}" || { echo "codeowners-cli failed for $repo"; rm -rf $work/$name; continue; }
        $work/venv/bin/python - $out/contributors.yaml <<'PY'
import sys, yaml
path = sys.argv[1]
data = yaml.safe_load(open(path)) or []
for c in data:
    if c.get("github_id", -1) > 0:
        c["available_to_review"] = True
yaml.safe_dump(data, open(path, "w"), allow_unicode=True)
PY
    fi

    # raw_change_weights.yml: decayed changed lines; raw_review_weights.yml: decayed approval counts;
    # pr_reviewer-by-files.yml: 0.6 * change score + 0.4 * approval score, each weight / top weight in the folder (0-1);
    # owners below min_score or min_raw are dropped from pr_reviewer-by-files.yml only (raw files keep everyone)
    norm_args=(--normalize max --min_score $min_score --min_raw_change_weight $min_raw)
    if [ "$use_reviews" = 1 ]; then
        "$(dirname "$0")/dump_reviews.sh" -r $repo -o $work/$name.reviews || echo "review dump failed for $repo"
        [ -d $work/$name.reviews ] && norm_args+=(--reviews_file $work/$name.reviews --reviews_out $work/$name.rv.yaml)
    fi
    if run_codeowners $work/$name.raw.yaml "${args[@]}" &&
       run_codeowners $work/$name.yaml "${args[@]}" "${norm_args[@]}"; then
        mv $work/$name.raw.yaml $out/raw_change_weights.yml
        mv $work/$name.yaml $out/pr_reviewer-by-files.yml
        [ -f $work/$name.rv.yaml ] && mv $work/$name.rv.yaml $out/raw_review_weights.yml
    else
        echo "codeowners-cli failed for $repo"
    fi
    rm -rf $work/$name
done
