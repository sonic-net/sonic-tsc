#!/bin/python3

import sys
import os
import json
import random

# key: lower charactor. value: print format
org_map = {
    'dell':         'Dell',
    'microsoft':    'Microsoft',
    "msft":         "Microsoft",
    'cisco':        'Cisco',
    'broadcom':     'Broadcom',
    'brcm':         'Broadcom',
    'arista':       'Broadcom',
    'intel':        'Intel',
    'barefoot':     'Intel',
    'centec':       'Centec',
    'celestica':    'Celestica',
    'edgecore':     'EdgeCore',
    'edge-core':    'EdgeCore',
    'marvell':      'Marvell',
    'cavium':       'Marvell',
    'innovium':     'Marvell',
    'nvidia':       'Nvidia',
    'mellanox':     'Nvidia',
    'mlnx':         'Nvidia',
    'alibaba':      'Alibaba',
    'uber':         'Uber',
    'nokia':        'Nokia',
    'juniper':      'Juniper',
    'google':       'Google',
    'ruijie':       'Ruijie',
    'linkedin':     'Linkedin',
    'keysight':     'Keysight',
    'tencent':      'Tencent',
    'jabil':        'Jabil',
    "ragile":       'Ragile',
    'ebay':         'eBay',
    'vmware':       'VMware',
    'genesiscloud': 'GenesisCloud',
    'usnistgov':    'USnistgov',
    'tutao':        'Tutao',
    'wwt':          'wwt',
    'canonical':    'Canonical',
    'ordnance':     'Ordnance',
    'h3c':          'H3C',
    'jd':           'JD',
    'bayer':        'Bayer',
    'baidu':        'Baidu',
    'oracle':       'Oracle',
    'teraspek':     'Teraspek',
    'tamu-edu':     'Texas A&M University',
    'orange':       'Orange',
    'null':         'Others',
    'aviz networks':'Aviz Networks',
    'xflow research':           'xFlow Research',
    'max-planck-institut':      'Max-Planck-Institut',
    'internet initiative japan':'Internet Initiative Japan',
}

automation_account = ['microsoft-github-policy-service', 'linux-foundation-easycla','lgtm-com','mssonicbld','azure-pipelines','svc-acs','msftclas']
repo_name = 'sonic-contributor-map/'
clone_cmd = 'git clone https://github.com/sonic-net/sonic-contributor-map'
update_cmd = 'cd sonic-contributor-map; git reset HEAD --hard; git checkout main; git pull'

year_weight = {
#    '2023': 0.3,
    '2022': 0.3,
    '2021': 0.25,
    '2020': 0.2,
    '2019': 0.15,
    '2018': 0.1,
}

prs_map = {} 
reviews_map = {}
author_org = {}

def sii_caculate():
    ret = {}
    person = False
    if len(sys.argv) > 1 and sys.argv[1].find('person') > -1:
        person = True

    issue_score, issue_triage_score = caculate_issue(person)
    print('issue score:')
    print(json.dumps(round_floats(issue_score)))
    print('issue triage score:')
    print(json.dumps(round_floats(issue_triage_score)))

    pr_score,test_pr_score = caculate_pr(person)
    print('pr score:')
    print(json.dumps(round_floats(pr_score)))

    print('test pr score:')
    print(json.dumps(round_floats(test_pr_score)))

    pr_review_score,test_pr_review_score = caculate_review(person)
    print('pr review score:')
    print(json.dumps(round_floats(pr_review_score)))

    print('test pr review score:')
    print(json.dumps(round_floats(test_pr_review_score)))

    hld_doc_score,testplan_hld_score = caculate_hld(person)
    print('hld&doc score:')
    print(json.dumps(round_floats(hld_doc_score)))

    print('test plan hld score:')
    print(json.dumps(round_floats(testplan_hld_score)))

    input_score = caculate_input()
    print('input score:')
    print(json.dumps(round_floats(input_score)))

    if not person:
        print('Organization,Score', file=open('sii_org.csv', 'w'))
        summ = summ_org_scores( issue_score,issue_triage_score,pr_score,test_pr_score,pr_review_score,test_pr_review_score,hld_doc_score,testplan_hld_score,input_score)
        for i in sorted(summ.items(), key=lambda x: (-x[1], x[0])):
            print('%s,%.2f' % i, file=open('sii_org.csv', 'a'))
    else:
        summ = summ_org_scores( issue_score,pr_score,test_pr_score,pr_review_score,test_pr_review_score,hld_doc_score,testplan_hld_score )
        print('Author,Organization,Score', file=open('sii_author.csv', 'w'))
        for i in sorted(summ.items(), key=lambda x: (-x[1], x[0])):
            if i[0] not in author_org:
                org = 'Others'
            else:
                org = author_org[i[0]]
            print('{},{},'.format(i[0], org) + "%.2f" % i[1], file=open('sii_author.csv', 'a'))


#    Sii 4,6,12,13,14,15
#    TODO
# 4  PR cherry-picking [3] Count


#   Sii 6,12,13,14,15
# 6  New ASIC [4] Introduction Count
# 12 Summit Presentation Count
# 13 Hackathon Participation Team Count
# 14 SONiC Production Deployment (S/M/L) [6]
# 15 SONiC End Consumer Proliferation (S/M/L)
def caculate_input():
    ret = {}
    paths = ['development_new_asic_introduction.json', 'innovation_hackathon_participation_team_count.json', 'innovation_summit_presentation_count.json', 'proliferation_sonic_end_consumer_proliferation.json', 'proliferation_sonic_production_deployment.json']

    for path in paths:
        file = repo_name + path
        with open(file) as f:
            content = f.read()
        content_json = json.loads(content)
        for record in content_json:
            record = {k.lower(): v for k, v in record.items()}
            key_count = 0
            year = str(record['year'])
            count = record['count']
            org = record['organization']
            if year not in year_weight.keys():
                continue

            score = 0
            if path == 'development_new_asic_introduction.json':
                score = 100 * count
            if path == 'innovation_summit_presentation_count.json':
                score = 10 * count
            if path == 'innovation_hackathon_participation_team_count.json':
                score = 50 * count
            if path == 'proliferation_sonic_production_deployment.json':
                if count >= 100:
                    score = 100
                if count >= 501:
                    score = 500
                if count >= 50001:
                    score = 1000
            if path == 'proliferation_sonic_end_consumer_proliferation.json':
                if count >= 100:
                    score = 5
                if count >= 501:
                    score = 50
                if count >= 50001:
                    score = 100
            score = score * year_weight[year]
            if org not in ret:
                ret[org] = 0
            ret[org] += score
    return ret


#   Sii 1,5,9
# 1 Merged HLD [1] Count
# 5 Documentations (Release Notes/Meeting Minutes)
# 9 Merged SONiC MGMT TEST Plan HLD [1] Count
def caculate_hld(byperson=False):
    ret = {}
    ret_testplan = {}
    paths = ['sii_hld/', 'sii_testplan_hld/']
    for path in paths:
        files = os.listdir(path)
        for file in files:
            if not file.endswith('.csv'):
                continue
            with open(path + file) as f:
                content = f.read()
            for line in content.split('\n'):
                if line:
                    author = line.split(',')[2]
                    timestamp = line.split(',')[3]
                    year = timestamp.split('-')[0]
                    if author in automation_account:
                        continue
                    if year not in year_weight:
                        continue
                    if path == 'sii_hld/':
                        score = 50
                        if author not in ret:
                            ret[author] = 0
                        ret[author] += score * year_weight[year]
                    else:
                        score = 100
                        if author not in ret_testplan:
                            ret_testplan[author] = 0
                        ret_testplan[author] += score * year_weight[year]

    if byperson:
        return ret,ret_testplan
    return summ_by_org(ret), summ_by_org(ret_testplan)

#   Sii 3,11
# 3  PR Review Count (S/M/L)
# 11 TEST PR review count (S/M/L)
def caculate_review(byperson=False):
    ret = {}
    ret_test = {}
    for repo_number_author, detail in reviews_map.items():
        repo = repo_number_author.split(',')[0]
        number = repo_number_author.split(',')[1]
        author = repo_number_author.split(',')[2]
        year = detail['year']
        test = detail['test']
        count = detail['count']
        if author in automation_account:
            continue
        if year not in year_weight:
            continue
        if count <= 2:
            score = 1
        elif count <=4:
            score = 2
        else:
            score =5
        if test:
            if author not in ret_test:
                ret_test[author] = 0
            ret_test[author] += score * year_weight[year]
        else:
            if author not in ret:
                ret[author] = 0
            ret[author] += 2 * score * year_weight[year]

    if byperson:
        return ret,ret_test
    return summ_by_org(ret),summ_by_org(ret_test)
    

#   Sii 2,10
# 2  Merged PR [2] Count (S/M/L)
# 10 Merged Test cases [2] (S/M/L)
def caculate_pr(byperson=False):
    ret = {}
    ret_test = {}
    for repo_number, detail in prs_map.items():
        repo = repo_number.split(',')[0]
        number = repo_number.split(',')[1]
        test = detail['test']
        additions = detail['additions']
        year = detail['year']
        author = detail['author']
        if author in automation_account:
            continue
        if additions <= 50:
            score = 10
        elif additions <=300:
            score = 20
        else:
            score = 50 + int((additions-300)/100)

        if test:
            if author not in ret_test:
                ret_test[author] = 0
            ret_test[author] += score * year_weight[year]
        else:
            if author not in ret:
                ret[author] = 0
            ret[author] += 2 * score * year_weight[year]

    if byperson:
        return ret,ret_test
    return summ_by_org(ret),summ_by_org(ret_test)



#   Sii 7,8
# 7 Issues Opened Count
# 8 Issues Triaged/Fixed Count
def caculate_issue(byperson=False):
    issue_file = 'sii_issue/issues.json'
    # format:
    # open issue:   ret.person.${author} += 5 * index
    # triage issue: ret.organization.${org} += 10 * index
    ret_issue = {}
    ret_issue_t = {}
    with open(issue_file) as f:
        content = f.read()

    issues = json.loads(content)
    for issue in issues:
        year = issue['createdAt'].split('-')[0]
        author = issue['author']
        labels = issue['labels'].split(',')
        if author in automation_account:
            continue
        # if github account deleted, it is ''
        if author == '':
            continue
        if year not in year_weight:
            continue
        if author not in ret_issue:
            # init ret.person.${author}
            ret_issue[author] = 0
        # SII for opening issue
        ret_issue[author] += 5 * year_weight[year]

        # SII for issue triage
        for label in issue['labels'].split(','):
            if label.lower() in org_map:
                Label = org_map[label.lower()]
                if Label not in ret_issue_t:
                    ret_issue_t[Label] = 0
                ret_issue_t[Label] += 10 * year_weight[year]

    if byperson:
        return ret_issue, ret_issue_t
    return summ_by_org(ret_issue), ret_issue_t


def init():
    ret = {}
    if os.path.isdir(repo_name):
        os.system(update_cmd)
    else:
        os.system(clone_cmd)

    author_org_load()

    pr_review_load() 
    print()
    print('author count:', len(author_org))
    print(random.choice(list(author_org.items())))
    print('pr count:' ,len(prs_map))
    print(random.choice(list(prs_map.items())))
    print('review count:', len(reviews_map))
    print(random.choice(list(reviews_map.items())))


def author_org_load():
    global author_org
    with open('sii_author_map/author.csv') as f:
        content = f.read()
    for line in content.split('\n'):
        if line:
            author = line.split(',')[0]
            org = line.split(',')[2].lower()
            for org_official in org_map.keys():
                if org_official in org:
                    author_org[author] = org_map[org_official]
                    break
            if author not in author_org:
                author_org[author] = org
    with open ('sonic-contributor-map/contributors.json') as f:
        content = f.read()
        contributors_list = json.loads(content)
    for contributor in contributors_list:
        contributor = {k.lower(): v for k, v in contributor.items()}
        author_org[contributor['id']] = contributor['organization']


def summ_org_scores(*args):
    ret = {}
    for arg in args:
        for org,score in arg.items():
            if org not in ret:
                ret[org] = 0
            ret[org] += score
    return ret


def summ_by_org(*args):
    ret = {}
    for arg in args:
        for author,score in arg.items():
            if author in automation_account:
                continue
            if author in author_org:
                org = author_org[author]
            else:
                org = 'Others'

            if org not in ret:
                ret[org] = 0

            ret[org] += score
    return ret


def round_floats(o):
    if isinstance(o, float): return round(o, 2)
    if isinstance(o, dict): return {k: round_floats(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [round_floats(x) for x in o]
    return o


def parse_author(map,key='author'):
    if 'login' in map[key]:
        return map[key]['login']
    else:
        return map[key]


def pr_review_load():
    global prs_map, reviews_map
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
                    test = False
                    if 'testCase' in pr and pr['testCase'] == 'yes':
                        test = True
                    year_ = pr['mergedAt'].split('-')[0]
                    repo = pr['repo']
                    number = pr['number']
                    additions = pr['additions']
                    author = parse_author(pr)
                    if author in automation_account:
                        continue
                    prs_map[ repo + ',' + str(number) ] = {'year': year_,'author': author,'test': test, 'additions': additions}

    for year in year_weight:
        paths = ['sii_pr_review/', 'sii_test_pr_review/']
        for path in paths:
            pr_path = path + str(year)
            files = os.listdir(pr_path)
            for file in files:
                if not file.endswith('reviews.json'):
                    continue
                with open(pr_path + '/' + file) as f:
                    content = f.read()
                reviews = json.loads(content)
                for review in reviews:
                    number = review['number']
                    repo = review['repo']
                    if 'comment_at' in review:
                        year_ = review['comment_at'].split('-')[0]
                        author = parse_author(review, 'comment_author')
                    elif 'review_at' in review:
                        if review['review_at'] == None:
                            print('bad case:', review)
                            continue
                        year_ = review['review_at'].split('-')[0]
                        author = parse_author(review, 'review_author')
                    else:
                        year_ = review['latestReview_at'].split('-')[0]
                        author = parse_author(review, 'latestReview_author')
                    if author in automation_account:
                        continue
                    # TODO some data need to dump!!!
                    if repo + ',' + str(number) not in prs_map:
                        continue
                    if author == prs_map[ repo + ',' + str(number) ]['author']:
                        continue
                    test = prs_map[ repo + ',' + str(number) ]['test']
                    # Use review count to judge S/M/L
                    if repo + ',' + str(number) + ',' + author not in reviews_map:
                        reviews_map[ repo + ',' + str(number) + ',' + author ] = {'year': year_, 'test': test, 'count': 0 }
                    reviews_map[ repo + ',' + str(number) + ',' + author ]['count'] += 1


if __name__ == '__main__':
    init()
    sii_caculate()


