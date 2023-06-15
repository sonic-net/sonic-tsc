Script to dump infomation from github.
Dumped data.

data status:
| item | data file|
|--|--|
| Merged HLD [1] Count | sii_hld/*.csv |
| Merged PR [2] Count (S/M/L) | sii_pr_review/**/*.prs.json |
| PR Review Count (S/M/L) | sii_pr_review/**/*.reviews.json |
| PR cherry-picking [3] Count | NA |
| Documentations (Release Notes/Meeting Minutes) | sii_hld/*.csv |
| New ASIC [4] Introduction Count | NA |
| Issues Opened Count | sii_issue/issues.json |
| Issues Triaged/Fixed Count | sii_issue/issues.json |
| Merged SONiC MGMT TEST Plan HLD [1] Count | sii_testplan_hld/sonic-mgmt_hld.csv |
| Merged Test cases [2] (S/M/L) | sii_test_pr_review(working) |
| TEST PR review count (S/M/L) | sii_test_pr_review(working) |
| Summit Presentation Count | NA |
| Hackathon Participation Team Count | NA |
| SONiC Production Deployment (S/M/L) [6] | NA |
| SONiC End Consumer Proliferation (S/M/L) | NA |

caculate script:
./sii_caculate.py person
./sii_caculate.py

[Sii scores by org:](Sii_org.csv)

|Organization|Score                      |
| :-- | --: |
|Microsoft|96489.95|
|Nvidia|32092.00|
|Others|17671.65|
|Broadcom|9103.95|
|Dell|6435.85|
|Intel|2569.75|
|Cisco|1404.20|
|Nokia|1338.30|
|Google|1185.65|
|Tencent|991.50|
|Alibaba|877.95|
|Linkedin|875.70|
|EdgeCore|857.10|
|plvision|792.15|
|Uber|754.40|
|Bayer|734.80|
|Ragile|725.55|
|Marvell|715.05|
|Juniper|711.05|
|airbnb|618.10|
|Centec|445.15|
|accton|397.25|
|Keysight|239.65|
|Ruijie|205.15|
|opennetworkingfoundation|182.10|
|Celestica|155.75|
|xFlowResearch|153.30|
|Orange|99.90|
|Jabil|92.50|
|asterfusion|86.90|
|netberg|79.60|
|Max-Planck-Institut|78.95|
|ufispace|71.30|
|cai|70.75|
|fungibleinc|66.00|
|docker|60.80|
|ingrasys|52.00|
|aviatrix|44.70|
|criteo|41.30|
|pegatroncorp|38.20|
|JD|29.00|
|inventec|25.80|
|ntt|25.40|
|cloudlight|18.00|
|Baidu|17.00|
|InternetInitiativeJapan|16.25|
|inspur|10.00|
|xnetworks|8.00|
|GenesisCloud|7.25|
|AvizNetworks|7.20|
|ibm|6.25|
|arcanebyte|6.00|
|n/a|5.00|
|arm|4.75|
|eBay|4.50|
|self|4.50|
|tw|4.30|
|thelinuxfoundation|3.30|
|Teraspek|3.25|
|standardair&lite|3.00|
|aussieserverhosts|3.00|
|vertiv|2.50|
|USnistgov|2.50|
|Tutao|2.50|
|teta-co.ir|2.50|
|@redpill-linpro|2.00|
|tuilmenau|2.00|
|mirantis|2.00|
|globallogic|2.00|
|wtmicroelectronics|2.00|
|sap|1.80|
|VMware|1.80|
|@vinted|1.50|
|@bisdn|1.50|
|x-cellenttechnologiesgmbh|1.50|
|purepeople|1.50|
|china|1.50|
|@rbccps-iisc@dreamlabin|1.50|
|H3C|1.50|
|wwt|1.50|
|fungible|1.50|
|pensnado|1.25|
|ymcag|1.25|
|buaa|1.25|
|universityofedinburgh|1.25|
|TexasA&MUniversity|1.00|
|Canonical|1.00|
|terrahostas|1.00|
|texasa&muniversity|1.00|
|crashcourse|1.00|
|redmudvillage|1.00|
|sonm|0.75|
|Oracle|0.60|
|dunstanassociates|0.60|
|duiadnsco|0.60|
|none|0.50|
|replicatedinc.|0.40|
|firstmode|0.40|
|Ordnance|0.20|
|www.volansys.com|0.20|
