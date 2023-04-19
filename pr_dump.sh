#!/bin/bash

years="2016 2017 2018 2019 2020 2021 2022 2023"
repos="sonic-buildimage"
months="01 02 03 04 05 06 07 08 09 10 11 12"
keys="additions,author,baseRefName,number,title,comments,mergedAt"
interval=2
debug="#"

delete_empty_file(){
	[ -n "$(find . -xtype f -name "*.json" -size -10)" ] && rm $(find . -xtype f -name "*.json" -size -10)
}

for year in $years
do
	echo year: $year
	for repo in $repos
	do
		echo "    " repo: $repo
		delete_empty_file
		[ -f $year/$repo.prs.json ] && continue
		eval $debug gh pr list -R sonic-net/$repo -L 10000 -s merged --json $keys -S "merged:$year-01-01..$year-12-31" | jq '.[] += {repo: "$repo"}' > $year/$repo.prs.json
		delete_empty_file
		[ -f $year/$repo.prs.json ] && sleep $interval && continue
		for month in $months
		do
			days=31
			[[ "$month" == "02" ]] && ([[ "$year" == "2016" ]] || [[ "$year" == "2020" ]]) && days=29
			[[ "$month" == "02" ]] && ([[ "$year" != "2016" ]] && [[ "$year" != "2020" ]]) && days=28
			[[ "$month" == "04" ]] || [[ "$month" == "06" ]] || [[ "$month" == "09" ]] || [[ "$month" == "11" ]] && days=30
			echo "        " $month $days
			[ -f $year/$repo.$month.prs.json ] && continue
			eval $debug gh pr list -R sonic-net/$repo -L 10000 -s merged --json $keys -S "merged:$year-$month-01..$year-$month-$days" | jq '.[] += {repo: "$repo"}' > $year/$repo.$month.prs.json
			delete_empty_file
			sleep $interval && continue
		done	
	done
done
