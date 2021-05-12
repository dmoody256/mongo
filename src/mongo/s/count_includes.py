import os

includes = {}

for dirpath, dnames, fnames in os.walk("./"):
    for f in fnames:
        if f.endswith(".cpp") or f.endswith(".h"):
            try:
                fin = open(os.path.join(dirpath, f), encoding='utf-8')
                lines = fin.readlines()
            except UnicodeDecodeError:
                fin = open(os.path.join(dirpath, f), encoding="ISO-8859-1")
                lines = fin.readlines()
                
            if fin:
                for line in lines:
                    line = line.strip()
                    if '#include' in line:
                        if line not in includes:
                            includes[line] = 1
                        else:
                            includes[line] += 1
                fin.close()

for line, num in sorted(includes.items(), key=lambda tup: tup[1]):
    print(f"{line}: {num}")