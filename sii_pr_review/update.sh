rm -rf $(find . -name $(date +%Y))

cat repos | xargs -i ./pr_dump.sh -r {} -y $(date +%Y) -m | tee log.log

cat repos | xargs -i ./pr_dump.sh -r {} -y $(date +%Y) -m -t reviews | tee log.log
