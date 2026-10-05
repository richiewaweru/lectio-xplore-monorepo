// Phase 5 fixes: proof for L2 (lesson-map chips), L8 (correct icon), L10 (match-pairs aria-pressed).
const fs=require('fs'),path=require('path');
const pw=require('C:/Projects/lectio/node_modules/.pnpm/playwright@1.62.1/node_modules/playwright');
const BASE='http://127.0.0.1:5190/dev/shared-lesson';const out=path.join(__dirname,'..','learn');
const L=[];const log=s=>{L.push(s);console.log(s)};
(async()=>{const b=await pw.chromium.launch();
for(const [w,h] of [[1280,900],[390,844]]){
 const p=await b.newPage({viewport:{width:w,height:h}});
 await p.goto(`${BASE}/phase5-photosynthesis?dev=1`,{waitUntil:'networkidle'});await p.waitForTimeout(500);
 const map=p.locator('nav.lesson-map');await map.screenshot({path:path.join(out,`lesson-map-${w}.png`)});
 const r=await p.evaluate(()=>{const items=[...document.querySelectorAll('nav.lesson-map li button')];
  return {hscroll:document.documentElement.scrollWidth>innerWidth,scrollW:document.documentElement.scrollWidth,innerW:innerWidth,
   items:items.map(b=>{const s=b.lastElementChild;const bb=b.getBoundingClientRect(),sb=s.getBoundingClientRect();return {text:s.innerText,overflowX:s.scrollWidth>s.clientWidth,textRightInsideButton:sb.right<=bb.right-8,btnW:Math.round(bb.width),btnH:Math.round(bb.height)}})}});
 log(`lesson-map @${w}: hscroll=${r.hscroll} (${r.scrollW}/${r.innerW}) ${JSON.stringify(r.items)}`);
 await p.close();
}
// match-pairs (first task of the lesson)
const p=await b.newPage({viewport:{width:1280,height:900}});
await p.goto(`${BASE}/phase5-photosynthesis?dev=1`,{waitUntil:'networkidle'});
const mq=p.locator('[data-interaction-type="match-pairs"]').first();
const states=async()=>mq.evaluate(el=>[...el.querySelectorAll('ul.col button')].map(x=>`${x.tagName}:${x.innerText.trim().slice(0,18)}:${x.getAttribute('aria-pressed')}`));
log('match-pairs before: '+JSON.stringify(await states()));
const lefts=mq.locator('ul.col').nth(0).locator('button'),rights=mq.locator('ul.col').nth(1).locator('button');
await lefts.nth(0).click();log('after clicking left 1: '+JSON.stringify(await states()));
await mq.screenshot({path:path.join(out,'match-pairs-left-selected.png')});
await rights.nth(0).click();
for(let i=1;i<3;i++){await lefts.nth(i).click();await rights.nth(i).click();}
log('after three matches: '+JSON.stringify(await states()));
await mq.screenshot({path:path.join(out,'match-pairs-all-matched.png')});
await mq.getByRole('button',{name:/check my answer/i}).click();await p.waitForTimeout(400);
const fb=await mq.locator('.feedback').first().evaluate(f=>({outcome:f.getAttribute('data-outcome'),icon:!!f.querySelector('svg.feedback-icon'),text:f.innerText.trim().slice(0,80),iconFill:f.querySelector('circle')&&f.querySelector('circle').getAttribute('fill'),bg:getComputedStyle(f).backgroundColor}));
log('match-pairs feedback: '+JSON.stringify(fb));
await mq.screenshot({path:path.join(out,'match-pairs-feedback.png')});
fs.writeFileSync(path.join(out,'fixes.log'),L.join('\n')+'\n');await b.close()})().catch(e=>{console.error(e);process.exit(1)});
