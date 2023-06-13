#!/bin/python3

import sys
import os
import json

# key: lower charactor. value: print format
org_map = {
    "dell":         "Dell",
    "microsoft":    "Microsoft",
    "msft":         "Microsoft",
    "cisco":        "Cisco",
    "broadcom":     "Broadcom",
    "brcm":         "Broadcom",
    "arista":       "Broadcom",
    "intel":        "Intel",
    "barefoot":     "Intel",
    "centec":       "Centec",
    "celestica":    "Celestica",
    "edgecore":     "EdgeCore",
    "edge-core":    "EdgeCore",
    "marvell":      "Marvell",
    "cavium":       "Marvell",
    "nvidia":       "Nvidia",
    "mellanox":     "Nvidia",
    "mlnx":         "Nvidia",
    "alibaba":      "Alibaba",
    "uber":         "Uber",
    "nokia":        "Nokia",
    "juniper":      "Juniper",
    "google":       "Google",
    "ruijie":       "Ruijie",
    "linkedin":     "Linkedin",
    "keysight":     "Keysight",
    "tencent":      "Tencent",
    "jabil":        "Jabil",
    "ragile":       "Ragile",
    "ebay":         "eBay",
    "vmware":       "VMware",
    "genesiscloud": "GenesisCloud",
    "usnistgov":    "USnistgov",
    "tutao":        "Tutao",
    "wwt":          "wwt",
    "canonical":    "Canonical",
    "ordnance":     "Ordnance",
    "h3c":          "H3C",
    "jd":           "JD",
    "bayer":        "Bayer",
    "baidu":        "Baidu",
    "oracle":       "Oracle",
    "teraspek":     "Teraspek",
    "tamu-edu":     "Texas A&M University",
    "orange":       "Orange",
    "null":         "Others",
    "aviz networks":"Aviz Networks",
    "xflow research":           "xFlow Research",
    "max-planck-institut":      "Max-Planck-Institut",
    "internet initiative japan":"Internet Initiative Japan",
}

automation_account = ['linux-foundation-easycla','lgtm-com','mssonicbld','azure-pipelines','svc-acs','msftclas']

year_weight = {
#    "2023": 0.3,
    "2022": 0.3,
    "2021": 0.25,
    "2020": 0.2,
    "2019": 0.15,
    "2018": 0.1,
}

def sii_caculate():
    ret = {}
    person = False
    if len(sys.argv) > 1 and sys.argv[1].find("person") > -1:
        person = True

    issue_score = caculate_issue(person)
    pr_score = caculate_pr()

    print(json.dumps(pr_score))


def author2org():
    ret = {}
    with open('sii_author_map/author.csv') as f:
        content = f.read()
    for line in content.split('\n'):
        if line:
            author = line.split(',')[0]
            org = line.split(',')[2].lower()
            for org_official in org_map.keys():
                if org_official in org:
                    ret[author] = org_map[org_official]
                    break
            if author not in ret:
                ret[author] = org
    return ret


author_org = author2org()

def summ_by_org(author_score):
    ret = {}
    for author,score in author_score.items():
        if author in automation_account:
            continue
        if author in author_org:
            org = author_org[author]
        else:
            org = "Others"

        if org not in ret:
            ret[org] = 0

        ret[org] += score
    return ret

def caculate_review()

# Sii 2
def caculate_pr(byperson=False):
    ret = {'person': {}, 'org': {}}
    for year in year_weight:
        paths = ['sii_pr_review/', 'sii_test_pr_review/']
        for path in paths:
            pr_path = path + str(year)
            files = os.listdir(pr_path)
            for file in files:
                if not file.endswith('prs.json'):
                    continue
                with open(pr_path + '/' + file) as f:
                    content = f.read()
                prs = json.loads(content)
                for pr in prs:
                    if "testCase" in pr and pr["testCase"] == "yes":
                        continue
                    year = pr["mergedAt"].split('-')[0]
                    author = pr["author"]
                    additions = pr["additions"]
                    if author not in ret['person']:
                        ret['person'][author] = 0
                    if additions <= 50:
                        score = 10
                    elif additions <=300:
                        score = 20
                    else:
                        score = 50 + int((additions-300)/100)
                    ret['person'][author] += score * year_weight[year]

    if byperson:
        return ret['person']

    return summ_by_org(ret['person'])


# Sii 7,8
def caculate_issue(byperson=False):
    issue_file = 'sii_issue/issues.json'
    # format:
    # open issue:   ret.person.${author} += 5 * index
    # triage issue: ret.organization.${org} += 10 * index
    ret = {'person': {}, 'organization': {}}
    with open(issue_file) as f:
        content = f.read()

    issues = json.loads(content)
    for issue in issues:
        year = issue['createdAt'].split('-')[0]
        author = issue['author']
        labels = issue['labels'].split(',')
        # if github account deleted, it is ''
        if author == '':
            continue
        if year not in year_weight:
            continue
        if author not in ret['person']:
            # init ret.person.${author}
            ret['person'][author] = 0
        # SII for opening issue
        ret['person'][author] += 5 * year_weight[year]
        # SII for issue triage
        for label in issue['labels'].split(','):
            if label.lower() in org_map:
                Label = org_map[label.lower()]
                if Label not in ret['organization']:
                    ret['organization'][Label] = 0
                ret['organization'][Label] += 10 * year_weight[year]

    if byperson:
        return ret['person']

    return summ_by_org(ret['person'])


if __name__ == '__main__':
    sii_caculate()


