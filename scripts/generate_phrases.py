# -*- coding: utf-8 -*-
"""生成短语库分片 ph_a.txt .. ph_z.txt

ECDICT 的 frq 列只覆盖单词，词组全为 0。
所以用两个信号排序：
  1) 带 collins / oxford 标记的核心短语（约 900 条）优先
  2) 其余按"句中最高频词的词频"排序 —— 一个短语里所有词都常用，它大概率也常用
"""
import csv, os, re, sys, collections, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('ph2resp', os.path.join(HERE, 'ph2resp.py'))
m = importlib.util.module_from_spec(spec)
sys.argv_saved = sys.argv
sys.argv = ['x', 'none']
spec.loader.exec_module(m)

CSV = m.CSV
OUT = os.environ.get('DICT_OUT', r'../src/common/dictionary')
LIMIT = int(sys.argv_saved[1]) if len(sys.argv_saved) > 1 else 12000

WORD_FRQ = {}
PHRASES = []

with open(CSV, encoding='utf-8', errors='replace') as f:
    rd = csv.reader(f)
    head = next(rd)
    I = {h: i for i, h in enumerate(head)}
    for row in rd:
        if len(row) <= I['frq']:
            continue
        wd = row[I['word']].strip()
        if not wd:
            continue

        def num(k):
            try:
                return int(row[I[k]].strip())
            except:
                return 0

        frq = num('frq')
        if ' ' not in wd:
            if frq > 0:
                WORD_FRQ[wd.lower()] = frq
            continue

        parts = wd.split()
        if not (2 <= len(parts) <= 4):
            continue
        if not re.fullmatch(r"[a-zA-Z][a-zA-Z'\- ]*", wd):
            continue
        tr = row[I['translation']].strip()
        if not tr:
            continue
        col, oxf = num('collins'), num('oxford')
        PHRASES.append((wd, tr, col, oxf))

print('候选词组: %d' % len(PHRASES))

scored = []
for wd, tr, col, oxf in PHRASES:
    words = [p.lower().strip("'-") for p in wd.split()]
    frqs = []
    ok = True
    for p in words:
        if p not in WORD_FRQ:
            ok = False
            break
        frqs.append(WORD_FRQ[p])
    if not ok:
        continue
    worst = max(frqs)                      # 最生僻的那个词的词频
    marked = (col > 0) or (oxf > 0)
    # 排序键：有 collins/oxford 的绝对优先，其次看最生僻词有多常用
    key = (0 if marked else 1, worst, len(words), wd)
    scored.append((key, wd, tr))

scored.sort(key=lambda x: x[0])
sel = scored[:LIMIT]
print('入选词组: %d' % len(sel))

shards = collections.defaultdict(list)
for _, wd, tr in sel:
    pos, mean = m.clean_meaning(tr)
    if not mean:
        continue
    k = wd[0].lower()
    if not ('a' <= k <= 'z'):
        continue
    shards[k].append('%s\t%s\t%s\t' % (wd.lower(), pos, mean))

total = 0
count = 0
for k in sorted(shards):
    p = os.path.join(OUT, 'ph_%s.txt' % k)
    data = '\n'.join(sorted(shards[k]))
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(data)
    total += os.path.getsize(p)
    count += len(shards[k])

print('写入短语: %d 条, %d 个分片, %.1f KB' % (count, len(shards), total / 1024))
print()
print('=== 抽样 ===')
for k in ['l', 't', 'i', 'a']:
    if k in shards:
        for ln in sorted(shards[k])[:4]:
            print('  ' + ln.replace('\t', ' | '))
