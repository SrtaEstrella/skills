#!/usr/bin/env python3
"""scientella-knowledge format checker."""

import re, sys, os

def _content_and_lines(path):
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()
    return c, c.splitlines()

# 3.4.1: 缩进只允许 4 空格或其倍数，禁止 Tab，禁止不规则空格数
def s3_4_1(lines):
    v = []
    for i, line in enumerate(lines, 1):
        if not re.match(r'^( {4})*- ', line): continue
        leading = re.match(r'^( *)', line).group(1)
        if '\t' in leading:
            v.append((i, f'含Tab缩进，统一使用4空格缩进 (\u00a73.4.1)'))
        elif len(leading) % 4 != 0:
            v.append((i, f'空格缩进不是4的倍数: {len(leading)}个空格 (\u00a73.4.1)'))
    return v

# 3.4.3: 每行正文（可读内容）不超过 150 字
# 测量时提取 wikilink 字面形态、去除粗体/斜体/行内代码等格式标记，
# 再扣除项目符号和缩进空格，然后逐字符计数（含中英文及数字，不含空白和已去除的格式标记）。
def _visible_length(line):
    """Return the visible text length of a line after stripping markup."""
    # 1. Strip leading bullet + whitespace
    body = re.sub(r'^(\t|    )*(-\s+)?', '', line)
    # 2. Extract wikilink display text: [[target|display]] -> display, [[target]] -> target
    body = re.sub(r'\[\[[^\]|]+\|([^\]]+)\]\]', r'\1', body)
    body = re.sub(r'\[\[([^\]]+)\]\]', r'\1', body)
    # 3. Strip bold/italic markers: **, __, *, _
    body = re.sub(r'\*\*|__|\*|_', '', body)
    # 4. Strip inline code backticks
    body = re.sub(r'`[^`]+`', 'CODE', body)
    # 5. Strip zero-width control chars and whitespace, then count all remaining characters
    body = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\u2060\ufeff\s]', '', body)
    return len(body)

def s3_4_3(lines):
    v = []
    in_fm = fm_closed = False
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s == '---':
            if not in_fm: in_fm = True
            elif in_fm and not fm_closed: fm_closed = True; continue
        if not fm_closed: continue
        if s.startswith('```') or s.startswith('|') or s.startswith('#') or s == '' or '$$' in s:
            continue
        vl = _visible_length(line)
        if vl > 150:
            v.append((i, f'正文单行 {vl} 字超限（<=150），建议拆解 (\\u00a73.4.3)'))
    return v

# 3.4.12: 正文不得有空行
def s3_4_12(lines):
    v = []
    in_fm = fm_closed = False
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s == '---':
            if not in_fm: in_fm = True
            elif in_fm and not fm_closed: fm_closed = True; continue
        if fm_closed and s == '':
            if i < len(lines) and lines[i].lstrip().startswith('|'):
                continue
            v.append((i, '正文中不得有空行 (\u00a73.4.12)'))
    return v

# 3.5.1: 条目以标点结尾（中文句号/分号/问号/叹号/冒号/引号/括号均合法）
def s3_5_1(lines):
    END_PUNCT_CJK = set('。；！？：\"\"\'\'）】》」』〕〉》\uff09\u3011\u300b\u300f\uff3d\u300d\u300f')
    END_PUNCT_LATIN = set('.!?;:\"\')\u201d\u2019]')
    ALL_END = END_PUNCT_CJK | END_PUNCT_LATIN
    v = []
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if not re.match(r'^(\t|    )*- ', line): continue
        content = re.sub(r'^\s*-\s+', '', s)
        if not content or content.startswith('```') or content.startswith('---') or content.startswith('#'): continue
        if content.startswith('\U0001f4a1'): continue
        # also skip lines ending in LaTeX ($$ or $)
        if content.rstrip().endswith('$'): continue
        if content[-1] not in ALL_END:
            # Only flag CJK-content lines that are substantial
            if re.search(r'[一-鿿]', content) and len(content) > 10:
                v.append((i, f'条目缺结尾标点: "{content[:60]}" (\\u00a73.5.1)'))
    return v

# 3.5.2: 禁止 em-dash
def s3_5_2(lines):
    v = []
    for i, line in enumerate(lines, 1):
        for m in re.finditer('[\u2014\u2015]', line):
            ctx = line[max(0,m.start()-5):m.end()+5].strip()
            v.append((i, f'行{i}列{m.start()+1}: 破折号 (\u00a73.5.2) "...{ctx}..."'))
    return v

# 3.5.3: 弯引号
def s3_5_3(lines):
    v = []
    for i, line in enumerate(lines, 1):
        for m in re.finditer('[\u300c\u300d]', line):
            v.append((i, f'行{i}列{m.start()+1}: 直角引号，改用弯引号 (\u00a73.5.3)'))
        # 逐字符状态机：仅检测反引号外的半角直引号（代码字面量不参与 Markdown 解析，§3.5.7）
        in_code = False
        for j, ch in enumerate(line):
            if ch == '`':
                in_code = not in_code
                continue
            if ch == '"' and not in_code:
                ctx = line[max(0, j - 3):j + 4]
                if re.search(r'[一-鿿]', ctx):
                    v.append((i, f'行{i}列{j + 1}: 中文上下文中半角直引号 (\u00a73.5.3)'))
    return v

# 3.5.4: 括号半角/全角
def s3_5_4(lines):
    v = []
    for i, line in enumerate(lines, 1):
        for m in re.finditer(r'\uff08([A-Za-z0-9\s\-\+/,.\u201c\u201d\u3001]+)\uff09', line):
            inner = m.group(1).strip()
            if re.search(r'[A-Za-z]{3,}', inner):
                v.append((i, f'行{i}列{m.start()+1}: 纯英文全角括号，改用半角"({inner})" (\u00a73.5.4)'))
    return v

# 3.5.5: 术语英文对照首字母大写（跳过反引号内代码，§3.5.7）
def s3_5_5(lines):
    v = []
    for i, line in enumerate(lines, 1):
        in_code = False
        # 将反引号内代码段替换为占位，避免误检代码中的小写标识符
        masked = []
        for j, ch in enumerate(line):
            if ch == '`':
                in_code = not in_code
                masked.append('`')
                continue
            masked.append('X' if in_code else ch)
        masked_line = ''.join(masked)
        for m in re.finditer(r'\(([a-z][a-z\s]+)\)', masked_line):
            inner = m.group(1).strip()
            if re.search(r'[A-Za-z]{4,}', inner) and inner[0].islower():
                before = masked_line[max(0, m.start() - 1):m.start()]
                if before not in ('f', ' '):
                    v.append((i, f'行{i}列{m.start() + 1}: 括号内英文"{inner}"可能应首字母大写 (\u00a73.5.5)'))
    return v

# 3.4.5: 禁止 #/## 标题
def s3_4_5(lines):
    v = []
    in_fm = fm_closed = False
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s == '---':
            if not in_fm: in_fm = True
            elif in_fm and not fm_closed: fm_closed = True; continue
        if not fm_closed: continue
        if re.match(r'^#{1,2}\s', s):
            v.append((i, f'使用了#/##标题，正文仅允许### (\u00a73.4.5)'))
    return v

# 3.1.2: 文件名
def s3_1_2(filepath):
    bn = os.path.basename(filepath)
    v = []
    for ch in '/:*?"<>|':
        if ch in bn:
            v.append((-1, f'文件名"{bn}"含非法字符"{ch}" (\u00a73.1.2)'))
    for m in re.finditer(r'[\uff08\uff09]', bn):
        v.append((-1, f'文件名"{bn}"含全角括号"{m.group()}"，应使用半角"()" (\u00a73.1.2)'))
    return v

# 3.5.6: 粗体空格规则
def s3_5_6(lines):
    v = []
    punct = set('\uff0c\u3002\uff01\uff1f\uff1b\uff1a\u3001\u201c\u201d\u2018\u2019\uff08\uff09\u3010\u3011\u300a\u300b\u2014\u2026,.!?;:\'"()[]{}<>')
    allowed = punct | {' '}
    for i, line in enumerate(lines, 1):
        for m in re.finditer(r'\*\*(.+?)\*\*', line):
            content = m.group(1)
            if not content: continue
            start, end = m.start(), m.end()
            if content[0] in punct:
                if start > 0 and line[start-1] not in allowed:
                    ctx = line[max(0,start-5):end+5]
                    v.append((i, f'粗体内容以标点"{content[0]}"起首，**前缺少空格 (\u00a73.5.6): "...{ctx}..."'))
            if content[-1] in punct:
                if end < len(line) and line[end] not in allowed:
                    ctx = line[max(0,start-5):end+5]
                    v.append((i, f'粗体内容以标点"{content[-1]}"结尾，**后缺少空格 (\u00a73.5.6): "...{ctx}..."'))
    return v

# 3.5.6: 同时检测字面 Unicode 转义序列（如 \u201c），这些是写入工具失败留下的 6 字节 ASCII 序列，非正确 Unicode 字符
def s3_5_7(lines):
    v = []
    for i, line in enumerate(lines, 1):
        for m in re.finditer(r'\\u[0-9a-fA-F]{4}', line):
            v.append((i, f'行{i}列{m.start()+1}: 字面 Unicode 转义序列 "{m.group()}"，应为实际 Unicode 字符 (\u00a73.5.6)'))
    return v

# 3.5.8: 粗体嵌套与未闭合检测（**A **[[B]]** C** 类嵌套粗体是坏格式，条目前导粗体内含链接时不另加粗）
def s3_5_8(lines):
    v = []
    for i, line in enumerate(lines, 1):
        s = line.rstrip('\n')
        if s.strip().startswith('|') or s.strip().startswith('---'):
            continue
        markers = [m.start() for m in re.finditer(r'\*\*', s)]
        n = len(markers)
        if n == 0:
            continue
        if n % 2 == 1:
            ctx = s[max(0, markers[0]-5):markers[-1]+7]
            v.append((i, f'粗体标记数量为奇数（{n} 个 **），存在未闭合粗体 (\u00a73.5.8): "...{ctx}..."'))
            continue
        types = ['开' if k % 2 == 0 else '闭' for k in range(n)]
        for k in range(n-1):
            if types[k] == types[k+1]:
                start = markers[k]
                ctx = s[max(0, start-5):start+12]
                v.append((i, f'粗体嵌套：** 标记未交替配对（**A **[[B]]** C** 类），前导粗体内含链接时不另加粗 (\u00a73.5.8): "...{ctx}..."'))
                break
    return v

# 3.3.7: tag 约束
def s3_3_7(lines):
    v = []
    in_fm = fm_closed = in_tags = False
    tags = []
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s == '---':
            if not in_fm: in_fm = True
            elif in_fm and not fm_closed: fm_closed = True; break
            continue
        if not in_fm or fm_closed: continue
        if re.match(r'^tags:', s): in_tags = True; continue
        if re.match(r'^[a-zA-Z]', s): in_tags = False; continue
        if not in_tags: continue
        m = re.match(r'^\s*-\s+(.+)', s)
        if m:
            tag = re.sub(r'\s*#.*$', '', m.group(1).strip()).strip('\'"')
            if tag: tags.append((i, tag))
        minline = re.match(r'^tags:\s*\[(.+)\]', s)
        if minline:
            for t in re.split(r'[,\s]+', minline.group(1)):
                t = t.strip().strip('"').strip("'")
                if t: tags.append((i, t))
    for ln, tag in tags:
        if ' ' in tag: v.append((ln, f'tag "{tag}" 含空格 (\u00a73.3.7)'))
        if tag and tag[0].isdigit(): v.append((ln, f'tag "{tag}" 以数字开头 (\u00a73.3.7)'))
    return v

# 3.6.4: 生硬「关联」条目（SKILL §3.6.4：禁止 `**关联**：` 及「与 XXX 的关联**：」类条目，关联信息应有机融入正文，跳过反引号内代码；同时检测「关系/联系/区别/比较/对比」的同构条目）
def s3_6_4(lines):
    v = []
    for i, line in enumerate(lines, 1):
        in_code = False
        masked = []
        for ch in line:
            if ch == '`':
                in_code = not in_code
                masked.append('`')
                continue
            masked.append('X' if in_code else ch)
        masked_line = ''.join(masked)
        for m in re.finditer(r'(?:关联|关系|联系|区别|比较|对比)\*\*：', masked_line):
            ctx = line[max(0, m.start() - 12):m.end() + 22]
            v.append((i, f'生硬「关联/关系/联系/区别/比较/对比」类条目（§3.6.4）：检测到「{m.group(0)[:-3]}**：」模式，关联信息应有机融入定义/机制/应用条目；可能为误报（前导词具体到概念名时为合理单列），需能动判断是否真正存在问题: "...{ctx}..."'))
    return v

def check_all(filepath):
    if not os.path.exists(filepath):
        return [('\u2014', '', f'文件不存在: {filepath}')]
    lines = _content_and_lines(filepath)[1]
    results = []
    checks = [
        ('\u00a73.1.2', s3_1_2),
        ('\u00a73.3.7', s3_3_7),
        ('\u00a73.4.1', s3_4_1),
        ('\u00a73.4.3', s3_4_3),
        ('\u00a73.4.5', s3_4_5),
        ('\u00a73.4.12', s3_4_12),
        ('\u00a73.5.1', s3_5_1),
        ('\u00a73.5.2', s3_5_2),
        ('\u00a73.5.3', s3_5_3),
        ('\u00a73.5.4', s3_5_4),
        ('\u00a73.5.5', s3_5_5),
        ('\u00a73.5.6', s3_5_6),
        ('\u00a73.5.6', s3_5_7),
        ('\u00a73.5.8', s3_5_8),
        ('\u00a73.6.4', s3_6_4),
    ]
    for code, fn in checks:
        args = (filepath,) if code == '\u00a73.1.2' else (lines,)
        for lineno, msg in fn(*args):
            results.append((code, lineno, msg))
    return results

def _collect_md_files(paths):
    """Expand CLI args into a list of .md files.

    Accepts three forms, mixed freely:
      - a single .md file
      - a list of .md files
      - one or more directories: recursively collect every *.md under it,
        at any depth (unlimited nesting)
    Hidden directories (names starting with '.') are skipped, matching the
    knowledge-base convention (.workbuddy / .scientella / .obsidian are not
    card content). Non-existent paths are kept as-is so check_all can report
    the "file not found" error.
    """
    files = []
    for p in paths:
        if os.path.isdir(p):
            for dirpath, dirnames, filenames in os.walk(p):
                dirnames[:] = [d for d in dirnames if not d.startswith('.')]
                for fn in filenames:
                    if fn.endswith('.md'):
                        files.append(os.path.join(dirpath, fn))
        else:
            files.append(p)
    return sorted(files)

if __name__ == '__main__':
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, OSError): pass
    if len(sys.argv) < 2:
        print('Usage: python3 scripts/format-check.py <file1.md|dir1> [file2.md|dir2 ...]')
        print('  - file: check that single file')
        print('  - dir : recursively check all .md under it (any depth; hidden dirs skipped)')
        print('  - mixed lists are allowed; paths may be absolute or relative')
        sys.exit(1)
    files = _collect_md_files(sys.argv[1:])
    all_ok = True
    for fp in files:
        res = check_all(fp)
        display = fp.replace('\\', '/')
        if not res:
            print(f'[OK] {display}: 未检测到格式违规')
        else:
            all_ok = False
            print(f'[!!] {display}: {len(res)} 处可疑项')
            for code, line, msg in sorted(res, key=lambda x: (x[0], x[1])):
                print(f'  [{code}] 行{line}: {msg}')
    sys.exit(0 if all_ok else 1)
