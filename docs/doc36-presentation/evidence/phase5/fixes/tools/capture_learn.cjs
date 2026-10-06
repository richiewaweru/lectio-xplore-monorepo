// Phase 5 fixes Learn capture: dev fixture route (lesson never reached READY, so no stored document exists for the real route).
const fs=require('fs'),path=require('path');
const pw=require('C:/Projects/lectio/node_modules/.pnpm/playwright@1.62.1/node_modules/playwright');
const BASE='http://127.0.0.1:5190/dev/shared-lesson';const out=path.join(__dirname,'..','learn');fs.mkdirSync(out,{recursive:true});
const SECTION_IDS=['orient','criteria','contrast','apply','check'];
const report={};
(async()=>{const b=await pw.chromium.launch();
for(const f of ['phase5-photosynthesis','legacy','golden']){
 for(const [w,h] of [[1280,900],[390,844]]){
  const p=await b.newPage({viewport:{width:w,height:h}});
  await p.goto(`${BASE}/${f}?dev=1`,{waitUntil:'networkidle'});await p.waitForTimeout(600);
  await p.screenshot({path:path.join(out,`${f}-learn-${w}.png`),fullPage:true});
  const r=await p.evaluate((SECTION_IDS)=>{
   const vis=document.body.innerText;
   const bad=[];
   const rx=[/shared-node-/i,/shared-task/i,/\btask-[a-z0-9]/i,/shared-key-idea/i,/shared-figure/i,/\bchoice-\d/i,/\bV2\b/,/\bnodes?\b/i,/document\s*·/i];
   for(const r of rx){const m=vis.match(r);if(m)bad.push({where:'visible-text',pattern:String(r),match:m[0]})}
   for(const id of SECTION_IDS){if(new RegExp('^\s*'+id+'\s*$','im').test(vis))bad.push({where:'visible-text',pattern:'section id line',match:id})}
   const attrBad=[];
   for(const el of document.querySelectorAll('main *')){for(const a of el.attributes){
     if(a.name==='class'||a.name==='style')continue;
     for(const r of [/shared-node-/i,/shared-task/i,/\btask-[a-z0-9]/i,/shared-key-idea/i,/shared-figure/i,/\bchoice-\d/i,/\bV2\b/]){if(r.test(a.value))attrBad.push({tag:el.tagName.toLowerCase(),attr:a.name,value:a.value.slice(0,80)})}
     if(['id','href','aria-label','aria-labelledby','aria-controls','title','alt','for','name'].includes(a.name)&&SECTION_IDS.some(s=>a.value===s||a.value==='#'+s))attrBad.push({tag:el.tagName.toLowerCase(),attr:a.name,value:a.value})
   }}
   const nodes=[...document.querySelectorAll('[data-testid="canvas-node"]')].map(n=>({kind:n.getAttribute('data-kind'),text:[...n.querySelectorAll('p, li, td, th, h2, h3, h4, header, figcaption, strong, label, button, textarea')].length?n.innerText:n.innerText}));
   const paras=[...document.querySelectorAll('[data-testid="canvas-node"][data-kind="paragraph"] .learn-paragraph')].map(el=>[...el.querySelectorAll(':scope > p')].map(p=>p.innerText.trim()));
   return {scrollW:document.documentElement.scrollWidth,innerW:innerWidth,hscroll:document.documentElement.scrollWidth>innerWidth,bad,attrBad,
     literal:{bold:/\*\*/.test(vis),tilde:/~/.test(vis),caret:/\^/.test(vis)},
     counts:{canvasNodes:nodes.length,taskHeaders:document.querySelectorAll('.task-header').length,ol:document.querySelectorAll('ol').length,strong:document.querySelectorAll('main strong').length,sub:document.querySelectorAll('main sub').length,sup:document.querySelectorAll('main sup').length,paragraphsBlocksSplit:paras},
     sectionHeaders:[...document.querySelectorAll('.section-header')].map(h=>h.innerText.replace(/\s+/g,' ')),
     tabs:[...document.querySelectorAll('nav.lesson-map button, nav.lesson-map a')].map(x=>x.innerText.replace(/\s+/g,' ')),
     fontPx:getComputedStyle(document.querySelector('.learn-paragraph p, .learn-paragraph')||document.body).fontSize,
     blocks:nodes};
  },SECTION_IDS);
  report[`${f}@${w}`]=r;
  console.log(f,w,'hscroll',r.hscroll,'bad',r.bad.length,'attrBad',r.attrBad.length,'literal',JSON.stringify(r.literal));
  await p.close();
 }
}
fs.writeFileSync(path.join(out,'learn-dom-report.json'),JSON.stringify(report,null,1));
await b.close();})().catch(e=>{console.error(e);process.exit(1)});
