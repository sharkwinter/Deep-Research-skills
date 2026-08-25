#!/usr/bin/env python3
"""引文回源核查：报告里每段英文引文，必须能在 sources/ 里找到。
用法: quotecheck.py <报告.md> <sources 目录>"""
import re,sys,glob,os
rep=open(sys.argv[1],encoding='utf-8').read()
src="".join(open(f,encoding='utf-8',errors='ignore').read() for f in glob.glob(os.path.join(sys.argv[2],'*')) if os.path.isfile(f))
def norm(x):
    x=re.sub(r'(?m)^[>#\s]+','\n',x)     # 剥掉行首引用块/标题标记（引文常跨行）
    x=re.sub(r'\*\*|\*|`|"|\u201c|\u201d','',x)   # 去强调/反引号/内嵌引号
    x=x.replace('“','"').replace('”','"').replace('’',"'")
    return re.sub(r'\s+',' ',x).strip().lower()
srcn=norm(src)
spans=set()
for pat in (r'"([^"\n]{15,})"', r'“([^”\n]{15,})”'):
    spans |= {m.group(1) for m in re.finditer(pat, rep)}
def is_english_prose(s):
    if '_' in s and ' ' not in s.strip(): return False   # 标识符不是引文
    words=re.findall(r"[A-Za-z][A-Za-z'\-]+", s)
    return len(words)>=5 and len(words)/max(1,len(s.split()))>0.6
cands=sorted(s for s in spans if is_english_prose(s))
bad=[]
for q in cands:
    parts=[p for p in re.split(r'\.\.\.|…', q) if len(norm(p))>=15]  # 省略号切段，逐段核
    if all(norm(p) in srcn for p in (parts or [q])): continue
    bad.append(q)
print(f"英文引文 {len(cands)} 条 | 未回源 {len(bad)} 条")
for b in bad: print("  ✗",re.sub(r'\s+',' ',b)[:150])
sys.exit(1 if bad else 0)
