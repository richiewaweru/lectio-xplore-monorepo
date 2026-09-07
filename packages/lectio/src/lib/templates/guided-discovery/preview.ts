import type { TemplatePreview } from '$lib/templates/types';
import type { SectionContent } from '$lib/schema/types';

const probabilityTreeSvg = `<svg viewBox="0 0 400 260" xmlns="http://www.w3.org/2000/svg" class="w-full h-auto">
  <!-- Root -->
  <circle cx="40" cy="130" r="10" fill="hsl(213 37% 17% / 0.15)" stroke="hsl(213 37% 17% / 0.4)" stroke-width="2"/>
  <text x="40" y="134" text-anchor="middle" font-size="9" fill="hsl(213 37% 17%)">Start</text>

  <!-- Branch 1: Heads -->
  <line x1="50" y1="125" x2="150" y2="60" stroke="hsl(24 95% 53%)" stroke-width="2"/>
  <text x="95" y="82" text-anchor="middle" font-size="10" fill="hsl(24 95% 53%)">H (½)</text>
  <circle cx="155" cy="55" r="8" fill="hsl(24 95% 53% / 0.15)" stroke="hsl(24 95% 53%)" stroke-width="1.5"/>

  <!-- Branch 2: Tails -->
  <line x1="50" y1="135" x2="150" y2="200" stroke="hsl(213 37% 50%)" stroke-width="2"/>
  <text x="95" y="178" text-anchor="middle" font-size="10" fill="hsl(213 37% 50%)">T (½)</text>
  <circle cx="155" cy="205" r="8" fill="hsl(213 37% 50% / 0.15)" stroke="hsl(213 37% 50%)" stroke-width="1.5"/>

  <!-- Sub-branches from Heads -->
  <line x1="163" y1="50" x2="260" y2="25" stroke="hsl(24 95% 53% / 0.6)" stroke-width="1.5"/>
  <text x="210" y="30" text-anchor="middle" font-size="9" fill="hsl(24 95% 53%)">H (½)</text>
  <rect x="265" y="12" width="55" height="24" rx="6" fill="hsl(24 95% 53% / 0.12)" stroke="hsl(24 95% 53% / 0.4)" stroke-width="1"/>
  <text x="292" y="28" text-anchor="middle" font-size="9" font-weight="bold" fill="hsl(24 95% 53%)">HH: ¼</text>

  <line x1="163" y1="60" x2="260" y2="80" stroke="hsl(213 37% 50% / 0.6)" stroke-width="1.5"/>
  <text x="210" y="78" text-anchor="middle" font-size="9" fill="hsl(213 37% 50%)">T (½)</text>
  <rect x="265" y="68" width="55" height="24" rx="6" fill="hsl(213 37% 17% / 0.06)" stroke="hsl(213 37% 17% / 0.2)" stroke-width="1"/>
  <text x="292" y="84" text-anchor="middle" font-size="9" fill="hsl(213 37% 17% / 0.7)">HT: ¼</text>

  <!-- Sub-branches from Tails -->
  <line x1="163" y1="200" x2="260" y2="180" stroke="hsl(24 95% 53% / 0.6)" stroke-width="1.5"/>
  <text x="210" y="183" text-anchor="middle" font-size="9" fill="hsl(24 95% 53%)">H (½)</text>
  <rect x="265" y="168" width="55" height="24" rx="6" fill="hsl(213 37% 17% / 0.06)" stroke="hsl(213 37% 17% / 0.2)" stroke-width="1"/>
  <text x="292" y="184" text-anchor="middle" font-size="9" fill="hsl(213 37% 17% / 0.7)">TH: ¼</text>

  <line x1="163" y1="210" x2="260" y2="235" stroke="hsl(213 37% 50% / 0.6)" stroke-width="1.5"/>
  <text x="210" y="232" text-anchor="middle" font-size="9" fill="hsl(213 37% 50%)">T (½)</text>
  <rect x="265" y="222" width="55" height="24" rx="6" fill="hsl(213 37% 50% / 0.12)" stroke="hsl(213 37% 50% / 0.4)" stroke-width="1"/>
  <text x="292" y="238" text-anchor="middle" font-size="9" font-weight="bold" fill="hsl(213 37% 50%)">TT: ¼</text>

  <!-- Summary -->
  <text x="360" y="130" text-anchor="middle" font-size="11" font-weight="600" fill="hsl(213 37% 17% / 0.5)">4 outcomes</text>
  <text x="360" y="148" text-anchor="middle" font-size="10" fill="hsl(213 37% 17% / 0.4)">each ¼</text>
</svg>`;

const discoveryMathSection: SectionContent = {
	section_id: 'disc-math-01',
	template_id: 'guided-discovery',

	header: {
		title: 'Probability of Compound Events',
		subtitle: 'When two things happen in sequence — how do the odds combine?',
		subject: 'Mathematics',
		grade_band: 'secondary',
		objectives: ['Use tree diagrams and the multiplication rule to calculate compound probabilities'],
	},

	hook: {
		headline: 'If you flip two coins, why is getting two heads not twice as hard as getting one?',
		body: "One coin, one flip — the chance of heads is ½. Simple. But what about two coins? You might think two heads is ½ again, or maybe ½ of ½. The answer isn't obvious until you see all the possible paths the outcomes can take.",
		anchor: 'the multiplication rule for independent events',
	},

	explanation: {
		body: "When two events are independent — meaning the outcome of one doesn't affect the other — the probability of both happening is the product of their individual probabilities. This is the multiplication rule: P(A and B) = P(A) × P(B). For two coin flips, each flip has P(H) = ½, so P(HH) = ½ × ½ = ¼. A probability tree makes this visible: each branch splits the sample space, and the final probability of any path is the product of probabilities along that path. With two coins, there are four equally likely paths: HH, HT, TH, and TT — each with probability ¼.",
		emphasis: ['multiplication rule', 'P(A) × P(B)', 'independent'],
		callouts: [
			{
				type: 'insight',
				text: 'The tree diagram is not just a teaching aid — it is the formal definition of how compound sample spaces work. Every probability textbook builds on this structure.',
			},
			{
				type: 'remember',
				text: 'Independent events multiply. If events affect each other (dependent), you need conditional probability instead.',
			},
		],
	},

	definition: {
		term: 'Multiplication Rule (Independent Events)',
		formal:
			'For independent events A and B, P(A ∩ B) = P(A) · P(B). Events are independent if the occurrence of one does not change the probability of the other.',
		plain: 'When two things happen separately and neither affects the other, multiply their probabilities to find the chance of both happening.',
		examples: [
			'P(two heads) = P(H) × P(H) = ½ × ½ = ¼',
			'P(rolling 6 then drawing an ace) = 1/6 × 4/52 = 4/312 ≈ 0.013',
		],
		related_terms: ['Independent Events', 'Conditional Probability', 'Sample Space'],
	},

	simulation: {
		explanation:
			'Build your own probability tree by choosing events. Watch the compound probabilities calculate as branches grow.',
		html_content: `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;background:#eff6ff;color:#1e293b;padding:16px;display:flex;flex-direction:column;gap:12px;height:100vh;overflow:hidden}
.controls{display:flex;flex-wrap:wrap;gap:14px;align-items:end}
.ctrl{display:flex;flex-direction:column;gap:4px}
.ctrl label{font-size:12px;font-weight:600;color:#475569}
.ctrl label span{color:#2563eb;font-variant-numeric:tabular-nums}
input[type=range]{width:140px;accent-color:#2563eb;height:5px;cursor:pointer}
.flip-btns{display:flex;gap:6px}
.flip-btns button{padding:4px 14px;border-radius:999px;border:1.5px solid #bfdbfe;background:#fff;color:#1e40af;font:inherit;font-size:12px;font-weight:600;cursor:pointer;transition:all .15s}
.flip-btns button.active{background:#2563eb;color:#fff;border-color:#2563eb}
.flip-btns button:hover{border-color:#60a5fa}
svg{flex:1;min-height:0}
.summary{display:flex;gap:16px;font-size:13px;color:#475569;justify-content:center;flex-wrap:wrap}
.summary strong{color:#2563eb}
.node{cursor:default}
.node:hover circle{fill:#dbeafe}
.leaf-box{rx:6;ry:6}
.branch{stroke-width:2;fill:none}
.branch-h{stroke:#2563eb}
.branch-t{stroke:#f97316}
.prob-label{font-size:10px;font-weight:600}
.leaf-text{font-size:10px;font-weight:700}
.leaf-prob{font-size:9px;fill:#64748b}
</style></head><body>
<div class="controls">
  <div class="ctrl">
    <label>P(Heads) <span id="pv">0.50</span></label>
    <input type="range" id="prob" min="5" max="95" value="50" step="5">
  </div>
  <div class="ctrl">
    <label>Number of flips</label>
    <div class="flip-btns" id="btns">
      <button data-n="2" class="active">2</button>
      <button data-n="3">3</button>
      <button data-n="4">4</button>
    </div>
  </div>
</div>
<svg id="tree" viewBox="0 0 520 220"></svg>
<div class="summary">
  <span>Outcomes: <strong id="oc">4</strong></span>
  <span>P(all H): <strong id="ah">0.2500</strong></span>
  <span>P(all T): <strong id="at">0.2500</strong></span>
  <span>P(mixed): <strong id="mx">0.5000</strong></span>
</div>
<script>
const svg=document.getElementById('tree');
const probSlider=document.getElementById('prob');
const pv=document.getElementById('pv');
const oc=document.getElementById('oc'),ah=document.getElementById('ah'),at=document.getElementById('at'),mx=document.getElementById('mx');
let flips=2,pH=0.5;
document.getElementById('btns').addEventListener('click',e=>{
  if(e.target.tagName!=='BUTTON')return;
  flips=parseInt(e.target.dataset.n);
  document.querySelectorAll('.flip-btns button').forEach(b=>b.classList.remove('active'));
  e.target.classList.add('active');
  draw();
});
probSlider.addEventListener('input',()=>{pH=probSlider.value/100;pv.textContent=pH.toFixed(2);draw()});
function draw(){
  const pT=1-pH;const n=Math.pow(2,flips);
  const outcomes=[];
  for(let i=0;i<n;i++){
    let path='',prob=1;
    for(let f=0;f<flips;f++){
      if((i>>((flips-1)-f))&1){path+='T';prob*=pT}
      else{path+='H';prob*=pH}
    }
    outcomes.push({path,prob});
  }
  const W=520,H=220;
  const layerW=W/(flips+1.5);
  let lines='',nodes='';
  function addLayer(parentX,parentY,depth,pathSoFar,probSoFar,yMin,yMax){
    if(depth>=flips){
      const idx=outcomes.findIndex(o=>o.path===pathSoFar);
      const p=probSoFar;
      nodes+=\`<rect class="leaf-box" x="\${parentX-24}" y="\${parentY-12}" width="48" height="24" fill="\${pathSoFar.indexOf('T')===-1?'#dbeafe':pathSoFar.indexOf('H')===-1?'#ffedd5':'#f1f5f9'}" stroke="\${pathSoFar.indexOf('T')===-1?'#93c5fd':pathSoFar.indexOf('H')===-1?'#fdba74':'#cbd5e1'}" stroke-width="1"/>\`;
      nodes+=\`<text class="leaf-text" x="\${parentX}" y="\${parentY+1}" text-anchor="middle" fill="\${pathSoFar.indexOf('T')===-1?'#1d4ed8':'#1e293b'}">\${pathSoFar}</text>\`;
      nodes+=\`<text class="leaf-prob" x="\${parentX}" y="\${parentY+18}" text-anchor="middle">\${p.toFixed(3)}</text>\`;
      return;
    }
    const nextX=parentX+layerW;
    const midY=(yMin+yMax)/2;
    const hY=(yMin+midY)/2;
    const tY=(midY+yMax)/2;
    lines+=\`<path class="branch branch-h" d="M\${parentX},\${parentY} C\${parentX+layerW*0.4},\${parentY} \${nextX-layerW*0.4},\${hY} \${nextX},\${hY}"/>\`;
    lines+=\`<path class="branch branch-t" d="M\${parentX},\${parentY} C\${parentX+layerW*0.4},\${parentY} \${nextX-layerW*0.4},\${tY} \${nextX},\${tY}"/>\`;
    const lx=(parentX+nextX)/2,ly1=(parentY+hY)/2-6,ly2=(parentY+tY)/2-6;
    nodes+=\`<text class="prob-label" x="\${lx}" y="\${ly1}" text-anchor="middle" fill="#2563eb">H (\${pH.toFixed(2)})</text>\`;
    nodes+=\`<text class="prob-label" x="\${lx}" y="\${ly2}" text-anchor="middle" fill="#f97316">T (\${pT.toFixed(2)})</text>\`;
    addLayer(nextX,hY,depth+1,pathSoFar+'H',probSoFar*pH,yMin,midY);
    addLayer(nextX,tY,depth+1,pathSoFar+'T',probSoFar*pT,midY,yMax);
  }
  const startX=30,startY=H/2;
  addLayer(startX,startY,0,'',1,10,H-10);
  nodes+=\`<circle cx="\${startX}" cy="\${startY}" r="8" fill="#e0e7ff" stroke="#6366f1" stroke-width="2"/>\`;
  nodes+=\`<text x="\${startX}" y="\${startY+3.5}" text-anchor="middle" font-size="7" font-weight="700" fill="#4338ca">Start</text>\`;
  svg.innerHTML=lines+nodes;
  const allH=Math.pow(pH,flips),allT=Math.pow(pT,flips);
  oc.textContent=n;
  ah.textContent=allH.toFixed(4);
  at.textContent=allT.toFixed(4);
  mx.textContent=(1-allH-allT).toFixed(4);
}
draw();
</script></body></html>`,
		spec: {
			type: 'probability_tree',
			goal: 'Explore how branching paths create compound probabilities through the multiplication rule.',
			anchor_content: {
				events: ['coin_flip', 'coin_flip'],
				starting_probabilities: [0.5, 0.5],
			},
			context: {
				learner_level: 'secondary',
				template_id: 'guided-discovery',
				color_mode: 'light',
				accent_color: '#2563eb',
				surface_color: '#eff6ff',
				font_mono: 'ui-monospace',
			},
			dimensions: { width: '100%', height: 340, resizable: false },
			print_translation: 'static_diagram',
		},
		fallback_diagram: {
			svg_content: probabilityTreeSvg,
			caption:
				'Probability tree for two fair coin flips showing four equally likely outcomes, each with probability ¼.',
			alt_text:
				'Tree diagram branching from Start into Heads and Tails, each further branching into Heads and Tails, with final probabilities of one quarter each.',
		},
	},

	worked_example: {
		title: 'Two dice: probability of doubles',
		setup: 'You roll two fair six-sided dice. What is the probability of rolling doubles (both dice show the same number)?',
		steps: [
			{
				label: 'Identify the events',
				content: 'Die 1 shows any number (6 outcomes). Die 2 must match die 1 (1 favourable out of 6).',
			},
			{
				label: 'Check independence',
				content: 'The dice are independent — the result of one does not affect the other.',
			},
			{
				label: 'Apply the multiplication rule',
				content: 'P(die 1 = k) = 1/6 for any k. P(die 2 = k | die 1 = k) = 1/6. But we need to sum over all k: P(doubles) = 6 × (1/6 × 1/6) = 6/36 = 1/6.',
			},
		],
		conclusion: 'There are 6 favourable outcomes (1-1, 2-2, ... 6-6) out of 36 total, giving P(doubles) = 1/6 ≈ 16.7%.',
		answer: '1/6 ≈ 0.167',
	},

	pitfall: {
		misconception: 'Two heads is twice as unlikely as one head',
		correction: "P(at least one head in two flips) = ¾, not ½. P(two heads) = ¼. The relationship isn't linear — it's multiplicative. Each additional requirement multiplies, not adds, to reduce the probability.",
		example: "Getting at least one head from two coins: P = 1 − P(TT) = 1 − ¼ = ¾. That's more likely than a single head from one coin (½).",
		why: "Additive thinking is deeply intuitive. Students expect 'harder' to mean 'subtract or halve' rather than 'multiply fractions'.",
	},

	reflection: {
		prompt: 'How does the tree diagram help you see where the multiplication rule comes from? Could you explain it to someone who only knows single-event probability?',
		type: 'open',
		space: 4,
	},

	practice: {
		problems: [
			{
				difficulty: 'warm',
				question: 'A coin is flipped and a die is rolled. What is the probability of getting heads AND rolling a 4?',
				hints: [
					{ level: 1, text: 'Are these events independent? If so, multiply their probabilities.' },
					{ level: 2, text: 'P(H) = ½, P(4) = 1/6. Multiply them.' },
				],
				solution: {
					approach: 'Multiplication rule for independent events.',
					answer: 'P(H and 4) = ½ × 1/6 = 1/12 ≈ 0.083',
				},
				writein_lines: 3,
			},
			{
				difficulty: 'medium',
				question: 'A bag has 3 red and 5 blue marbles. You draw one marble, replace it, then draw again. What is the probability of drawing red both times?',
				hints: [
					{ level: 1, text: 'With replacement means the draws are independent.' },
					{ level: 2, text: 'P(red) = 3/8 each time. Apply the multiplication rule.' },
				],
				solution: {
					approach: 'Independent draws with replacement — multiply probabilities.',
					answer: 'P(RR) = 3/8 × 3/8 = 9/64 ≈ 0.141',
				},
				writein_lines: 4,
			},
			{
				difficulty: 'cold',
				question: 'You flip a coin three times. Draw the full probability tree and find P(exactly two heads).',
				hints: [
					{ level: 1, text: 'The tree has 8 final branches (2³ = 8).' },
					{ level: 2, text: 'Count paths with exactly two H: HHT, HTH, THH.' },
					{ level: 3, text: 'Each path has probability ½ × ½ × ½ = 1/8. There are 3 such paths.' },
				],
				solution: {
					approach: 'List all paths with exactly 2 heads and sum their probabilities.',
					answer: 'P(exactly 2 heads) = 3 × 1/8 = 3/8 = 0.375',
				},
				writein_lines: 6,
			},
		],
	},

	glossary: {
		terms: [
			{
				term: 'Independent Events',
				definition: 'Two events where the outcome of one does not affect the probability of the other.',
				used_in: 'Explanation, Worked Example',
				related: ['Dependent Events', 'Multiplication Rule'],
			},
			{
				term: 'Multiplication Rule',
				definition: 'For independent events, P(A and B) = P(A) × P(B).',
				used_in: 'Explanation, Worked Example',
				related: ['Independent Events', 'Compound Event'],
			},
			{
				term: 'Sample Space',
				definition: 'The set of all possible outcomes of an experiment.',
				used_in: 'Explanation',
				related: ['Event', 'Probability'],
			},
			{
				term: 'Compound Event',
				definition: 'An event consisting of two or more simple events occurring together or in sequence.',
				related: ['Multiplication Rule', 'Sample Space'],
			},
			{
				term: 'Probability Tree',
				definition: 'A diagram where each branch represents a possible outcome, with probabilities on each branch.',
				used_in: 'Explanation, Simulation',
				related: ['Sample Space', 'Compound Event'],
			},
			{
				term: 'Conditional Probability',
				definition: 'The probability of an event given that another event has occurred: P(A|B).',
				related: ['Independent Events', 'Dependent Events'],
			},
		],
	},

	what_next: {
		body: 'The multiplication rule works perfectly for independent events. But what happens when one event changes the odds of another?',
		next: 'Section 2 — Conditional Probability and Dependent Events',
		preview: 'Drawing without replacement, Bayes\' theorem, and the difference one condition makes.',
		prerequisites: ['Multiplication rule for independent events', 'Probability tree diagrams'],
	},
};

export const guidedDiscoveryPreview: TemplatePreview = {
	section: discoveryMathSection,
	summary:
		'A probability section that explains the multiplication rule first, then lets learners build their own probability tree in the simulation to verify the theory.'
};
