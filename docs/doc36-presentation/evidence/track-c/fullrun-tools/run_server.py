import os, sys, json, time, itertools
sys.path.insert(0, r"C:\Users\richi\.codex\worktrees\doc36-writer\lectio\apps\textbook-agent\backend\src")
os.environ["RUN_MIGRATIONS_ON_STARTUP"]="false"
os.environ["DEEPSEEK_STRUCTURED_MODE"]="prompted_json"
LOG=os.environ["PROVIDER_LOG"]
import httpx
_n=itertools.count(1)
async def on_req(request):
    try:
        host=request.url.host
        if "deepseek" not in host: return
        body=request.content.decode("utf-8","replace") if request.content else ""
        request.extensions["lectio_id"]=next(_n)
        request.extensions["lectio_t"]=time.time()
        rec={"kind":"request","n":request.extensions["lectio_id"],"ts":time.time(),"method":request.method,"url":str(request.url),"body":body}
        open(LOG,"a",encoding="utf-8").write(json.dumps(rec)+"\n")
    except Exception as e:
        open(LOG,"a").write(json.dumps({"kind":"hook_error","error":repr(e)})+"\n")
async def on_resp(response):
    try:
        req=response.request
        if "deepseek" not in req.url.host: return
        await response.aread()
        rec={"kind":"response","n":req.extensions.get("lectio_id"),"ts":time.time(),"status":response.status_code,"body":response.text}
        open(LOG,"a",encoding="utf-8").write(json.dumps(rec)+"\n")
    except Exception as e:
        open(LOG,"a").write(json.dumps({"kind":"hook_error","error":repr(e)})+"\n")
_orig=httpx.AsyncClient.__init__
def _init(self,*a,**k):
    hooks=k.get("event_hooks") or {}
    hooks={"request":list(hooks.get("request",[]))+[on_req],"response":list(hooks.get("response",[]))+[on_resp]}
    k["event_hooks"]=hooks
    _orig(self,*a,**k)
httpx.AsyncClient.__init__=_init
import uvicorn
uvicorn.run("app:app",host="127.0.0.1",port=8013)
