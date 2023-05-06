#!/bin/python3

import json
import sys

def help():

	print("Usage:")
	print("	", sys.argv[0], "path/to/file")
	print()
	print("args:", sys.argv)


def main():

	if len(sys.argv) < 2:
		help()
		exit(1)

	for file in sys.argv[1:]:
		file_c=file.replace("prs","comments")
		with open(file) as f:
			data=json.load(f)
			data_c=[]
			for item in data:
				for comment in item["comments"]:
					if comment["author"]["login"] != item["author"]:
						data_c.append({"repo":item["repo"], "number":item["number"], "author": comment["author"]["login"], "comment": comment["body"]})

		with open(file_c, 'w', encoding='utf8') as f:
			json.dump(data_c, f, indent=4)


if __name__ == "__main__":
	main()
