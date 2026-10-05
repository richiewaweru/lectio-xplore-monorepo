const fs=require('fs'),path=require('path');
const pw=require('C:/Projects/lectio/node_modules/.pnpm/playwright@1.62.1/node_modules/playwright');
const BASE='http://127.0.0.1:5189/dev/shared-lesson';const out=path.join(__dirname,'..','learn');
const L=[];const log=s=>{L.push(s);console.log(s)};
(async()=>{const b=await pw.chromium.launch();const p=await b.newPage({viewport:{width:1280,height:900}});
// 1. new lesson: native buttons, aria-pressed, Tab reachability, check feedback
await p.goto(`${BASE}/phase5-photosynthesis?dev=1`,{waitUntil:'networkidle'});
const info=await p.evaluate(()=>{const q=[...document.querySelectorAll('[data-question-number]')];return q.map(s=>({q:s.getAttribute('data-question-number'),type:s.getAttribute('data-interaction-type'),
 options:[...s.querySelectorAll('button.option')].map(o=>({tag:o.tagName,pressed:o.getAttribute('aria-pressed'),role:o.getAttribute('role')})),
 textareas:s.querySelectorAll('textarea,input[type=text]').length,buttons:[...s.querySelectorAll('button:not(.option)')].map(x=>x.innerText.trim()),header:(s.querySelector('.task-header')||{}).innerText}));});
log('INTERACTIONS '+JSON.stringify(info));
// keyboard on Q5
const q5=p.locator('[data-question-number="5"] button.option');await q5.nth(1).focus();
const desc=()=>p.evaluate(()=>{const e=document.activeElement;return `<${e.tagName.toLowerCase()}> "${(e.innerText||'').replace(/\s+/g,' ').trim().slice(0,40)}" aria-pressed=${e.getAttribute('aria-pressed')} role=${e.getAttribute('role')}`});
log('Q5 focus: '+await desc());await p.keyboard.press('Space');log('after Space: '+await desc());
await p.keyboard.press('Tab');log('Tab: '+await desc());
const tabs=[];for(let i=0;i<6;i++){tabs.push(await desc());await p.keyboard.press('Tab')}log('Tab sequence from Q5 option B: '+JSON.stringify(tabs));
await q5.nth(1).focus();await p.keyboard.press('Space');
const btn=p.locator('[data-question-number="5"]').getByRole('button',{name:/check my answer/i});await btn.click();await p.waitForTimeout(500);
const fb=await p.locator('[data-question-number="5"]').innerText();log('Q5 wrong-option feedback region text: '+JSON.stringify(fb));
await p.locator('[data-question-number="5"]').screenshot({path:path.join(out,'phase5-q5-wrong-feedback.png')});
await p.reload({waitUntil:'networkidle'});const q5b=p.locator('[data-question-number="5"] button.option');await q5b.nth(0).click();await p.locator('[data-question-number="5"]').getByRole('button',{name:/check my answer/i}).click();await p.waitForTimeout(500);
const fb2=await p.locator('[data-question-number="5"]').innerText();log('Q5 after choosing A: '+JSON.stringify(fb2));
await p.locator('[data-question-number="5"]').screenshot({path:path.join(out,'phase5-q5-right-feedback.png')});
// text task Q2
const ta=p.locator('[data-question-number="2"] textarea');
if(await ta.count()){await ta.fill('Because the soil and water were the same, something else must explain it.');
 const b2=p.locator('[data-question-number="2"]').getByRole('button').last();log('Q2 button: '+await b2.innerText());await b2.click();await p.waitForTimeout(500);
 log('Q2 after submit: '+JSON.stringify(await p.locator('[data-question-number="2"]').innerText()));
 await p.locator('[data-question-number="2"]').screenshot({path:path.join(out,'phase5-q2-feedback.png')});}
// 2. golden predict
await p.goto(`${BASE}/golden?dev=1`,{waitUntil:'networkidle'});
const g1=p.locator('[data-question-number="1"]');log('GOLDEN Q1 header: '+(await g1.locator('.task-header').innerText()).replace(/\s+/g,' '));
for(const i of [0,1]){await p.goto(`${BASE}/golden?dev=1`,{waitUntil:'networkidle'});const o=p.locator('[data-question-number="1"] button.option');await o.nth(i).click();
 await p.locator('[data-question-number="1"]').getByRole('button',{name:/lock in/i}).click();await p.waitForTimeout(400);
 const t=await p.locator('[data-question-number="1"]').innerText();log(`GOLDEN predict option ${i}: contains Correct=${/correct/i.test(t)} contains "Not yet"=${/not yet/i.test(t)} saved=${/saved/i.test(t)} :: ${JSON.stringify(t.replace(/\s+/g,' ').slice(-160))}`);}
// 3. legacy answers
await p.goto(`${BASE}/legacy?dev=1`,{waitUntil:'networkidle'});
const lq=await p.evaluate(()=>[...document.querySelectorAll('[data-question-number]')].map(s=>({q:s.getAttribute('data-question-number'),type:s.getAttribute('data-interaction-type'),options:s.querySelectorAll('button.option').length})));log('LEGACY tasks '+JSON.stringify(lq));
const lo=p.locator('[data-question-number="1"] button.option');log('legacy Q1 option count '+await lo.count());
for(let i=0;i<await lo.count();i++){await p.goto(`${BASE}/legacy?dev=1`,{waitUntil:'networkidle'});await p.locator('[data-question-number="1"] button.option').nth(i).click();
 await p.locator('[data-question-number="1"]').getByRole('button',{name:/check my answer|submit|check/i}).first().click();await p.waitForTimeout(300);
 const t=(await p.locator('[data-question-number="1"]').innerText()).replace(/\s+/g,' ');log(`legacy Q1 option ${i} -> ${t.slice(-80)}`);if(/correct\./i.test(t)&&!/not yet/i.test(t)){await p.locator('[data-question-number="1"]').screenshot({path:path.join(out,'legacy-q1-correct.png')});}else await p.locator('[data-question-number="1"]').screenshot({path:path.join(out,`legacy-q1-opt${i}.png`)});}
fs.writeFileSync(path.join(out,'interaction.log'),L.join('\n')+'\n');await b.close()})().catch(e=>{console.error(e);fs.writeFileSync(path.join(out,'interaction.log'),L.join('\n')+'\nERROR '+e.message+'\n');process.exit(1)});
