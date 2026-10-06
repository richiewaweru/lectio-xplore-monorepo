import asyncio, json, sys, datetime
from pathlib import Path
sys.path.insert(0, r"C:\Users\richi\.codex\worktrees\doc36-integration\lectio\apps\textbook-agent\backend\src")
from sqlalchemy import select, text
from core.database.session import async_session_factory
from infra.database.models import SharedLessonDocumentModel, GenerationWorkItemModel, GenerationRunModel, GenerationEventModel, GenerationBuildModel
OUT=Path(r"C:\Users\richi\.codex\worktrees\doc36-integration\lectio\docs\doc36-presentation\evidence\phase5")
slug=sys.argv[1]; d=OUT/f"fullrun-{slug}"
end=json.loads((d/"end.json").read_text()) if (d/"end.json").exists() else {}
start=json.loads((d/"start.json").read_text())
lid=sys.argv[2]
def dump(o): return json.loads(json.dumps(o,default=str))
async def main():
    async with async_session_factory() as s:
        docs=(await s.execute(select(SharedLessonDocumentModel).where(SharedLessonDocumentModel.path_lesson_id==lid))).scalars().all()
        (d/"shared-documents-all-revisions.json").write_text(json.dumps([dict(id=x.id,revision=x.revision,status=x.status,content_hash=x.content_hash,created_at=str(x.created_at)) for x in docs],indent=2))
        if docs:
            x=sorted(docs,key=lambda x:x.revision)[-1]
            (d/"shared-document.json").write_text(json.dumps(x.document_json,indent=2,default=str),encoding="utf-8")
        t0=datetime.datetime.utcfromtimestamp(start["ts"]-5)
        builds=[b for (b,) in (await s.execute(select(GenerationBuildModel.id).where(GenerationBuildModel.path_lesson_id==lid)))]
        runs=(await s.execute(select(GenerationRunModel).where(GenerationRunModel.build_id.in_(builds)).order_by(GenerationRunModel.created_at))).scalars().all()
        runs_out=[]; wi_out=[]; ev_out=[]
        for r in runs:
            runs_out.append({c.name:str(getattr(r,c.name)) for c in GenerationRunModel.__table__.columns})
            items=(await s.execute(select(GenerationWorkItemModel).where(GenerationWorkItemModel.run_id==r.id))).scalars().all()
            for it in items:
                wi_out.append({c.name:(dump(getattr(it,c.name)) if c.name.endswith("_json") else str(getattr(it,c.name))) for c in GenerationWorkItemModel.__table__.columns})
            evs=(await s.execute(select(GenerationEventModel).where(GenerationEventModel.run_id==r.id).order_by(GenerationEventModel.seq))).scalars().all()
            for e in evs:
                ev_out.append({c.name:(dump(getattr(e,c.name)) if c.name.endswith("_json") else str(getattr(e,c.name))) for c in GenerationEventModel.__table__.columns})
        (d/"runs.json").write_text(json.dumps(runs_out,indent=2),encoding="utf-8")
        (d/"work-items.json").write_text(json.dumps(wi_out,indent=2),encoding="utf-8")
        (d/"events.json").write_text(json.dumps(ev_out,indent=2),encoding="utf-8")
        print(len(docs),"docs",len(runs_out),"runs",len(wi_out),"items",len(ev_out),"events")
asyncio.run(main())
