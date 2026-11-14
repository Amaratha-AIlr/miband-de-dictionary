# De词典 · Offline EN–ZH Dictionary for Mi Band

> 小米手环 11（Vela 快应用）上的**离线英汉词典**。3,000 常用词 + 12,000 条短语，英汉双向，音标用「重拼」写成能直接读的拼法。

![version](https://img.shields.io/badge/version-7.4.0-brightgreen)
![size](https://img.shields.io/badge/rpk-503%20KB-blue)
![words](https://img.shields.io/badge/3%2C000%20words%20%2B%2012%2C000%20phrases-informational)
![platform](https://img.shields.io/badge/Xiaomi%20Vela-QuickApp-orange)

**下载**：米坛社区（待发布）

---

## 它长什么样

```
首页                    列表页                详情页
┌──────────┐        ┌──────────┐        ┌──────────┐
│          │        │ ‹ contact │        │ ‹ 详情    │
│   📕     │        │          │        │          │
│  DE词典   │  →     │ contact  │   →    │ contact  │
│ ┌──────┐ │        │ contain  │        │ kon'-takt│
│ │点击输入│⌕│        │ contest  │        │ (n/vi/vt)│
│ └──────┘ │        │          │        │ 联系；接触 │
│   关于    │        │ [键盘]    │        │ (相关短语)│
└──────────┘        └──────────┘        └──────────┘
```

---

## 功能

### 英 → 汉

输 `contact` → 出 `contact / kon'-takt / n/vi/vt / 联系；接触；使接触`

- **精确匹配 + 前缀推荐**：输 `con` 会列出 `contact / contain / contest / …`
- **词性、释义精简**：一行看完，不刷屏
- **重拼音标**：`dictionary → dik'-shuh-nuh-ri`，用小写字母 + 撇号标重音 + 连字符分音节

### 汉 → 英

用键盘切到中文拼音输入「保险」→ 列出 `safety / insurance / assure / …` → 点进去看英文详情

### 短语

- 直接查：`look up`、`according to`、`take care of`
- **相关短语**：详情页点「相关短语」，列出包含该词的短语

### 界面与交互

- **纯黑白配色**，无彩色干扰（图标除外）
- **分级返回**：详情 → 列表 → 输入 → 关于 → 首页，一级一级退，不会突然退出应用
- **搜索框居中**：输入时搜索框落在屏幕上方正中，不被顶栏挤压
- **完全离线**：无网络请求，词库全在包里

---

## 词库

| 项目 | 数量 | 说明 |
|---|---|---|
| 英文词条 | 3,000 | 按 ECDICT 词频取最常用的 |
| 汉英索引 | 10,289 | 由中文释义反向建立 |
| 短语 | 12,000 | 词组条目，按 collins/oxford 标记 + 句中词频排序 |

**分片结构**（按首字母切分，打开应用不预加载，敲首字母才读那一片）：

```
src/common/dictionary/
  en_a.txt … en_z.txt    26 片，单词
  zh_00 … zh_15          16 片，汉英（按首字哈希）
  ph_a.txt … ph_x.txt    24 片，短语
```

单行格式：`词条 \t 词性 \t 释义 \t 重拼`

---

## 音标为什么不用 IPA

手环字体**没有国际音标字形**（`ə ʃ θ ŋ` 这些），直接显示会变成豆腐块。

所以用**重拼（respelling）**：把音标转成用小写字母就能读的拼法。

```
contact      →  kon'-takt
dictionary   →  dik'-shuh-nuh-ri
beautiful    →  byoo'-ti-ful
philosophy   →  fi'lo-suh-fi
```

规则要点：

- 撇号 `'` 标重音位置
- 连字符 `-` 分音节
- 与拼写几乎相同的词**不显示音标**（`and`、`up` 这种标了没信息量），省体积也省干扰
- 英式非卷舌音标会补 `r`（`for → fawr`、`car → kahr`），否则中文用户会念错

---

## 技术要点

### 这个项目踩过的最大的坑：`file.readText` 的返回值

```js
// ❌ 错：把返回对象当字符串
success: (data) => { const text = String(data || '') }   // → "[object Object]"

// ✅ 对：取 data.text
success: (data) => { const text = data && data.text ? data.text : "" }
```

Vela 的 `file.readText` 成功回调给的是 **`{ text: "..." }` 对象**，不是字符串。搞错这一处，表现是「应用能装上、界面正常、但查什么都是未找到」—— 极难定位。

### 包体积与键盘组件

- 键盘用 [NEORUAA/Vela_input_method](https://github.com/NEORUAA/Vela_input_method)（MIT），组件本身编译后约 500 KB JS
- 日语罗马字词表（24 KB）替换为空壳，只保留中英输入
- 实测包体到 **500 KB 左右仍可正常安装**；早期 1.1 MB 的版本会在蓝牙传输阶段中断

### 其他

- 画布 212×520，`designWidth: "device-width"`
- 组件根类名是 `.page`，页面根类名必须避开（本页用 `.dd-page`）—— Vela 不隔离组件样式，同名会互相污染
- 自定义组件 `<import>` 的 `src` **必须带 `.ux` 后缀**，省略会导致页面不挂载（黑/白屏）

---

## 目录结构

```
src/
  app.ux / manifest.json
  pages/index/index.ux          单页四视图：首页 / 输入 / 列表 / 详情 / 关于
  components/InputMethod/       QWERTY 键盘（来自 Vela_input_method，MIT）
  common/
    scripts/dict.js             查词核心：分片加载 + 二分查找 + 前缀推荐
    dictionary/                 词库分片（en_ / zh_ / ph_）
    images/                     图标、作者拼图
  i18n/
scripts/                        词库生成脚本（见下）
```

---

## 自己重新生成词库

词库不是手改的，都由脚本从 ECDICT 生成：

```bash
# 1. 下载 ECDICT 到工作区
#    https://github.com/skywind3000/ECDICT  → ecdict.csv

# 2. 生成英文 + 汉英分片
python scripts/generate_dict.py 3000

# 3. 生成短语分片
python scripts/generate_phrases.py 12000
```

（脚本内的 ECDICT 路径按需修改。）

---

## 构建

```bash
npm i
npx aiot build --complete-feature        # 调试包
npx aiot release --complete-feature --drop-console true   # 发布包（需签名）
```

> ⚠️ **`aiot build` 会覆盖 `aiot release` 的产物**，要发版就先 build 再 release，或 release 后别再 build。

签名需要 `sign/private.pem` + `sign/certificate.pem`（已被 .gitignore 排除）。

---

## 许可证

MIT © 2026 Amarantha

第三方资源：

- 词库数据 [ECDICT](https://github.com/skywind3000/ECDICT) — MIT
- 键盘组件 [Vela_input_method](https://github.com/NEORUAA/Vela_input_method) — MIT

详见 [LICENSE](LICENSE)。

---

## 关于

与 Amarantha 及 DeepSeek AI 共同完成。
