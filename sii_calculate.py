#!/bin/python3

import sys
import os
import json
import random
from datetime import datetime,timedelta

# key: lower charactor. value: print format
org_map = {
    'dell':          'Dell',
    'dell technologies': 'Dell',
    'microsoft':     'Microsoft',
    "msft":          'Microsoft',
    'cisco':         'Cisco',
    'broadcom':      'Broadcom',
    'brcm':          'Broadcom',
    'arista':        'Arista',
    'aristanetworks':'Arista',
    'intel':         'Intel',
    'barefoot':      'Intel',
    'centec':        'Centec',
    'celestica':     'Celestica',
    'edgecore':      'EdgeCore',
    'edge-core':     'EdgeCore',
    'marvell':       'Marvell',
    'cavium':        'Marvell',
    'innovium':      'Marvell',
    'nvidia':        'Nvidia',
    'mellanox':      'Nvidia',
    'mlnx':          'Nvidia',
    'alibaba':       'Alibaba',
    'uber':          'Uber',
    'nokia':         'Nokia',
    'juniper':       'Juniper',
    'google':        'Google',
    'ruijie':        'Ruijie',
    'linkedin':      'Linkedin',
    'keysight':      'Keysight',
    'tencent':       'Tencent',
    'jabil':         'Jabil',
    "ragile":        'Ragile',
    'ebay':          'eBay',
    'vmware':        'VMware',
    'genesiscloud':  'GenesisCloud',
    'usnistgov':     'USnistgov',
    'tutao':         'Tutao',
    'wwt':           'wwt',
    'canonical':     'Canonical',
    'ordnance':      'Ordnance',
    'h3c':           'H3C',
    'jd':            'JD',
    'bayer':         'Bayer',
    'baidu':         'Baidu',
    'oracle':        'Oracle',
    'teraspek':      'Teraspek',
    'tamu-edu':      'Texas A&M University',
    'orange':        'Orange',
    'null':          'Others',
    'aviz networks': 'Aviz Networks',
    'xflow research':           'xFlow Research',
    'max-planck-institut':      'Max-Planck-Institut',
    'internet initiative japan':'Internet Initiative Japan',
}

automation_account = ['microsoft-github-policy-service', 'linux-foundation-easycla','lgtm-com','mssonicbld','azure-pipelines','svc-acs','msftclas']
repo_name = 'sonic-contributor-map/'
clone_cmd = 'git clone https://github.com/sonic-net/sonic-contributor-map'
update_cmd = 'cd sonic-contributor-map; git reset HEAD --hard; git checkout main; git pull'

year_weight = {
    str(datetime.now().year - 0): 0,
    str(datetime.now().year - 1): 0.3,
    str(datetime.now().year - 2): 0.25,
    str(datetime.now().year - 3): 0.2,
    str(datetime.now().year - 4): 0.15,
    str(datetime.now().year - 5): 0.1
}

year_weight_predict = {
    str(datetime.now().year - 0): 0.3,
    str(datetime.now().year - 1): 0.25,
    str(datetime.now().year - 2): 0.2,
    str(datetime.now().year - 3): 0.15,
    str(datetime.now().year - 4): 0.1,
    str(datetime.now().year - 5): 0
}

prs_map = {} 
prs_drop = {}
reviews_map = {}
author_org = {}
author_org_dup = {}

def sii_calculate(predict: False):
    ret = {}
    if predict:
        global year_weight,year_weight_predict
        year_weight = year_weight_predict
        org_output_file = 'sii_org_predict.csv'
        author_output_file = 'sii_author_predict.csv'
    else:
        org_output_file = 'sii_org.csv'
        author_output_file = 'sii_author.csv'

    issue_score, issue_triage_score = calculate_issue()
    print('issue score:')
    print(json.dumps(round_floats(summ_author_scores(issue_score))))
    print('issue triage score:')
    print(json.dumps(round_floats(issue_triage_score)))

    pr_score,test_pr_score = calculate_pr()
    print('pr score:')
    print(json.dumps(round_floats(summ_author_scores(pr_score))))

    print('test pr score:')
    print(json.dumps(round_floats(summ_author_scores(test_pr_score))))

    pr_review_score,test_pr_review_score = calculate_review()
    print('pr review score:')
    print(json.dumps(round_floats(summ_author_scores(pr_review_score))))

    print('test pr review score:')
    print(json.dumps(round_floats(summ_author_scores(test_pr_review_score))))

    hld_doc_score,testplan_hld_score = calculate_hld()
    print('hld&doc score:')
    print(json.dumps(round_floats(summ_author_scores(hld_doc_score))))

    print('test plan hld score:')
    print(json.dumps(round_floats(summ_author_scores(testplan_hld_score))))

    input_score = calculate_input()
    print('input score:')
    print(json.dumps(round_floats(input_score)))

    print('Organization,Score', file=open(org_output_file, 'w'))
    summ = summ_dict_scores( \
            summ_org_scores(issue_score), \
            issue_triage_score, \
            summ_org_scores(pr_score), \
            summ_org_scores(test_pr_score), \
            summ_org_scores(pr_review_score), \
            summ_org_scores(test_pr_review_score), \
            summ_org_scores(hld_doc_score), \
            summ_org_scores(testplan_hld_score), \
            input_score)
    for i in sorted(summ.items(), key=lambda x: (-x[1], x[0])):
        print('%s,%.2f' % i, file=open(org_output_file, 'a'))

    print('Author,Organization,Score', file=open(author_output_file, 'w'))

    summ = summ_dict_scores( \
            summ_author_scores(issue_score), \
            summ_author_scores(pr_score), \
            summ_author_scores(test_pr_score), \
            summ_author_scores(pr_review_score), \
            summ_author_scores(test_pr_review_score), \
            summ_author_scores(hld_doc_score), \
            summ_author_scores(testplan_hld_score))
    for i in sorted(summ.items(), key=lambda x: (-x[1], x[0])):
        author = i[0]
        if author not in author_org:
            org = 'Others'
        else:
            org = author_org[author]
        if '(' in author and ')' in author:
            org = author.split('(')[1][:-1]
            author = author.split('(')[0]

        print('{},{},'.format(author, org) + "%.2f" % i[1], file=open(author_output_file, 'a'))


#    Sii 4,6,12,13,14,15
#    TODO
# 4  PR cherry-picking [3] Count


#   Sii 6,12,13,14,15
# 6  New ASIC [4] Introduction Count
# 12 Summit Presentation Count
# 13 Hackathon Participation Team Count
# 14 SONiC Production Deployment (S/M/L) [6]
# 15 SONiC End Consumer Proliferation (S/M/L)
def calculate_input():
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
                score = 50 * count
            if path == 'innovation_hackathon_participation_team_count.json':
                score = 10 * count
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
def calculate_hld():
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
                    ts = datetime.strptime(line.split(',')[3], '%Y-%m-%dT%H:%M:%SZ')
                    year_m = ts.strftime("%Y%m")
                    year = year_m[:4]
                    if year not in year_weight:
                        continue
                    if path == 'sii_hld/':
                        score = 50
                        if year_m not in ret:
                            ret[year_m] = {}
                        if author not in ret[year_m]:
                            ret[year_m][author] = 0
                        ret[year_m][author] += score * year_weight[year]
                    else:
                        score = 100
                        if year_m not in ret_testplan:
                            ret_testplan[year_m] = {}
                        if author not in ret_testplan[year_m]:
                            ret_testplan[year_m][author] = 0
                        ret_testplan[year_m][author] += score * year_weight[year]

    return ret,ret_testplan

#   Sii 3,11
# 3  PR Review Count (S/M/L)
# 11 TEST PR review count (S/M/L)
def calculate_review():
    ret = {}
    ret_test = {}
    for repo_number_author, detail in reviews_map.items():
        repo = repo_number_author.split(',')[0]
        number = repo_number_author.split(',')[1]
        author = repo_number_author.split(',')[2]
        year_m = detail['year_m']
        year = year_m[:4]
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
            if year_m not in ret_test:
                ret_test[year_m] = {}
            if author not in ret_test[year_m]:
                ret_test[year_m][author] = 0
            ret_test[year_m][author] += 2 * score * year_weight[year]
        else:
            if year_m not in ret:
                ret[year_m] = {}
            if author not in ret[year_m]:
                ret[year_m][author] = 0
            ret[year_m][author] += score * year_weight[year]

    return ret,ret_test


#   Sii 2,10
# 2  Merged PR [2] Count (S/M/L)
# 10 Merged Test cases [2] (S/M/L)
def calculate_pr():
    ret = {}
    ret_test = {}
    for repo_number, detail in prs_map.items():
        repo = repo_number.split(',')[0]
        number = repo_number.split(',')[1]
        test = detail['test']
        additions = detail['additions']
        year_m = detail['year_m']
        year = year_m[:4]
        author = detail['author']

        if additions <= 50:
            score = 10
        elif additions <=300:
            score = 20
        else:
            score = 50 + int((additions-300)/100)

        if test:
            if year_m not in ret_test:
                ret_test[year_m] = {}
            if author not in ret_test[year_m]:
                ret_test[year_m][author] = 0
            ret_test[year_m][author] += score * year_weight[year]
        else:
            if year_m not in ret:
                ret[year_m] = {}
            if author not in ret[year_m]:
                ret[year_m][author] = 0
            # TODO test PR score * 2, it is reversed
            ret[year_m][author] += 2 * score * year_weight[year]

    return ret,ret_test



#   Sii 7,8
# 7 Issues Opened Count
# 8 Issues Triaged/Fixed Count
def calculate_issue():
    issue_file = 'sii_issue/issues.json'
    # format:
    # year_m is YYYYmm, ex: 202212
    # open issue:   ret.year_m.${author} += 5 * year_weight
    # triage issue: ret.${org} += 10 * year_weight
    ret_issue = {}
    ret_issue_t = {}

    with open(issue_file) as f:
        content = f.read()

    issues = json.loads(content)
    for issue in issues:
        ts = datetime.strptime(issue['createdAt'], '%Y-%m-%dT%H:%M:%SZ')
        year = str(ts.year)
        year_m = ts.strftime("%Y%m")
        author = issue['author']
        labels = issue['labels'].split(',')
        if author in automation_account:
            continue
        # if github account deleted, it is ''
        if author == '':
            continue

        if str(year) not in year_weight:
            continue

        if year_m not in ret_issue:
            ret_issue[year_m] = {}

        if author not in ret_issue[year_m]:
            ret_issue[year_m][author] = 0

        # SII for opening issue
        ret_issue[year_m][author] += 5 * year_weight[year]

        # SII for issue triage
        for label in issue['labels'].split(','):
            if label.lower() in org_map:
                Org = org_map[label.lower()]
                if Org not in ret_issue_t:
                    ret_issue_t[Org] = 0
                ret_issue_t[Org] += 10 * year_weight[year]

    return ret_issue, ret_issue_t


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
    print(author_org_dup)
    print('pr count:' ,len(prs_map))
    print(random.choice(list(prs_map.items())))
    print('review count:', len(reviews_map))
    print(random.choice(list(reviews_map.items())))


def author_org_load():
    global author_org,author_org_dup
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

    tmp = {}
    with open ('sonic-contributor-map/contributors.json') as f:
        content = f.read()
        contributors_list = json.loads(content)
    for contributor in contributors_list:
        contributor = {k.lower(): v for k, v in contributor.items()}
        if contributor['id'] not in tmp:
            tmp[contributor['id']] = contributor['organization']
        else:
            author_org_dup[contributor['id']] = []

    for k, v in dict.items(tmp):
        author_org[k] = v

    for contributor in contributors_list:
        contributor = {k.lower(): v for k, v in contributor.items()}
        if contributor['id'] in author_org_dup:
            if 'enddate' in contributor:
                contributor['enddate'] = datetime.strptime(contributor['enddate'], '%m/%Y').strftime("%Y%m")
            if 'startdate' in contributor:
                contributor['startdate'] = datetime.strptime(contributor['startdate'], '%m/%Y').strftime("%Y%m")

            if 'startdate' not in contributor:
                contributor['startdate'] = datetime.strptime('01/2016', '%m/%Y').strftime("%Y%m")
            if 'enddate' not in contributor:
                contributor['enddate'] = datetime.strptime('01/2030', '%m/%Y').strftime("%Y%m")

            author_org_dup[contributor['id']].append({'organization': contributor['organization'], 'start': contributor['startdate'], 'end': contributor['enddate']})
            author_org[contributor['id']] = 'author_org_dup'


# input dict: .year_m.author = score
# ex: {"202211": {"someone" : 20}}
# output dict .author.score)
def summ_author_scores(*args):
    ret = {}
    for arg in args:
        for year_m, author_score in arg.items():
            for author, score in author_score.items():
                if author in automation_account or author == '':
                    continue
                if author in author_org_dup:
                    for item in author_org_dup[author]:
                        if year_m >= item['start'] and year_m <= item['end']:
                            org = item['organization']
                            author += "(" + org + ")"

                if author not in ret:
                    ret[author] = 0

                ret[author] += score
    return ret

# input dict: year_m.author = score
# output dict: org = score
def summ_org_scores(*args):
    ret = {}
    for arg in args:
        for year_m, author_score in arg.items():
            for author, score in author_score.items():
                org = ''
                if author in automation_account or author == '': 
                    continue

                if author in author_org:
                    org = author_org[author]

                if author in author_org_dup:
                    for item in author_org_dup[author]:
                        if year_m >= item['start'] and year_m <= item['end']:
                            org = item['organization']
                if org == '':
                    org = 'Others'

                if org not in ret:
                    ret[org] = 0 

                ret[org] += score
    return ret

# summ score dicts together
def summ_dict_scores(*args):
    ret = {}
    for arg in args:
        for k, v in arg.items():
            if k not in ret:
                ret[k] = 0
            ret[k] += v

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
            try:
                files = os.listdir(pr_path)
            except FileNotFoundError:
                continue
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
                    ts = datetime.strptime(pr['mergedAt'], '%Y-%m-%dT%H:%M:%SZ')
                    merged_year = str(ts.year)
                    year_m = ts.strftime("%Y%m")
                    repo = pr['repo']
                    number = pr['number']
                    additions = pr['additions']
                    author = parse_author(pr)
                    if author in automation_account:
                        prs_drop[repo + ',' + str(number)] = True
                        continue
                    prs_map[ repo + ',' + str(number) ] = {'year_m': year_m, 'author': author,'test': test, 'additions': additions}

    for year in year_weight:
        paths = ['sii_pr_review/', 'sii_test_pr_review/']
        for path in paths:
            pr_path = path + str(year)
            try:
                files = os.listdir(pr_path)
            except FileNotFoundError:
                continue
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
                        ts = datetime.strptime(review['comment_at'], '%Y-%m-%dT%H:%M:%SZ')
                        author = parse_author(review, 'comment_author')
                    elif 'review_at' in review:
                        if review['review_at'] == None:
                            print('bad case:', review)
                            continue
                        ts = datetime.strptime(review['review_at'], '%Y-%m-%dT%H:%M:%SZ')
                        author = parse_author(review, 'review_author')
                    else:
                        ts = datetime.strptime(review['latestReview_at'], '%Y-%m-%dT%H:%M:%SZ')
                        author = parse_author(review, 'latestReview_author')

                    if author in automation_account:
                        continue
                    # TODO some data need to dump!!!
                    if repo + ',' + str(number) not in prs_map:
                        if repo + ',' + str(number) not in prs_drop:
                            print("Warning: PR data {} {} is missing!!!".format(repo, number), file=sys.stderr)
                        continue
                    if author == prs_map[ repo + ',' + str(number) ]['author']:
                        continue
                    year_m = ts.strftime("%Y%m")
                    merged_year = year_m[:4]
                    if merged_year not in year_weight:
                        continue
                    test = prs_map[ repo + ',' + str(number) ]['test']
                    # Use review count to judge S/M/L
                    if repo + ',' + str(number) + ',' + author not in reviews_map:
                        reviews_map[ repo + ',' + str(number) + ',' + author ] = {'year_m': year_m, 'test': test, 'count': 0 }
                    reviews_map[ repo + ',' + str(number) + ',' + author ]['count'] += 1


if __name__ == '__main__':
    init()
    sii_calculate(False)
    sii_calculate(True)


