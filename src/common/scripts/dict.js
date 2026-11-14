/**
 * De词典 · 查词核心
 *
 * 关于读包内文件：
 *   不同 Vela 版本对 file.readText 的 uri 写法要求不一致，
 *   这里依次尝试多种写法，取第一个能读出内容的，并把成功的写法记下来复用。
 *
 * 注意：不在模块顶层 import '@system.file'，由页面传入 file 实例。
 */

const ZH_BUCKETS = 16

/* 依次尝试的 uri 模板，%s 为分片名（不含 .txt） */
const URI_FORMS = [
  '/common/dictionary/%s.txt',
  'internal://app/common/dictionary/%s.txt',
  'internal:///common/dictionary/%s.txt',
  'common/dictionary/%s.txt',
  '../common/dictionary/%s.txt'
]

export function createDict(file) {
  const cache = {}
  const pending = {}
  let goodForm = -1          /* 已验证可用的 uri 模板下标 */
  let lastError = ''         /* 最近一次失败信息，用于页面显示 */

  function tryRead(name, formIndex) {
    return new Promise(function (resolve) {
      const uri = URI_FORMS[formIndex].replace('%s', name)
      let done = false
      try {
        file.readText({
          uri: uri,
          encoding: 'utf-8',
          success: function (data) {
            if (done) return
            done = true
            /* 关键：Vela 的 readText 成功回调给的是 {text: "..."} 对象，不是字符串。
               兼容两种形态，避免再退回 [object Object]。 */
            let text = ''
            if (typeof data === 'string') {
              text = data
            } else if (data && typeof data.text === 'string') {
              text = data.text
            } else if (data && data.data && typeof data.data === 'string') {
              text = data.data
            }
            if (!text) {
              lastError = 'EMPTY:' + uri + ' keys=' + (data ? Object.keys(data).join(',') : 'null')
              resolve({ ok: false, form: formIndex, text: '', uri: uri })
              return
            }
            resolve({ ok: true, form: formIndex, text: text, uri: uri })
          },
          fail: function (msg, code) {
            if (done) return
            done = true
            lastError = 'FAIL[' + code + ']' + msg + ' @' + uri
            resolve({ ok: false, form: formIndex, text: '', uri: uri })
          }
        })
      } catch (e) {
        if (done) return
        done = true
        lastError = 'THROW ' + (e && e.message ? e.message : e) + ' @' + uri
        resolve({ ok: false, form: formIndex, text: '', uri: uri })
      }
    })
  }

  function loadShard(name) {
    if (cache[name]) return Promise.resolve(cache[name])
    if (pending[name]) return pending[name]

    const p = (goodForm >= 0
      ? tryRead(name, goodForm).then(function (r) { return r.ok ? r : { ok: false } })
      : (function () {
          /* 未知可用写法：从 0 开始逐个试 */
          let idx = 0
          function step() {
            if (idx >= URI_FORMS.length) return Promise.resolve({ ok: false, text: '' })
            const cur = idx++
            return tryRead(name, cur).then(function (r) {
              if (r.ok) return r
              return step()
            })
          }
          return step()
        })()
    ).then(function (r) {
      if (!r || !r.ok) {
        cache[name] = []
        pending[name] = null
        return []
      }
      goodForm = r.form
      const lines = r.text.split('\n')
      const out = []
      for (let i = 0; i < lines.length; i++) {
        if (lines[i]) out.push(lines[i])
      }
      cache[name] = out
      pending[name] = null
      return out
    })

    pending[name] = p
    return p
  }

  function wordOf(line) {
    const i = line.indexOf('\t')
    return i < 0 ? line : line.substring(0, i)
  }

  function parseEntry(line) {
    const parts = line.split('\t')
    return {
      word: parts[0] || '',
      pos: parts[1] || '',
      meaning: parts[2] || '',
      resp: parts[3] || ''
    }
  }

  function lowerBound(lines, target) {
    let lo = 0
    let hi = lines.length
    while (lo < hi) {
      const mid = (lo + hi) >> 1
      if (wordOf(lines[mid]).toLowerCase() < target) lo = mid + 1
      else hi = mid
    }
    return lo
  }

  function searchEn(text) {
    const q = String(text || '').trim().toLowerCase()
    if (!q) return Promise.resolve({ exact: null, near: [], info: 'EMPTYQ' })
    const first = q.charAt(0)
    const letters = /[a-z]/.test(first) ? first : '_'
    const shardWord = 'en_' + letters
    const shardPhrase = 'ph_' + letters
    return Promise.all([loadShard(shardWord), loadShard(shardPhrase)]).then(function (arr) {
      const lines = arr[0] || []
      const phLines = arr[1] || []
      let exact = null
      const near = []

      /* 先查单词 */
      const idx = lowerBound(lines, q)
      for (let i = idx; i < lines.length && near.length < 12; i++) {
        const w = wordOf(lines[i]).toLowerCase()
        if (w.indexOf(q) !== 0) break
        const e = parseEntry(lines[i])
        e.type = 'word'
        if (w === q && !exact) exact = e
        else near.push(e)
      }

      /* 再查短语（前缀匹配，含空格的查询会命中） */
      if (phLines.length) {
        const pidx = lowerBound(phLines, q)
        for (let i = pidx; i < phLines.length && near.length < 20; i++) {
          const w = wordOf(phLines[i]).toLowerCase()
          if (w.indexOf(q) !== 0) break
          const e = parseEntry(phLines[i])
          e.type = 'phrase'
          if (w === q && !exact) exact = e
          else near.push(e)
        }
      }

      const info = shardWord + ' n=' + lines.length + '/ph=' + phLines.length + ' form=' + goodForm
      return { exact: exact, near: near, info: info }
    })
  }

  /**
   * 相关短语：在 word 首字母那片里找包含该词的短语
   */
  function relatedPhrases(word, limit) {
    const w = String(word || '').trim().toLowerCase()
    const cap = limit || 10
    if (!w) return Promise.resolve([])
    const first = w.charAt(0)
    if (!/[a-z]/.test(first)) return Promise.resolve([])
    return loadShard('ph_' + first).then(function (lines) {
      const out = []
      if (!lines || !lines.length) return out
      for (let i = 0; i < lines.length && out.length < cap; i++) {
        const ln = lines[i]
        if (ln.toLowerCase().indexOf(w) < 0) continue
        out.push(parseEntry(ln))
      }
      return out
    })
  }

  function searchZh(text) {
    const q = String(text || '').trim()
    if (!q) return Promise.resolve({ word: '', candidates: [] })
    const b = q.charCodeAt(0) % ZH_BUCKETS
    const shard = 'zh_' + (b < 10 ? '0' + b : '' + b)
    return loadShard(shard).then(function (lines) {
      const idx = lowerBound(lines, q)
      for (let i = idx; i < lines.length; i++) {
        const ln = lines[i]
        const t = wordOf(ln)
        if (t > q) break
        if (t === q) {
          const rest = ln.substring(ln.indexOf('\t') + 1)
          return { word: q, candidates: rest ? rest.split(',') : [] }
        }
      }
      return { word: q, candidates: [] }
    })
  }

  function getEntry(word) {
    return searchEn(word).then(function (r) {
      return r.exact
    })
  }

  /**
   * 拼音首字母查英文单词
   *   "bx" -> 拼音索引 -> 必须/表现/... -> 各自的中文→英文 -> 英文单词列表
   */
  function searchPy(letters) {
    const q = String(letters || '').trim().toLowerCase()
    if (!q || !/^[a-z]+$/.test(q)) return Promise.resolve([])
    const shard = 'py_' + q.charAt(0)
    return loadShard(shard).then(function (lines) {
      const idx = lowerBound(lines, q)
      const words = []
      for (let i = idx; i < lines.length; i++) {
        const ln = lines[i]
        const t = wordOf(ln)
        if (t > q) break
        if (t === q) {
          const rest = ln.substring(ln.indexOf('\t') + 1)
          if (rest) {
            const arr = rest.split(',')
            for (let j = 0; j < arr.length; j++) {
              if (arr[j] && words.length < 10) words.push(arr[j])
            }
          }
        }
      }
      if (!words.length) return []
      /* 中文词 -> 英文单词 */
      const tasks = []
      for (let i = 0; i < words.length; i++) {
        tasks.push(searchZh(words[i]))
      }
      return Promise.all(tasks).then(function (res) {
        const out = []
        const seen = {}
        for (let i = 0; i < res.length; i++) {
          const cands = (res[i] && res[i].candidates) || []
          for (let j = 0; j < cands.length; j++) {
            const en = cands[j]
            if (en && !seen[en]) {
              seen[en] = 1
              out.push(en)
            }
          }
        }
        return out.slice(0, 20)
      })
    })
  }

  return {
    loadShard: loadShard,
    searchEn: searchEn,
    searchZh: searchZh,
    searchPy: searchPy,
    relatedPhrases: relatedPhrases,
    getEntry: getEntry
  }
}
