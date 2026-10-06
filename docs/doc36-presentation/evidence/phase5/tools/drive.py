import asyncio, json, sys, time, os
from pathlib import Path
import httpx
sys.path.insert(0, r"C:\Users\richi\.codex\worktrees\doc36-integration\lectio\apps\textbook-agent\backend\src")
sys.path.insert(0, r"C:\Users\richi\.codex\worktrees\doc36-integration\lectio\apps\textbook-agent\backend\scripts")
from run_whole_lesson_proof import ensure_proof_user, auth_headers  # reuses repo helpers
OUT=Path(r"C:\Users\richi\.codex\worktrees\doc36-integration\lectio\docs\doc36-presentation\evidence\phase5")
RUNS={
 "photosynthesis":dict(subject="Science",grade_level="Grade 5",title="How Plants Get the Energy to Grow",topic="How plants get the energy to grow (photosynthesis)",destination_objective="Explain how plants use light, water and carbon dioxide to make the food they need to grow.",starting_knowledge=["plants have roots, stems and leaves","living things need food to grow"]),
 "area":dict(subject="Mathematics",grade_level="Grade 6",title="Area of Rectangles and Compound Shapes",topic="Area of rectangles and compound shapes",destination_objective="Use the formula area = length x width to find the area of rectangles and of compound shapes made from rectangles.",starting_knowledge=["can multiply whole numbers","know that area is measured in square units"]),
 "compare":dict(subject="Science",grade_level="Grade 8",title="Photosynthesis and Respiration Compared",topic="Photosynthesis versus respiration",destination_objective="Compare photosynthesis and respiration: what goes in, what comes out, where and when each happens, and how they connect.",starting_knowledge=["plants make food using light","living things release energy from food"]),
}
KEY={"photosynthesis":{"photosynth":4,"equation":2,"together":2,"food":1},"area":{"compound":4,"area":3,"formula":2,"rectangle":1},"compare":{"compar":4,"respiration":4,"photosynth":2,"contrast":3}}
async def main(slug):
    spec=RUNS[slug]; d=OUT/f"fullrun-{slug}"; d.mkdir(parents=True,exist_ok=True)
    log=[]; 
    def L(m):
        line=f"[{time.strftime('%H:%M:%S')}] {m}"; print(line,flush=True); log.append(line)
        (d/"driver-log.txt").write_text("\n".join(log)+"\n",encoding="utf-8")
    def W(name,obj): (d/name).write_text(json.dumps(obj,indent=2,default=str),encoding="utf-8")
    t_start=time.time(); (d/"start.json").exists() and None; W("start.json",{"ts":t_start,"spec":spec})
    user=await ensure_proof_user(); h=auth_headers(user)
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8015",headers=h,timeout=httpx.Timeout(connect=30,read=1500,write=60,pool=30),limits=httpx.Limits(max_keepalive_connections=0)) as c:
        def chk(r):
            if not r.is_success: raise RuntimeError(f"{r.request.method} {r.request.url} {r.status_code} {r.text[:600]}")
            return r.json()
        if len(sys.argv)>3:  # resume on an existing planned unit: uid, title-substring
            uid=sys.argv[2]; sub=sys.argv[3].lower()
            ap=chk(await c.get(f"/api/v1/units/{uid}/path")); W("03-path-approved.json",ap)
            lessons=[l for l in ap["lessons"] if not l.get("skipped")]
            lesson=next(l for l in lessons if sub in str(l.get("title","")).lower()); lid=lesson["id"]
            L(f"resume unit {uid} lesson {lid} title={lesson.get('title')}")
        else:
            unit=chk(await c.post("/api/v1/units",json=spec)); uid=unit["id"]; L(f"unit {uid}"); W("01-unit.json",unit)
            pp={k:spec[k] for k in("topic","subject","grade_level","destination_objective","starting_knowledge")}
            path=chk(await c.post(f"/api/v1/units/{uid}/path:plan",json=pp)); W("02-path.json",path)
            L(f"path lessons={[ (l.get('title') or l.get('objective'))[:80] for l in path.get('lessons',[])]}")
            if os.environ.get("STOP_AFTER_PLAN"): return
            ap=chk(await c.post(f"/api/v1/units/{uid}/path:approve",json={"path_version_id":path["id"],"path_revision":path["revision"]})); W("03-path-approved.json",ap)
            lessons=[l for l in ap["lessons"] if not l.get("skipped")]
            kw=KEY[slug]
            def score(l):
                t=(str(l.get("title",""))+" "+str(l.get("objective",""))).lower()
                return sum(w for k,w in kw.items() if k in t)
            lesson=max(lessons,key=score); lid=lesson["id"]; L(f"picked lesson score={score(lesson)} title={lesson.get('title')}")
        if len(sys.argv)>4:
            gid=sys.argv[4]; L(f"resume generation {gid}")
            if os.environ.get("REGEN"):
                stt=(await c.get(f"/api/v1/units/{uid}/path/lessons/{lid}/status")).json(); rid=stt["workspace"]["preparation"]["run_id"]
                rg=await c.post(f"/api/v1/generation/runs/{rid}/retry",json={"work_item_ids":stt["workspace"]["preparation"]["progress"]["failed_work_item_ids"]}); L(f"retry run {rid} {rg.status_code} {rg.text[:200]}")
        else:
            prep=chk(await c.post(f"/api/v1/units/{uid}/path/lessons/{lid}:prepare",json={"path_version_id":ap["id"],"path_revision":ap["revision"],"lesson_revision":lesson["revision"],"lesson_mode":"first_exposure","group_ids":[]})); W("04-prepare.json",prep)
            gid=prep.get("generation_id") or prep.get("pack_id"); L(f"generation {gid}")
            chk(await c.post(f"/api/v1/preparations/{gid}/plan",json={}))
        teaching=None; last=""
        for i in range(360):
            r=await c.get(f"/api/v1/units/{uid}/path/lessons/{lid}/status"); b=r.json() if r.status_code==200 else {}
            st=str(b.get("workflow_stage") or ""); ps=(b.get("workspace") or {}).get("preparation",{}).get("state")
            key=f"{st}/{ps}"
            if key!=last: L(f"stage {key}"); last=key
            if st in {"awaiting_teaching_approval","teaching_ready"}:
                la=await c.get(f"/api/v1/v3/generations/{gid}/lesson-approach")
                if la.status_code==200: teaching=la.json(); break
            if ps=="awaiting_review" and (b.get("workspace") or {}).get("preparation",{}).get("review_kind")=="teaching_plan":
                la=await c.get(f"/api/v1/v3/generations/{gid}/lesson-approach")
                if la.status_code==200: teaching=la.json(); break
            if "fail" in str(ps) or "blocked" in st:
                W("status-failed.json",b); raise RuntimeError(f"prep failed {key}")
            await asyncio.sleep(5)
        W("05-teaching-plan.json",teaching)
        rev=(teaching.get("teaching_review") or {}).get("revision") or 1
        ta=await c.post(f"/api/v1/v3/generations/{gid}/lesson-approach/approve?path=learn",json={"expected_revision":rev,"expected_content_hash":(teaching.get("teaching_plan_identity") or {}).get("pending_content_hash"),"teacher_note":"doc36 Track C full-run evidence"})
        L(f"teaching approve {ta.status_code} {ta.text[:300]}")
        if not ta.is_success: raise RuntimeError("teaching approve failed") 
        pg=chk(await c.get(f"/api/v1/units/{uid}/path")); lesson=next(l for l in pg["lessons"] if l["id"]==lid)
        t_gen=time.time()
        gl=await c.post(f"/api/v1/units/{uid}/path/lessons/{lid}/realizations:generate-learn",json={"path_version_id":pg["id"],"path_revision":pg["revision"],"lesson_revision":lesson["revision"]},timeout=1500)
        L(f"generate-learn {gl.status_code} after {time.time()-t_gen:.0f}s")
        try: body=gl.json()
        except Exception: body={"text":gl.text}
        W("06-generate-learn.json",body)
        W("end.json",{"ts":time.time(),"unit_id":uid,"lesson_id":lid,"generation_id":gid,"generate_learn_status":gl.status_code,"started":t_start})
asyncio.run(main(sys.argv[1]))
