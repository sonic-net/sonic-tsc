# Script to dump infomation from github.

## TSC doc:
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

## Data store folder
[author organization map](sii_author_map/author.csv)
Three HLD file path:
[dash HLD](sii_hld/dash_hld.csv)

caculate script:
./sii_caculate.py person
./sii_caculate.py

[Sii scores by each org](Sii_org.csv)

[Sii scores by each author](Sii_author.csv)
