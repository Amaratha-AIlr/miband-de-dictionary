# scripts/ — 词库生成

词库分片**不是手写的**，全部由这里的脚本从 ECDICT 生成。

## 用法

```bash
# 1. 下载 ECDICT
#    https://github.com/skywind3000/ECDICT  →  ecdict.csv

# 2. 生成英文 + 汉英分片（参数 = 英文词条数）
python generate_dict.py 3000

# 3. 生成短语分片（参数 = 短语条数）
python generate_phrases.py 12000
```

默认从 `../ECDICT-master/ecdict.csv` 读，输出到 `../src/common/dictionary/`。
路径不同时用环境变量覆盖：

```bash
ECDICT_CSV=D:/path/ecdict.csv DICT_OUT=D:/path/dictionary python generate_dict.py 3000
```

## 文件说明

| 文件 | 作用 |
|---|---|
| `generate_dict.py` | 读 ECDICT → 筛选词频 → 转重拼 → 输出 `en_*.txt` / `zh_*.txt` |
| `generate_phrases.py` | 筛选词组 → 输出 `ph_*.txt` |
| `ph2resp.py` | 重拼引擎（音标 → kon'-takt 风格），被上面两个脚本 import |

## 输出格式

单行：`词条 \t 词性 \t 释义 \t 重拼`

- `en_*.txt` 按首字母分 26 片，按词条字典序排列（供二分查找）
- `zh_*.txt` 按首字 Unicode 哈希分 16 片，行格式 `中文词 \t 英文1,英文2,…`
- `ph_*.txt` 短语按首字母分片，格式同 `en_*`

## 注意

- 重拼规则改动后要重新跑，分片才会更新
- 冗余音标（与拼写相同）会被清空，这是有意为之，省体积
