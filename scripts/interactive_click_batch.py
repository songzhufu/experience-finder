import argparse,json,re,time
from dataclasses import dataclass,asdict
from datetime import date,datetime
from pathlib import Path
from urllib.parse import quote,urlsplit,urlunsplit
from urllib.request import urlopen
@dataclass
class N:title:str;publish_date:str;url:str;body:str;query:str;source_rank:int
R=Path(__file__).resolve().parents[1]
Q=["\u5b57\u8282\u8df3\u52a8 Agent \u5f00\u53d1 \u9762\u7ecf","\u5b57\u8282\u8df3\u52a8 AI \u5e94\u7528\u5f00\u53d1 \u9762\u7ecf","\u5b57\u8282\u8df3\u52a8 \u667a\u80fd\u4f53\u5f00\u53d1 \u9762\u7ecf","\u6296\u97f3 Agent \u5f00\u53d1 \u9762\u7ecf","\u5b57\u8282\u8df3\u52a8 \u5927\u6a21\u578b\u5e94\u7528\u5f00\u53d1 \u9762\u7ecf","\u5b57\u8282\u8df3\u52a8 AI \u5f00\u53d1 \u9762\u7ecf"]
B=("\u5b89\u5168\u9650\u5236","IP\u5b58\u5728\u98ce\u9669","300012","\u9a8c\u8bc1\u7801","\u6ed1\u5757","\u64cd\u4f5c\u9891\u7e41","\u5f53\u524d\u7b14\u8bb0\u6682\u65f6\u65e0\u6cd5\u6d4f\u89c8","\u626b\u7801\u67e5\u770b","\u767b\u5f55\u540e\u67e5\u770b")
BT=("\u5b57\u8282","\u6296\u97f3","\u98de\u4e66","\u706b\u5c71\u5f15\u64ce","\u8c46\u5305","bytedance","tiktok");AT=("agent","\u667a\u80fd\u4f53","ai\u5e94\u7528","ai \u5e94\u7528","\u5927\u6a21\u578b\u5e94\u7528","llm","rag","\u8c46\u5305");IT=("\u9762\u7ecf","\u9762\u8bd5","\u4e00\u9762","\u4e8c\u9762","\u4e09\u9762","\u7ec8\u9762")
def cn(u):
 p=urlsplit(u);return urlunsplit((p.scheme,p.netloc,p.path,"",""))
def tx(p):
 try:return p.locator("body").inner_text(timeout=4000)
 except:return ""
def ft(p,a):
 for x in a:
  try:
   v=p.locator(x).first.inner_text(timeout=1200).strip()
   if v:return v
  except:pass
 return ""
def dt(s):
 m=re.search(r"\d{4}[-/.\u5e74]\d{1,2}[-/.\u6708]\d{1,2}\u65e5?|\d{1,2}[-/.\u6708]\d{1,2}\u65e5?",s);return m.group()if m else"\u672a\u77e5"
def bad(s):return any(x in s for x in B)
def hs(s,a):return any(x in s.lower()for x in a)
def good(n):return hs(n.title+n.body,BT)and hs(n.title+n.body,AT)and hs(n.title+n.body,IT)
def load(f):
 try:return[N(**json.loads(x))for x in f.read_text(encoding="utf8").splitlines()if x]
 except:return[]
def wait(c,old,secs):
 end=time.time()+secs
 while time.time()<end:
  for p in reversed(c.pages):
   if ("/explore/" in p.url and cn(p.url)!=old) or p.locator("#detail-title").count()>0:return p
  time.sleep(1)
 return None
def latest(p):
 try:
  x=p.get_by_text("\u6700\u65b0",exact=True)
  if x.count():x.first.click(timeout=2000);p.wait_for_timeout(1000)
 except:pass
def key(n):
 m=re.search(r"(?:(\d{4})-)?(\d{1,2})-(\d{1,2})",n.publish_date)
 if not m:return(0,date.min)
 try:return(1,date(int(m.group(1)or datetime.now().year),int(m.group(2)),int(m.group(3))))
 except:return(0,date.min)
def main():
 a=argparse.ArgumentParser();a.add_argument("--target",type=int,default=100);a.add_argument("--cdp-url",default="http://127.0.0.1:9222");a.add_argument("--raw-output",default=str(R/"data"/"byte_agent_clicks_raw.jsonl"));a.add_argument("--markdown-output",default=str(R/"output"/"byte_agent_interviews_recent.md"));a.add_argument("--wait-seconds",type=int,default=900);z=a.parse_args();raw=Path(z.raw_output);md=Path(z.markdown_output)
 urlopen(z.cdp_url+"/json/version",timeout=3).read();ns={cn(n.url):n for n in load(raw)if good(n)}
 from playwright.sync_api import sync_playwright
 with sync_playwright()as w:
  b=w.chromium.connect_over_cdp(z.cdp_url,timeout=30000);c=b.contexts[0];p=c.pages[-1];rank=len(ns)
  while len(ns)<z.target:
   q=Q[len(ns)%len(Q)];p.bring_to_front();p.goto("https://www.xiaohongshu.com/search_result?keyword="+quote(q),wait_until="domcontentloaded",timeout=60000);p.wait_for_timeout(3500)
   if bad(tx(p)):print("Stopped: manual verification required",flush=True);break
   latest(p);old=cn(p.url);print(f"Ready {len(ns)+1}/{z.target}: {q}. Click one new post.",flush=True);d=wait(c,old,z.wait_seconds)
   if not d:print("Stopped: click wait timeout",flush=True);break
   s=tx(d)
   if bad(s):print("Skipped blocked post",flush=True);continue
   n=N(ft(d,["#detail-title","h1",".title","[class*=title]"]),dt(s),d.url,ft(d,["#detail-desc",".desc","[class*=desc]","[class*=content]","article"]),q,rank+1)
   if n.body and good(n)and cn(n.url)not in ns:
    rank+=1;n.source_rank=rank;ns[cn(n.url)]=n;raw.parent.mkdir(parents=True,exist_ok=True);open(raw,"a",encoding="utf8").write(json.dumps(asdict(n),ensure_ascii=False)+"\n");print(f"Saved {len(ns)}/{z.target}",flush=True)
   else:print("Skipped duplicate or unrelated post",flush=True)
  b.close()
 o=sorted(ns.values(),key=lambda n:(key(n),-n.source_rank),reverse=True)[:z.target];L=["# \u5b57\u8282 AI \u5e94\u7528\u5f00\u53d1 / Agent \u5f00\u53d1\u9762\u7ecf",""]
 for n in o:L+=["# "+n.title,"","## \u53d1\u5e03\u65f6\u95f4","",n.publish_date,"",n.url,"","## \u9762\u7ecf\u5185\u5bb9","",n.body.strip(),""]
 md.parent.mkdir(parents=True,exist_ok=True);md.write_text("\n".join(L).rstrip()+"\n",encoding="utf8");print(f"Wrote {len(o)} posts -> {md}",flush=True)
if __name__=="__main__":main()
