#!/bin/python3

import json
import sys

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
        with open(file) as f:
            data = json.load(f)
            for item in data:
                if type(item["author"]) is dict:
                    author = item["author"]["login"]
                    item["author"] = author
                labels = ""
                for label in item["labels"]:
                    labels += label["name"] + ","
                if "," in labels:
                    labels = labels.strip(",")
                item["labels"] = labels

        with open(file, 'w', encoding='utf8') as f:
            json.dump(data, f, indent=4)


if __name__ == "__main__":
    main()
