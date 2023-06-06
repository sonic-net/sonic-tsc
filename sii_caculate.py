#!/bin/python3

import sys
import json

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
    "xflow research":           "xFlow Research",
    "max-planck-institut":      "Max-Planck-Institut",
    "internet initiative japan":"Internet Initiative Japan",
}

automation_account = ['linux-foundation-easycla','lgtm-com','mssonicbld','azure-pipelines','svc-acs','msftclas']

score_map = {
    "2023": 0.3,
    "2022": 0.3,
    "2021": 0.25,
    "2020": 0.2,
    "2019": 0.15,
    "2018": 0.1,
}

def sii_org():
    ret = {}
    author_org = author2org()

    score_author = {}
    score_org = {}
    issue_score = caculate_issue()

    print(issue_score)
        

def sii_person():
    print("sii person")


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


def caculate_issue():
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
        if year not in score_map:
            continue
        if author not in ret['person']:
            # init ret.person.${author}
            ret['person'][author] = 0
        # SII for opening issue
        ret['person'][author] += 5 * score_map[year]
        # SII for issue triage
        for label in issue['labels'].split(','):
            if label.lower() in org_map:
                Label = org_map[label.lower()]
                if Label not in ret['organization']:
                    ret['organization'][Label] = 0
                ret['organization'][Label] += 10 * score_map[year]

    ret1 = {}
    for author,score in issue_score['person'].items():
        if author in automation_account:
            continue 
        if author in author_org:
            org = author_org[author]
        else:
            print(author + " org not found!!!")
            exit(1)
        if org not in ret1:
            ret1[org] = 0
        ret1[org] += score

    return ret1

def caculate_pr():
    print()


if __name__ == '__main__':
    if sys.argv[1] == "sii_org":
        sii_org()
    if sys.argv[1] == "sii_person":
        sii_person()
