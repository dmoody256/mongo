import os

includes = {}

for dirpath, dnames, fnames in os.walk("./"):
    for f in fnames:
        if f.endswith(".cpp"):
            with open(os.path.join(dirpath, f),encoding='utf-8') as fin:
                for line in fin.readlines():
                    if '#include' in line:
                        if line not in includes:
                            includes[line] = 1
                        else:
                            includes[line] += 1

for line, num in sorted(includes.items(), key=lambda tup: tup[1]):
    print(f"{line}: {num}")