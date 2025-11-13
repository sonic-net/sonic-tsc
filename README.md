# Sonic TSC support repo

### 1. This repo stores SII score. We use the variable year as current year.

- SII score in range [year-5, year-1]
  - [Scores by Org](sii_org.csv)
  - [Scores by author](sii_author.csv)
- SII score in range [year-4, year]
  - [Predict Scores by Org](sii_org_predict.csv)
  - [Predict Scores by author](sii_author_predict.csv)

## 2. Pipeline to dump raw data.
- Pipeline: [sonic-net.sonic-tsc.dump.data](https://dev.azure.com/mssonic/build/_build?definitionId=1374)
- Pipeline definition: [dump_data.yml](dump_data.yml)

## 3. Pipeline to refresh SII scores.
- Pipeline:  [sonic-net.sii.update](https://dev.azure.com/mssonic/build/_build?definitionId=1074&_a=summary)
- Pipeline definition:  [azure-pipeline.yml](azure-pipeline.yml)

## 4. This repo stores raw data to calculate SII scores and data dump script.

- [High Level Design](sii_hld)
- [Contributor Organization Map](https://github.com/sonic-net/sonic-contributor-map/blob/main/contributors.json)
- [Issue related data](sii_issue)
- [Normal PRs and Reviews](sii_pr_review)
- [Test case related PRs and Reviews](sii_test_pr_review)
- [TestPlan related HLD](sii_testplan_hld)

## 5. SII Weight Multiplier: [Original Link](https://github.com/sonic-net/SONiC/blob/master/tsc/TSC_Election.md)

| Contribution (Yearly) | Category | Weight Multiplier |
|--------------------------------  |----------| -------- |
| Merged HLD [1] Count              | Development | 50 |
| Merged PR [2] Count (S/M/L)       | Development | 10/20/ (50 + 1 per 100 LoC above 300)|
| PR Review Count (S/M/L)       | Development | 1/2/5    |
| PR cherry-picking [3] Count       | Development |  5 |
| Documentations (Release Notes/Meeting Minutes) | Development |  50/1  |
| New ASIC [4] Introduction Count | Development |  100 |
| Issues Opened Count               |  Quality [5] | 5 |
| Issues Triaged/Fixed Count        | Quality | 10 |
| Merged SONiC MGMT TEST Plan HLD [1] Count | Quality | 100 |
| Merged Test cases [2] (S/M/L)        | Quality | 20/40/100|
| TEST PR review count (S/M/L)     | Quality | 2/4/10 |
| Summit Presentation Count       | Innovation | 50  |
| Hackathon Participation Team Count | Innovation | 10 |
| SONiC Production Deployment (S/M/L) [6] | Proliferation | 100/500/1000 |
| SONiC End Consumer Proliferation (S/M/L) | Proliferation [7] | 5/50/100 |


## 6. Raw Data store path and data dump script
Author Organization Map:
>   Author Organization Map: [contributors.json](https://github.com/sonic-net/sonic-contributor-map/blob/main/contributors.json)
>     - ***NOTE***: Do not use the legacy [authors.csv](sii_author_map/authors.csv) / [authors.list](sii_author_map/authors.list)


Three HLD file data:
>   dash HLD: [dash HLD](sii_hld/dash_hld.csv)
>
>   sai HLD: [sai HLD](sii_hld/sai_hld.csv)
>
>   sonic HLD: [sonic HLD](sii_hld/sonic_hld.csv)
>
>   dump script: [dump_hld_data.sh](sii_hld/dash_hld.csv)


SONiC issue data:
>   issue data path: [issue](sii_issue/issues.json)
>
>   dump script: [sii_issue/issues_dump.sh](sii_issue/issues_dump.sh)

SONiC PR and Review data:
>   prs: sii_pr_review/**/*.prs.json
>
>   review: sii_pr_review/**/*.reviews.json
>
>   dump script: [sii_pr_review/pr_dump.sh](sii_pr_review/pr_dump.sh)


SONiC test related PR and Review data:
>   prs: sii_test_pr_review/**/*.prs.json
>
>   review: sii_test_pr_review/**/*.reviews.json
>
>   dump script: [sii_test_pr_review/pr_dump.sh](sii_test_pr_review/pr_dump.sh)

SONiC testplan HLD data:
>   test plan HLD: [test plan HLD](sii_testplan_hld/sonic-mgmt_hld.csv)
>
>   dump script: [sii_testplan_hld/generate_testplan_hld_data.sh](sii_testplan_hld/generate_testplan_hld_data.sh)

