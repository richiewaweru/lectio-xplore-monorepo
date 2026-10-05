// Integration capture: golden Learn at 1280/390, keyboard traversal, question numbers. Needs vite dev on :5188.
const fs=require('fs'),path=require('path');
const pw=require('C:/Projects/lectio/node_modules/.pnpm/playwright@1.62.1/node_modules/playwright');
const BASE='http://127.0.0.1:5188/dev/shared-lesson';const out=path.join(__dirname,'images');fs.mkdirSync(out,{recursive:true});
const lines=[];const log=s=>{lines.push(s);console.log(s)};
(async()=>{const b=await pw.chromium.launch();
for(const [w,h] of [[1280,900],[390,844]]){
 const p=await b.newPage({viewport:{width:w,height:h}});
 for(const f of ['golden','legacy']){await p.goto(`${BASE}/${f}?dev=1`,{waitUntil:'networkidle'});
  await p.waitForTimeout(500);await p.screenshot({path:path.join(out,`${f}-learn-${w}.png`),fullPage:true});log(`${f} @${w}: images/${f}-learn-${w}.png`);
  log(`${f} @${w} data-question-number: ${JSON.stringify(await p.$$eval('[data-question-number]',e=>e.map(x=>x.getAttribute('data-question-number'))))}`);
  log(`${f} @${w} task headers: ${await p.locator('.task-header').count()}  horizontal overflow: ${await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth)}`);}
 await p.close();}
// keyboard traversal
const p=await b.newPage({viewport:{width:1280,height:900}});
await p.goto(`${BASE}/golden?dev=1`,{waitUntil:'networkidle'});
const desc=()=>p.evaluate(()=>{const e=document.activeElement;return `<${e.tagName.toLowerCase()}> "${(e.innerText||'').replace(/\s+/g,' ').trim().slice(0,60)}" aria-pressed=${e.getAttribute('aria-pressed')} disabled=${e.disabled} role=${e.getAttribute('role')}`});
const first=p.locator('[data-question-number="1"] button.option').first();await first.focus();log('KEYBOARD golden');
const seen=[];
for(let i=0;i<14;i++){const d=await desc();seen.push(d);log(`${i+1}. ${d}`);
 if(/button/.test(d)&&/aria-pressed=false/.test(d)&&i%3==0){await p.keyboard.press('Space');log('   (Space) -> '+await desc());}
 await p.keyboard.press('Tab');}
await p.screenshot({path:path.join(out,'golden-keyboard-focus.png')});
log(`options with aria-pressed seen: ${seen.filter(s=>/aria-pressed=(true|false)/.test(s)).length}; any radio role: ${seen.some(s=>/role=radio/.test(s))}`);
await b.close();fs.writeFileSync(path.join(__dirname,'learn-capture.log'),lines.join('\n')+'\n');})().catch(e=>{console.error(e);process.exit(1)});
