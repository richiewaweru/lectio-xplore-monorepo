import asyncio, json, sys, httpx, time
sys.path.insert(0, r"C:\Users\richi\.codex\worktrees\doc36-integration\lectio\apps\textbook-agent\backend\src")
sys.path.insert(0, r"C:\Users\richi\.codex\worktrees\doc36-integration\lectio\apps\textbook-agent\backend\scripts")
from run_whole_lesson_proof import ensure_proof_user, auth_headers
from pathlib import Path
OUT=Path(r"C:\Users\richi\.codex\worktrees\doc36-integration\lectio\docs\doc36-presentation\evidence\phase5")
slug,uid,lid=sys.argv[1:4]
async def main():
    u=await ensure_proof_user()
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8015",headers=auth_headers(u),timeout=300,limits=httpx.Limits(max_keepalive_connections=0)) as c:
        st=(await c.get(f"/api/v1/units/{uid}/path/lessons/{lid}/status")).json()
        rid=st["workspace"]["learn"]["realization_id"]
        pg=(await c.get(f"/api/v1/units/{uid}/path")).json()
        r=await c.post(f"/api/v1/units/{uid}/path/lessons/{lid}/realizations/{rid}:retry",json={"path_version_id":pg["id"],"path_revision":pg["revision"]})
        print(slug,r.status_code,r.text[:400])
        (OUT/f"fullrun-{slug}"/"retry-response.json").write_text(json.dumps({"ts":time.time(),"status":r.status_code,"body":r.text[:3000]},indent=1))
asyncio.run(main())
