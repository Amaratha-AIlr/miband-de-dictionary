# -*- coding: utf-8 -*-
"""
De词典 · 重拼引擎 v2
    python ph2resp.py sample   # 输出样本供审阅
"""
import csv, os, re, sys, collections

CSV = os.environ.get('ECDICT_CSV', r'../ECDICT-master/ecdict.csv')
TOOLS = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# 音素映射（按"念出来最接近"的原则，尽量用英文母语者能直读的拼写）
# 长模式在前，保证最长匹配优先
# ============================================================
PHON = [
    # ---- 双元音 ----
    ('ɒ:r', 'or'), ('ɔ:r', 'or'), ('ɑ:r', 'ar'), ('a:r', 'ar'),
    ('єә', 'air'),
    ('eə', 'air'), ('eә', 'air'), ('ɛə', 'air'),
    ('uə', 'oor'), ('uә', 'oor'), ('ʊə', 'oor'),
    ('ɔi', 'oy'), ('ɔɪ', 'oy'), ('ɒi', 'oy'),
    ('əu', 'oh'), ('әu', 'oh'), ('oʊ', 'oh'), ('ou', 'oh'),
    ('au', 'ow'), ('aʊ', 'ow'),
    ('ei', 'ay'), ('eɪ', 'ay'),
    ('ai', 'ai'), ('aɪ', 'ai'), ('ʌi', 'ai'),
    # ---- 长元音 ----
    ('i:', 'ee'), ('u:', 'oo'), ('ɔ:', 'aw'), ('ɑ:', 'ah'),
    ('ɔ:', 'aw'), ('ɜ:', 'ur'), ('ə:', 'ur'), ('ә:', 'ur'),
    ('a:', 'ah'), ('ɒ:', 'aw'), ('e:', 'ay'),
    # ---- 短元音 ----
    ('æ', 'a'), ('a', 'a'), ('e', 'e'), ('ɛ', 'e'), ('є', 'e'),
    ('i', 'i'), ('ɪ', 'i'),
    ('u', 'u'), ('ʊ', 'u'), ('ʌ', 'u'),
    ('ɒ', 'o'), ('ɔ', 'o'), ('o', 'o'),
    ('ə', 'uh'), ('ә', 'uh'),
    ('ɚ', 'ur'), ('ɝ', 'ur'),
    # ---- 辅音 ----
    ('tʃ', 'ch'), ('t͡ʃ', 'ch'), ('dʒ', 'j'), ('d͡ʒ', 'j'),
    ('ʃ', 'sh'), ('ʒ', 'zh'),
    ('θ', 'th'), ('ð', 'dh'),
    ('ŋ', 'ng'), ('j', 'y'), ('ɡ', 'g'),
    ('ɹ', 'r'), ('ː', ''), ('ˑ', ''),
]
VOWELS = set('aeiou' + 'aeiou'.upper())

# 判断某个映射产出的是元音还是辅音
def is_vowel_rep(rep):
    if not rep:
        return False
    return rep[0] in 'aeiou'


def clean_phonetic(s):
    """清洗 ECDICT 音标：去变体、去括号、去音节点、去空格"""
    if not s:
        return ''
    s = s.strip().strip('/[]')
    # 变体分隔：", -xxx" 之后一律丢弃
    s = re.split(r',\s*-', s)[0]
    # 去括号内容（(r)/(ә) 等可选音）
    s = re.sub(r'\([^)]*\)', '', s)
    s = re.sub(r'\[[^\]]*\]', '', s)
    # 逗号在 ECDICT 里既可能是变体也可能是次重音音节界，
    # 统一删除（音节界由元音自动切分，不需要逗号）
    s = s.replace(',', '')
    s = s.replace('.', '')
    s = s.replace(' ', '')
    s = s.replace('-', '')
    s = s.replace('ˌ', '')
    return s.strip()


def tokenize(ph):
    """音标 -> [('V'|'C'|'S', 'rep'), ...]"""
    s = clean_phonetic(ph)
    s = s.replace("'", '\x01').replace('ˈ', '\x01')
    toks = []
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        if ch == '\x01':
            toks.append(('S', ''))
            i += 1
            continue
        hit = False
        for pat, rep in PHON:
            if s.startswith(pat, i):
                kind = 'V' if is_vowel_rep(rep) else 'C'
                toks.append((kind, rep))
                i += len(pat)
                hit = True
                break
        if hit:
            continue
        # 兜底：单字母辅音原样保留
        if ch in 'rlmnpbtdkfvszhgwkcxq':
            toks.append(('C', ch))
        i += 1
        # 其他字符（罕见 IPA 符号）直接丢弃
    return toks


def syllabify(toks):
    """切音节：重音记号开新音节；元音核开新音节"""
    syls = []          # [(letters, stressed)]
    cur = []
    cur_st = False
    has_v = False
    for kind, rep in toks:
        if kind == 'S':
            if cur:
                syls.append((cur, cur_st))
                cur, cur_st, has_v = [], False, False
            cur_st = True
            continue
        if kind == 'V':
            if has_v:
                syls.append((cur, cur_st))
                cur, cur_st, has_v = [], False, False
            cur.append(rep)
            has_v = True
        else:
            cur.append(rep)
    if cur:
        syls.append((cur, cur_st))

    # 重平衡：上一音节尾部辅音过多时，把最后若干辅音移到下一音节开头
    def is_v(rep):
        return is_vowel_rep(rep)

    changed = True
    guard = 0
    while changed and guard < 8:
        changed = False
        guard += 1
        for i in range(len(syls) - 1):
            a, ast = syls[i]
            b, bst = syls[i + 1]
            if not b:
                continue
            # 下一音节是否以元音开头
            b_starts_vowel = is_v(b[0])
            if not b_starts_vowel:
                continue
            # 上一音节尾部连续辅音数
            k = 0
            for rep in reversed(a):
                if is_v(rep):
                    break
                k += 1
            if k >= 1:
                # 上一音节去掉这个辅音后，仍必须含元音，否则不拆
                rest = a[:-1]
                if not any(is_v(r) for r in rest):
                    continue
                # 以下辅音不搬到下一音节开头：
                #   双字母辅音 sh/ch/th/dh/ng/zh（搬了会读错）
                #   r（r 上色元音，r 留在前一音节才对）
                if a[-1] == 'ng':
                    continue
                moved = a.pop()
                b.insert(0, moved)
                changed = True
    return syls


def ph2resp(ph):
    toks = tokenize(ph)
    if not toks:
        return ''
    syls = syllabify(toks)
    parts = []
    for letters, st in syls:
        s = ''.join(letters)
        if not s:
            continue
        parts.append(("'" if st else '') + s)
    out = '-'.join(parts)
    # 清理连字符与引号
    out = re.sub(r'-{2,}', '-', out)
    out = re.sub(r"'\-", "'", out)
    out = re.sub(r"-\'", "'", out)
    out = out.strip("-")
    out = re.sub(r"^'", '', out)     # 首音节重音不标（如 'kɒntækt -> kon'-takt）
    # 首音节重音要标在首音节后
    if parts and syls and syls[0][1] and len(parts) > 1:
        out = parts[0].lstrip("'") + "'-" + '-'.join(parts[1:])
        out = out.replace("'", "'", 1)
    return out


# ============================================================
# 释义精简
# ============================================================
POS_MAP = {'a': 'adj', 'ad': 'adv', 'adv': 'adv', 'adj': 'adj', 'n': 'n', 'v': 'v',
           'vt': 'vt', 'vi': 'vi', 'pron': 'pron', 'prep': 'prep', 'conj': 'conj',
           'num': 'num', 'art': 'art', 'aux': 'aux', 'int': 'int', 'abbr': 'abbr',
           'suf': 'suf', 'pref': 'pref', 'pl': 'pl', 'comb': 'comb', 'modal': 'modal'}
POS_RE = re.compile(r'^\s*([a-z]{1,5})\.\s*')
MEANING_MAX = 46


def clean_meaning(tr):
    if not tr:
        return '', ''
    lines = [x.strip() for x in tr.replace('\\n', '\n').split('\n') if x.strip()]
    poss, senses = [], []
    for ln in lines[:4]:
        m = POS_RE.match(ln)
        pos = ''
        if m:
            pos = POS_MAP.get(m.group(1).lower(), '')
            ln = ln[m.end():]
        ln = ln.strip()
        if not ln:
            continue
        if pos and pos not in poss:
            poss.append(pos)
        ln = re.sub(r'\[[^\]]*\]', '', ln)
        ln = re.sub(r'\([^)]*\)', '', ln)
        parts = [p.strip() for p in re.split(r'[;；,，]', ln) if p.strip()]
        if parts:
            senses.append(parts[0])
        if len(senses) >= 3:
            break
    meaning = '；'.join(senses)
    if len(meaning) > MEANING_MAX:
        meaning = meaning[:MEANING_MAX - 1] + '…'
    return '/'.join(poss), meaning


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'sample'

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
            ph = row[I['phonetic']].strip()
            tr = row[I['translation']].strip()
            if not ph or not tr:
                continue
            rows.append((frq, wd, ph, tr))
    rows.sort(key=lambda x: x[0])

    if mode == 'sample':
        os.makedirs(TOOLS, exist_ok=True)
        out = os.path.join(TOOLS, 'sample2.txt')
        L = ['重拼引擎 v2 样本', '=' * 80,
             '%-14s %-18s %-26s %s' % ('word', '原音标', '重拼', '词性 释义'),
             '-' * 80]
        want = ['contact', 'dictionary', 'beautiful', 'schedule', 'bright',
                'hospital', 'temperature', 'comfortable', 'photograph', 'through',
                'thought', 'either', 'the', 'despair', 'arrogance', 'threshold',
                'theologian', 'prognosis', 'archaic', 'petunia', 'officeholder',
                'devaluation', 'intermission', 'culpability', 'reinforcer',
                'mythical', 'sylvan', 'dimple', 'cicada', 'quantity',
                'keynote', 'deflect', 'bunk', 'dew', 'hearten', 'ion',
                'marinade', 'oriented', 'prognosis', 'resident', 'operation']
        seen = set()
        for target in want:
            for frq, wd, ph, tr in rows:
                if wd == target and wd not in seen:
                    seen.add(wd)
                    pos, mean = clean_meaning(tr)
                    L.append('%-14s %-18s %-26s %s %s' % (wd, ph, ph2resp(ph), pos, mean))
                    break
        with open(out, 'w', encoding='utf-8') as f:
            f.write('\n'.join(L))
        print('样本:', out, len(seen), '条')
        return

    print('full 模式待实现')


if __name__ == '__main__':
    main()
