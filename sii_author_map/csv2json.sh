#!/bin/bash -ex

s_file=$1
[ -z "$s_file" ] && s_file=author.csv
t_file=$(echo $s_file | sed 's/csv/json/')

echo [ > $t_file.tmp
cat $s_file | awk -F, '{print"{\"Id\": \""$1"\",\"Name\": \""$2"\",\"Organization\": \""$3"\"},"}' >> $t_file.tmp
sed -i '$ s/,$//g' $t_file.tmp
echo ] >> $t_file.tmp
cat $t_file.tmp | jq --indent 4 > tmp
mv tmp $t_file
