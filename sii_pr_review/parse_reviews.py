#!/bin/python3

import json
import sys
import os

def help():

    print("Usage:")
    print("    ", sys.argv[0], "path/to/file")
    print()
    print("args:", sys.argv)


def main():

    if len(sys.argv) < 2:
        help()
        exit(1)

    for file in sys.argv[1:]:
        data_p=[]
        print("=================",file)
        with open(file) as f:
            data=json.load(f)
            for item in data:
                if "comments" in item.keys():
                    for comment in item["comments"]:
                        tem = {}
                        tem["number"] = item["number"]
                        tem["repo"] = item["repo"]
                        tem["comment_at"] = comment["createdAt"]
                        tem["comment_author"] = comment["author"]["login"]
                        tem["comment_body"] = comment["body"]
                        data_p.append(tem)
                if "reviews" in item.keys():
                    for review in item["reviews"]:
                        tem = {}
                        tem["number"] = item["number"]
                        tem["repo"] = item["repo"]
                        tem["review_at"] = review["submittedAt"]
                        tem["review_author"] = review["author"]["login"]
                        data_p.append(tem)
                if "latestReviews" in item.keys():
                    for latest_review in item["latestReviews"]:
                        tem = {}
                        tem["number"] = item["number"]
                        tem["repo"] = item["repo"]
                        tem["latestReview_at"] = latest_review["submittedAt"]
                        tem["latestReview_author"] = latest_review["author"]["login"]
                        tem["latestReview_state"] = latest_review["state"]
                        data_p.append(tem)

        with open(file, 'w', encoding='utf8') as f:
            json.dump(data_p, f, indent=4)


if __name__ == "__main__":
    main()
