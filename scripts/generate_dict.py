# -*- coding: utf-8 -*-
"""
De词典 · 完整词库构建
    1. 英文词条 -> en_*.txt（按首字母分片）
    2. 汉英反向索引 -> zh_*.txt（按首字哈希分 16 片）
    3. 输出体积报告

用法: python build_all.py [词条数]
"""
import csv, os, sys, re, collections, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('ph2resp', os.path.join(HERE, 'ph2resp.py'))
m = importlib.util.module_from_spec(spec)
sys.argv_saved = sys.argv
sys.argv = ['x', 'none']
spec.loader.exec_module(m)

CSV = m.CSV
OUT = os.environ.get('DICT_OUT', r'../src/common/dictionary')
REPORT = os.path.join(HERE, 'build_report2.txt')

LIMIT = int(sys.argv_saved[1]) if len(sys.argv_saved) > 1 else 35000
ZH_BUCKETS = 16
ZH_MAX_EN = 4          # 每个中文词最多挂几个英文
ZH_MIN_LEN, ZH_MAX_LEN = 2, 6

lines = []
def w(s=''):
    lines.append(str(s))


def norm_resp(resp):
    """归一化重拼，用于判断"是否冗余" """
    return re.sub(r"['\-]", '', resp).lower()


def is_redundant(word, resp):
    """重拼和拼写几乎一样时，标出来没有信息量"""
    if not resp:
        return True
    return norm_resp(resp) == word.lower()


# ============================================================
# 读词
# ============================================================
rows = []
with open(CSV, encoding='utf-8', errors='replace') as f:
    rd = csv.reader(f)
    head = next(rd)
    I = {h: i for i, h in enumerate(head)}
    for row in rd:
        if len(row) <= I['frq']:
            continue
        wd = row[I['word']].strip()
        if not wd or ' ' in wd:
            continue
        try:
            frq = int(row[I['frq']].strip())
        except:
            frq = 0
        if frq <= 0:
            continue
        rows.append((frq, wd, row[I['phonetic']].strip(), row[I['translation']].strip()))
rows.sort(key=lambda x: x[0])
sel = rows[:LIMIT]

# ============================================================
# 英文分片
# ============================================================
os.makedirs(OUT, exist_ok=True)
for old in os.listdir(OUT):
    if old.endswith('.txt'):
        os.remove(os.path.join(OUT, old))

shards = collections.defaultdict(list)
no_ph = 0
redundant = 0
for frq, wd, ph, tr in sel:
    pos, mean = m.clean_meaning(tr)
    resp = m.ph2resp(ph)
    wl = wd.lower()
    # 非卷舌音标补 r
    if resp and not resp.endswith('r') and (wl.endswith('r') or wl.endswith('re')):
        resp = resp + 'r'
    if not ph:
        no_ph += 1
    if is_redundant(wd, resp):
        redundant += 1
        resp = ''            # 冗余音标不存，省体积
    line = '%s\t%s\t%s\t%s' % (wd, pos, mean, resp)
    k = wd[0].lower()
    if not (k.isalpha() and k.isascii()):
        k = '_'
    shards[k].append(line)

en_total = 0
for k in sorted(shards):
    data = '\n'.join(sorted(shards[k]))
    p = os.path.join(OUT, 'en_%s.txt' % k)
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(data)
    en_total += os.path.getsize(p)

# ============================================================
# 汉英反向索引
# ============================================================
CN_RE = re.compile(r'[\u4e00-\u9fff]{2,6}')
POS_PREFIX = re.compile(r'^[a-z]{1,6}\.\s*')
# 噪音过滤：动词短语碎片、带"的/地/得"的形容词变形
CN_NOISE_HEAD = ('使', '被', '给', '让', '把', '对', '向', '在', '于', '为', '跟', '和', '与')
CN_TAIL = ('的', '地', '得', '了', '着', '过', '们')


def clean_cn(seg):
    """清洗中文词条，返回可入库的规范词（可能为空）"""
    seg = seg.strip()
    # 去掉开头的噪音动词/介词
    changed = True
    while changed and seg:
        changed = False
        for h in CN_NOISE_HEAD:
            if seg.startswith(h) and len(seg) > len(h) + 1:
                seg = seg[len(h):]
                changed = True
                break
    # 去掉结尾的助词
    changed = True
    while changed and seg:
        changed = False
        for t in CN_TAIL:
            if seg.endswith(t) and len(seg) > len(t) + 1:
                seg = seg[:-len(t)]
                changed = True
                break
    if not re.fullmatch(r'[\u4e00-\u9fff]+', seg):
        return ''
    if not (ZH_MIN_LEN <= len(seg) <= ZH_MAX_LEN):
        return ''
    return seg


zh_map = collections.defaultdict(list)     # 中文词 -> [(frq, 英文)]
for frq, wd, ph, tr in sel:
    txt = tr.replace('\\n', '\n')
    # 去掉词性前缀与注释
    for ln in txt.split('\n'):
        ln = POS_PREFIX.sub('', ln.strip())
        ln = re.sub(r'\[[^\]]*\]', '', ln)
        ln = re.sub(r'\([^)]*\)', '', ln)
        # 按中文标点/空格切
        for seg in re.split(r'[；;，,、/|\s]+', ln):
            seg = clean_cn(seg)
            if not seg:
                continue
            if len(zh_map[seg]) < ZH_MAX_EN * 3:
                zh_map[seg].append((frq, wd))

# 排序 + 截断
zh_sorted = {}
for k, v in zh_map.items():
    v.sort()
    seen, out = set(), []
    for frq, wd in v:
        if wd in seen:
            continue
        seen.add(wd)
        out.append(wd)
        if len(out) >= ZH_MAX_EN:
            break
    # 只保留"够有用"的条目：
    #   要么能挂 2 个以上英文（说明是个真词），
    #   要么它的最佳英文是高频繁用词（frq <= 4000）
    best_frq = v[0][0] if v else 999999
    if len(out) >= 2 or best_frq <= 4000:
        zh_sorted[k] = out

buckets = collections.defaultdict(list)
for k, v in zh_sorted.items():
    b = ord(k[0]) % ZH_BUCKETS
    buckets[b].append('%s\t%s' % (k, ','.join(v)))

zh_total = 0
for b in range(ZH_BUCKETS):
    data = '\n'.join(sorted(buckets.get(b, [])))
    p = os.path.join(OUT, 'zh_%02d.txt' % b)
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(data)
    zh_total += os.path.getsize(p)

# ============================================================
# 报告
# ============================================================
w('=== De词典 词库构建报告 ===')
w()
w('[英文]')
w('  词条数      : %d' % len(sel))
w('  分片数      : %d' % len(shards))
w('  合计体积    : %.2f MB' % (en_total / 1024 / 1024))
w('  最大分片    : %s  (%.1f KB)' % (
    max(shards, key=lambda k: os.path.getsize(os.path.join(OUT, 'en_%s.txt' % k))),
    max(os.path.getsize(os.path.join(OUT, 'en_%s.txt' % k)) for k in shards) / 1024))
w('  无音标      : %d 条 (%.1f%%)' % (no_ph, 100.0 * no_ph / len(sel)))
w('  冗余音标已删: %d 条' % redundant)
w()
w('[汉英索引]')
w('  中文词条    : %d' % len(zh_sorted))
w('  分片数      : %d' % ZH_BUCKETS)
w('  合计体积    : %.2f MB' % (zh_total / 1024 / 1024))
w()
w('[总计] %.2f MB' % ((en_total + zh_total) / 1024 / 1024))
w()
w('=== 抽样 ===')
for sample in ['contact', 'beautiful', 'philosophy', 'and', 'up']:
    for k in shards:
        for line in shards[k]:
            if line.startswith(sample + '\t'):
                w('  en: ' + line.replace('\t', ' | '))
                break
for sample in ['保险', '联系', '美丽的', '合作']:
    if sample in zh_sorted:
        w('  zh: %s -> %s' % (sample, ','.join(zh_sorted[sample])))

with open(REPORT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print('\n'.join(lines))
