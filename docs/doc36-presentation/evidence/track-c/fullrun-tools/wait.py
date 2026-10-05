import asyncio, json, sys, time, httpx
sys.path.insert(0, r"C:\Users\richi\.codex\worktrees\doc36-writer\lectio\apps\textbook-agent\backend\src")
sys.path.insert(0, r"C:\Users\richi\.codex\worktrees\doc36-writer\lectio\apps\textbook-agent\backend\scripts")
from run_whole_lesson_proof import ensure_proof_user, auth_headers
from pathlib import Path
OUT=Path(r"C:\Users\richi\.codex\worktrees\doc36-writer\lectio\docs\doc36-presentation\evidence\track-c")
slug,uid,lid=sys.argv[1:4]; want=sys.argv[4] if len(sys.argv)>4 else None; d=OUT/f"fullrun-{slug}"
async def main():
    u=await ensure_proof_user(); last=None; hist=[]
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8013",headers=auth_headers(u),timeout=60,limits=httpx.Limits(max_keepalive_connections=0)) as c:
        for i in range(400):
            try: b=(await c.get(f"/api/v1/units/{uid}/path/lessons/{lid}/status")).json()
            except Exception as e: await asyncio.sleep(5); continue
            L=b["workspace"]["learn"]; key=(L["state"],L.get("shared_document_state"),json.dumps(L.get("progress"),sort_keys=True))
            if key!=last:
                last=key; hist.append({"t":time.time(),"learn":L}); (d/f"learn-status-history{sys.argv[5] if len(sys.argv)>5 else ''}.json").write_text(json.dumps(hist,indent=1),encoding="utf-8")
                print(time.strftime("%H:%M:%S"),L["state"],L.get("shared_document_state"),json.dumps(L.get("progress")),flush=True)
            if L["state"] in ("ready","failed","failed_recoverable","failed_terminal") and (want is None or L.get("shared_document_run_id")==want):
                (d/"end.json").write_text(json.dumps({"ts":time.time(),"unit_id":uid,"lesson_id":lid,"learn":L,"status":b},indent=1),encoding="utf-8"); return
            await asyncio.sleep(10)
asyncio.run(main())
