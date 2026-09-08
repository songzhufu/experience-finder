import argparse,json,re,time
from dataclasses import dataclass,asdict
from datetime import date,datetime
from pathlib import Path
from urllib.parse import quote,urlsplit,urlunsplit
from urllib.request import urlopen
R=Path(__file__).resolve().parents[1]
Q=["\u5b57\u8282\u8df3\u52a8 Agent \u5f00\u53d1 \u9762\u7ecf","\u5b57\u8282\u8df3\u52a8 AI \u5e94\u7528\u5f00\u53d1 \u9762\u7ecf","\u5b57\u8282\u8df3\u52a8 \u667a\u80fd\u4f53\u5f00\u53d1 \u9762\u7ecf","\u6296\u97f3 Agent \u5f00\u53d1 \u9762\u7ecf","\u5b57\u8282\u8df3\u52a8 \u5927\u6a21\u578b\u5e94\u7528\u5f00\u53d1 \u9762\u7ecf","\u5b57\u8282\u8df3\u52a8 AI \u5f00\u53d1 \u9762\u7ecf"]
B=("\u5b89\u5168\u9650\u5236","IP\u5b58\u5728\u98ce\u9669","300012","\u9a8c\u8bc1\u7801","\u6ed1\u5757","\u64cd\u4f5c\u9891\u7e41","\u5f53\u524d\u7b14\u8bb0\u6682\u65f6\u65e0\u6cd5\u6d4f\u89c8","\u626b\u7801\u67e5\u770b","\u767b\u5f55\u540e\u67e5\u770b")
BT=("\u5b57\u8282","\u6296\u97f3","\u98de\u4e66","\u706b\u5c71\u5f15\u64ce","\u8c46\u5305","bytedance","tiktok");AT=("agent","\u667a\u80fd\u4f53","ai\u5e94\u7528","ai \u5e94\u7528","\u5927\u6a21\u578b\u5e94\u7528","llm","rag","\u8c46\u5305");IT=("\u9762\u7ecf","\u9762\u8bd5","\u4e00\u9762","\u4e8c\u9762","\u4e09\u9762","hr\u9762","\u7ec8\u9762")
@dataclass
class N:title:str;publish_date:str;url:str;body:str;query:str;source_rank:int
def cn(u):
 p=urlsplit(u);return urlunsplit((p.scheme,p.netloc,p.path,"",""))
def tx(p):
 try:return p.locator("body").inner_text(timeout=3500)
 except:return ""
def hs(s,a):return any(x in s.lower() for x in a)
def bd(s):return any(x in s for x in B)
def ft(p,a):
 for x in a:
  try:
   v=p.locator(x).first.inner_text(timeout=1000).strip()
   if v:return v
  except:pass
 return ""
def td(s):
 m=re.search(r"\d{4}[-/.\u5e74]\d{1,2}[-/.\u6708]\d{1,2}\u65e5?|\d{1,2}[-/.\u6708]\d{1,2}\u65e5?",s);return m.group() if m else "\u672a\u77e5"
def ok(n):return hs(n.title+n.body,BT)and hs(n.title+n.body,AT)and hs(n.title+n.body,IT)
def cs(p):
 j="""()=>Array.from(document.querySelectorAll('a[href*="/explore/"]')).map(a=>{let n=a,t='';for(let i=0;i<5&&n;i++){t=(n.innerText||'').trim();if(t.length>8)break;n=n.parentElement}return {u:a.href,t:t.split(/\\n+/)[0]||''}})"""
 try:r=p.evaluate(j)
 except:return[]
 d={};[d.setdefault(cn(x["u"]),x)for x in r if x.get("u")];return list(d.values())
def sr(p,q):
 p.goto("https://www.xiaohongshu.com/search_result?keyword="+quote(q),wait_until="domcontentloaded",timeout=60000);p.wait_for_timeout(3000)
 if bd(tx(p)):raise RuntimeError("\u641c\u7d22\u9875\u9700\u8981\u4eba\u5de5\u9a8c\u8bc1")
 try:p.get_by_text("\u6700\u65b0",exact=True).first.click(timeout=2000);p.wait_for_timeout(1000)
 except:pass
 o=[];d=set()
 for _ in range(30):
  for x in cs(p):
   if x["u"]not in d:d.add(x["u"]);o.append(x)
  if len(o)>80:break
  p.mouse.wheel(0,1900);p.wait_for_timeout(900)
 return o
def gr(c,x,q,k):
 p=c.new_page()
 try:
  p.goto(x["u"],wait_until="domcontentloaded",timeout=60000);p.wait_for_timeout(2200);s=tx(p)
  n=N(ft(p,["#detail-title","h1",".title","[class*=title]"])or x["t"],td(s),p.url,ft(p,["#detail-desc",".desc","[class*=desc]","[class*=content]","article"]),q,k)
  return n if n.body and not bd(s)and ok(n)else None
 except Exception as e:print("Skipped",e);return None
 finally:p.close()
def ld(f):
 try:return[N(**json.loads(x))for x in f.read_text(encoding="utf8").splitlines()if x]
 except:return[]
def ky(n):
 m=re.search(r"(?:(\d{4})-)?(\d{1,2})-(\d{1,2})",n.publish_date)
 if not m:return(0,date.min)
 try:return(1,date(int(m.group(1)or datetime.now().year),int(m.group(2)),int(m.group(3))))
 except:return(0,date.min)
def main():
 a=argparse.ArgumentParser();a.add_argument("--target",type=int,default=100);a.add_argument("--cdp-url",default="http://127.0.0.1:9222");a.add_argument("--raw-output",default=str(R/"data"/"byte_agent_interviews_raw.jsonl"));a.add_argument("--markdown-output",default=str(R/"output"/"byte_agent_interviews_recent.md"));z=a.parse_args();raw=Path(z.raw_output);md=Path(z.markdown_output)
 try:urlopen(z.cdp_url+"/json/version",timeout=3).read()
 except Exception as e:raise SystemExit(str(e))
 ns={cn(n.url):n for n in ld(raw)if ok(n)}
 from playwright.sync_api import sync_playwright
 with sync_playwright()as w:
  b=w.chromium.connect_over_cdp(z.cdp_url,timeout=30000);c=b.contexts[0];p=c.pages[-1];k=len(ns)
  for q in Q:
   if len(ns)>=z.target:break
   print("Searching",q,flush=True)
   try:xs=sr(p,q)
   except RuntimeError as e:print(e);break
   for x in xs:
    if len(ns)>=z.target:break
    if cn(x["u"])in ns:continue
    k+=1;n=gr(c,x,q,k)
    if n:ns[cn(n.url)]=n;raw.parent.mkdir(parents=True,exist_ok=True);open(raw,"a",encoding="utf8").write(json.dumps(asdict(n),ensure_ascii=False)+"\n");print(f"Collected {len(ns)}/{z.target}: {n.title}",flush=True)
    time.sleep(1.2)
  b.close()
 o=sorted(list(ns.values()),key=lambda n:(ky(n),-n.source_rank),reverse=True)[:z.target];L=["# \u5b57\u8282 AI \u5e94\u7528\u5f00\u53d1 / Agent \u5f00\u53d1\u9762\u7ecf",""]
 for n in o:L+=["# "+n.title,"","## \u53d1\u5e03\u65f6\u95f4","",n.publish_date,"",n.url,"","## \u9762\u7ecf\u5185\u5bb9","",n.body.strip(),""]
 md.parent.mkdir(parents=True,exist_ok=True);md.write_text("\n".join(L).rstrip()+"\n",encoding="utf8");print(f"Saved {len(o)} posts -> {md}",flush=True);return 0 if len(o)>=z.target else 1
if __name__=="__main__":raise SystemExit(main())
