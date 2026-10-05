// G4 browser proof (real Chromium via the repo's existing Playwright install).
// Needs the dev frontend on 127.0.0.1:5188 (vite dev). Writes PNGs to ./images and a log.
// node g4_browser_proof.cjs [playwright-module-path]
const fs = require('fs'); const path = require('path');
const pw = require(process.argv[2] || 'C:/Projects/lectio/node_modules/.pnpm/playwright@1.62.1/node_modules/playwright');
const BASE = 'http://127.0.0.1:5188/dev/shared-lesson';
const out = path.join(__dirname, 'images'); const lines = [];
const log = (s) => { lines.push(s); console.log(s); };
async function task(p, n) { return p.locator(`[data-question-number="${n}"]`); }
async function shot(p, n, name) {
  const t = await task(p, n); await t.scrollIntoViewIfNeeded();
  await t.screenshot({ path: path.join(out, name) }); log(`  screenshot images/${name}`);
}
(async () => {
  const b = await pw.chromium.launch(); const p = await b.newPage({ viewport: { width: 1280, height: 1000 } });
  log(`G4 browser proof ${new Date().toISOString()}`);

  // 1. golden prediction -> saved message, never Correct / Not yet
  await p.goto(`${BASE}/golden?dev=1`, { waitUntil: 'networkidle' });
  let t = await task(p, 1);
  log(`golden Q1 prompt: ${(await t.locator('p,h2,h3,legend').first().innerText()).trim()}`);
  await shot(p, 1, 'golden-predict-1-before.png');
  await t.getByText(/captures its growing energy from the light/).click();
  await shot(p, 1, 'golden-predict-2-selected.png');
  const lock = t.getByRole('button', { name: 'Lock in my prediction' });
  log(`  submit label: "Lock in my prediction"; enabled after selecting: ${await lock.isEnabled()}`);
  await lock.click(); await p.waitForTimeout(800);
  await shot(p, 1, 'golden-predict-3-saved.png');
  const txt = await t.innerText();
  const bad = /\bCorrect\b|Not yet|Incorrect|Try again/i.test(txt);
  log(`  after submit task text: ${JSON.stringify(txt.replace(/\s+/g, ' ').slice(-220))}`);
  log(`  shows "Prediction saved": ${/Prediction saved/.test(txt)}`);
  log(`  RESULT predict never shows Correct/Not yet: ${!bad ? 'PASS' : 'FAIL'}`);
  // Also try the other (wrong-per-evaluation) option on a fresh load: still no grading.
  await p.goto(`${BASE}/golden?dev=1`, { waitUntil: 'networkidle' });
  t = await task(p, 1);
  await t.getByText(/takes in its growing energy from the soi/).click();
  await t.getByRole('button', { name: 'Lock in my prediction' }).click(); await p.waitForTimeout(800);
  await shot(p, 1, 'golden-predict-4-other-option-saved.png');
  const txt2 = await t.innerText();
  log(`  other option -> saved: ${/Prediction saved/.test(txt2)}; graded text present: ${/\bCorrect\b|Not yet|Incorrect/i.test(txt2)}`);
  log(`  RESULT predict (other option) neutral: ${!/\bCorrect\b|Not yet|Incorrect/i.test(txt2) ? 'PASS' : 'FAIL'}`);

  // 2. legacy role-absent tasks still render and answer
  await p.goto(`${BASE}/legacy?dev=1`, { waitUntil: 'networkidle' });
  t = await task(p, 1);
  await shot(p, 1, 'legacy-1-before.png');
  await t.getByText(/captures its growing energy from the light/).click();
  await t.getByRole('button', { name: 'Check' }).click(); await p.waitForTimeout(800);
  await shot(p, 1, 'legacy-2-correct-answer.png');
  const l1 = await t.innerText();
  log(`legacy Q1 correct answer -> contains "Correct.": ${/Correct\./.test(l1)}`);
  await p.goto(`${BASE}/legacy?dev=1`, { waitUntil: 'networkidle' });
  t = await task(p, 1);
  await t.getByText(/takes in its growing energy from the soi/).click();
  await t.getByRole('button', { name: 'Check' }).click(); await p.waitForTimeout(800);
  await shot(p, 1, 'legacy-3-wrong-answer.png');
  const l2 = await t.innerText();
  log(`legacy Q1 wrong answer -> contains "Not yet": ${/Not yet/.test(l2)}`);
  log(`  RESULT legacy renders and answers: ${/Correct\./.test(l1) && /Not yet/.test(l2) ? 'PASS' : 'FAIL'}`);

  // 3. Q numbers rendered by Learn
  for (const f of ['golden', 'legacy']) {
    await p.goto(`${BASE}/${f}?dev=1`, { waitUntil: 'networkidle' });
    log(`Learn ${f} data-question-number sequence: ${JSON.stringify(await p.$$eval('[data-question-number]', e => e.map(x => 'Q' + x.getAttribute('data-question-number'))))}`);
  }
  await b.close();
  fs.writeFileSync(path.join(__dirname, 'integration-browser-proof.log'), lines.join('\n') + '\n');
})().catch((e) => { console.error(e); process.exit(1); });
