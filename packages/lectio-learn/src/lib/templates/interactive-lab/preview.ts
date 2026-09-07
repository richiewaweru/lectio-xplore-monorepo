import type { TemplatePreview } from '$lib/templates/types';
import type { SectionContent } from '$lib/schema/types';

const forceArrowSvg = `<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg" class="w-full h-auto">
  <rect x="140" y="60" width="120" height="80" rx="8" fill="hsl(213 37% 17% / 0.08)" stroke="hsl(213 37% 17% / 0.3)" stroke-width="2"/>
  <text x="200" y="105" text-anchor="middle" font-size="14" fill="hsl(213 37% 17%)">m = 5 kg</text>
  <line x1="270" y1="100" x2="370" y2="100" stroke="hsl(24 95% 53%)" stroke-width="3"/>
  <polygon points="370,92 390,100 370,108" fill="hsl(24 95% 53%)"/>
  <text x="330" y="88" text-anchor="middle" font-size="12" font-weight="bold" fill="hsl(24 95% 53%)">F = 20 N</text>
  <line x1="130" y1="100" x2="50" y2="100" stroke="hsl(0 70% 50%)" stroke-width="2" stroke-dasharray="6,3"/>
  <polygon points="50,94 35,100 50,106" fill="hsl(0 70% 50%)"/>
  <text x="90" y="88" text-anchor="middle" font-size="11" fill="hsl(0 70% 50%)">f = 5 N</text>
  <text x="200" y="180" text-anchor="middle" font-size="13" fill="hsl(213 37% 17% / 0.6)">F_net = 20 − 5 = 15 N →</text>
</svg>`;

const labPhysicsSection: SectionContent = {
	section_id: 'lab-phys-01',
	template_id: 'interactive-lab',

	header: {
		title: "Newton's Second Law of Motion",
		subtitle: 'Force, mass, and acceleration — the equation that runs the universe',
		subject: 'Physics',
		grade_band: 'secondary',
		objectives: ['Discover how force and mass determine acceleration by manipulating variables directly'],
	},

	hook: {
		headline: 'Why does a tennis ball fly but a bowling ball barely moves?',
		body: 'You can hit both with the same force. The tennis ball rockets across the room. The bowling ball barely budges. Same push, wildly different results. Before we explain why — try it yourself below.',
		anchor: 'the relationship between force, mass, and acceleration',
	},

	simulation: {
		explanation:
			'Drag the sliders to change net force and mass. Watch how acceleration responds in real time.',
		html_content: `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;background:#fff7ed;color:#1c1917;padding:20px;display:flex;flex-direction:column;gap:16px;height:100vh;overflow:hidden}
.controls{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.slider-group{display:flex;flex-direction:column;gap:6px}
.slider-group label{font-size:13px;font-weight:600;color:#44403c;display:flex;justify-content:space-between}
.slider-group label span{color:#f97316;font-variant-numeric:tabular-nums}
input[type=range]{width:100%;accent-color:#f97316;height:6px;cursor:pointer}
.viz{flex:1;display:flex;align-items:center;justify-content:center;gap:24px;min-height:0}
.bar-area{flex:1;display:flex;flex-direction:column;align-items:center;gap:8px;max-width:220px}
.bar-container{width:60px;height:160px;background:#fef3c7;border:2px solid #f59e0b33;border-radius:12px;position:relative;overflow:hidden;display:flex;align-items:flex-end}
.bar-fill{width:100%;background:linear-gradient(180deg,#f97316,#ea580c);border-radius:0 0 10px 10px;transition:height .2s ease}
.bar-label{font-size:11px;color:#78716c;font-weight:500}
.equation-area{display:flex;flex-direction:column;align-items:center;gap:12px}
.equation{font-size:28px;font-weight:700;color:#1c1917;font-variant-numeric:tabular-nums}
.equation .highlight{color:#f97316}
.breakdown{font-size:14px;color:#78716c;text-align:center;line-height:1.6}
.block-viz{display:flex;align-items:center;gap:12px}
.block{width:50px;height:50px;background:#fed7aa;border:2px solid #f97316;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:#9a3412;transition:transform .2s}
.arrow{height:4px;background:#f97316;border-radius:2px;transition:width .2s;position:relative}
.arrow::after{content:'';position:absolute;right:-8px;top:-6px;border-left:10px solid #f97316;border-top:8px solid transparent;border-bottom:8px solid transparent}
</style></head><body>
<div class="controls">
  <div class="slider-group">
    <label>Net Force <span id="fv">15 N</span></label>
    <input type="range" id="force" min="1" max="50" value="15" step="1">
  </div>
  <div class="slider-group">
    <label>Mass <span id="mv">5.0 kg</span></label>
    <input type="range" id="mass" min="1" max="20" value="5" step="0.5">
  </div>
</div>
<div class="viz">
  <div class="bar-area">
    <div class="bar-container"><div class="bar-fill" id="bar"></div></div>
    <div class="bar-label">Acceleration</div>
  </div>
  <div class="equation-area">
    <div class="block-viz">
      <div class="arrow" id="arrow" style="width:60px"></div>
      <div class="block" id="block">5 kg</div>
    </div>
    <div class="equation">a = <span class="highlight" id="accel">3.00</span> m/s²</div>
    <div class="breakdown" id="info">F ÷ m = 15 ÷ 5 = 3.00</div>
  </div>
</div>
<script>
const fs=document.getElementById('force'),ms=document.getElementById('mass');
const fv=document.getElementById('fv'),mv=document.getElementById('mv');
const bar=document.getElementById('bar'),accel=document.getElementById('accel');
const info=document.getElementById('info'),arrow=document.getElementById('arrow');
const block=document.getElementById('block');
function update(){
  const f=parseFloat(fs.value),m=parseFloat(ms.value);
  const a=f/m;
  fv.textContent=f+' N';mv.textContent=m.toFixed(1)+' kg';
  accel.textContent=a.toFixed(2);
  info.textContent='F ÷ m = '+f+' ÷ '+m.toFixed(1)+' = '+a.toFixed(2);
  bar.style.height=Math.min(a/50*100,100)+'%';
  arrow.style.width=Math.max(20,Math.min(f*3,180))+'px';
  block.textContent=m.toFixed(1)+' kg';
  block.style.transform='scale('+(0.7+m/30)+')';
}
fs.addEventListener('input',update);ms.addEventListener('input',update);
update();
</script></body></html>`,
		spec: {
			type: 'graph_slider',
			goal: "Discover how changing force and mass affects acceleration in Newton's Second Law.",
			anchor_content: { equation: 'F = ma', starting_mass: 5, starting_force: 15 },
			context: {
				learner_level: 'secondary',
				template_id: 'interactive-lab',
				color_mode: 'light',
				accent_color: '#f97316',
				surface_color: '#fff7ed',
				font_mono: 'ui-monospace',
			},
			dimensions: { width: '100%', height: 320, resizable: false },
			print_translation: 'static_diagram',
		},
		fallback_diagram: {
			svg_content: forceArrowSvg,
			caption:
				'A 5 kg block with 20 N applied force and 5 N friction, producing 15 N net force and 3 m/s² acceleration.',
			alt_text:
				'Free body diagram showing a 5 kg block with force arrows for applied force and friction.',
		},
	},

	explanation: {
		body: "What you just saw is Newton's Second Law in action. The acceleration of an object is directly proportional to the net force acting on it and inversely proportional to its mass. Written as F = ma, this equation links three quantities: force (Newtons), mass (kilograms), and acceleration (metres per second squared). When you doubled the force in the simulation, acceleration doubled. When you doubled the mass, acceleration halved. This is exactly what the equation predicts — and what you discovered by experimenting first.",
		emphasis: ['F = ma', 'directly proportional', 'inversely proportional'],
		callouts: [
			{
				type: 'insight',
				text: 'The simulation showed you the pattern before the formula. This is how physics was actually discovered — observation first, equations second.',
			},
			{
				type: 'remember',
				text: 'More force → more acceleration. More mass → less acceleration. Always net force, not just any single force.',
			},
		],
	},

	definition: {
		term: 'Newton\'s Second Law',
		formal:
			'The acceleration of an object is equal to the net force acting upon it divided by its mass: a = F_net / m.',
		plain: 'Push harder, it speeds up more. Make it heavier, it speeds up less. The formula F = ma captures both ideas in three letters.',
		examples: [
			'A 10 kg box pushed with 50 N of net force accelerates at 5 m/s².',
			'Doubling the mass of a rocket requires doubling the thrust to maintain the same acceleration.',
		],
		related_terms: ['Force', 'Mass', 'Acceleration', 'Inertia'],
	},

	worked_example: {
		title: 'Finding acceleration from force and mass',
		setup: 'A 5 kg block is pushed with 20 N of force across a surface with 5 N of friction. Find the acceleration.',
		steps: [
			{
				label: 'Identify all forces',
				content: 'Applied force = 20 N (right). Friction = 5 N (left). Normal force and gravity cancel vertically.',
			},
			{
				label: 'Calculate net force',
				content: 'F_net = 20 − 5 = 15 N to the right.',
			},
			{
				label: 'Apply F = ma',
				content: 'a = F_net ÷ m = 15 ÷ 5 = 3 m/s² to the right.',
			},
		],
		conclusion: 'The block accelerates at 3 m/s² to the right — exactly what the simulation showed when you set force to 15 N and mass to 5 kg.',
		answer: '3 m/s² to the right',
	},

	pitfall: {
		misconception: 'Heavier objects always fall faster',
		correction: 'In a vacuum, all objects fall at the same rate regardless of mass. Air resistance, not mass, causes differences in everyday experience.',
		example: 'A hammer and a feather dropped on the Moon (no air) hit the ground at the same time — Apollo 15 demonstrated this.',
		why: 'Daily experience with dropping things in air strongly reinforces this intuition.',
	},

	practice: {
		problems: [
			{
				difficulty: 'warm',
				question: 'A 2 kg toy car is pushed with a net force of 6 N on a frictionless surface. What is its acceleration?',
				hints: [
					{ level: 1, text: 'Write down F = ma and identify what you know.' },
					{ level: 2, text: 'You know F = 6 N and m = 2 kg. Solve for a.' },
				],
				solution: {
					approach: 'Direct substitution into F = ma.',
					answer: 'a = 6 ÷ 2 = 3 m/s²',
				},
				writein_lines: 3,
			},
			{
				difficulty: 'medium',
				question: 'A 1500 kg car accelerates from rest to 20 m/s in 10 seconds. What net force is required?',
				hints: [
					{ level: 1, text: 'First find acceleration: a = Δv / Δt.' },
					{ level: 2, text: 'a = (20 − 0) / 10 = 2 m/s². Now use F = ma.' },
				],
				solution: {
					approach: 'Find acceleration from velocity change, then apply F = ma.',
					answer: 'F = 1500 × 2 = 3000 N',
				},
				writein_lines: 5,
			},
			{
				difficulty: 'cold',
				question: 'Two blocks (3 kg and 7 kg) are connected by a string on a frictionless surface. A 50 N force pulls the 7 kg block. Find the acceleration and the tension in the string.',
				hints: [
					{ level: 1, text: 'Treat both blocks as one system to find acceleration.' },
					{ level: 2, text: 'Total mass = 10 kg. a = 50/10 = 5 m/s².' },
					{ level: 3, text: 'For the 3 kg block alone: T = 3 × 5 = 15 N.' },
				],
				solution: {
					approach: 'System approach for acceleration, isolate one block for tension.',
					answer: 'a = 5 m/s², T = 15 N',
				},
				writein_lines: 6,
			},
		],
	},

	what_next: {
		body: "Now that you've felt how force and mass shape acceleration, the next question is: what happens when forces come in pairs?",
		next: "Section 2 — Newton's Third Law and Action-Reaction Pairs",
		preview: 'Every force has an equal and opposite partner — but they act on different objects.',
	},
};

export const interactiveLabPreview: TemplatePreview = {
	section: labPhysicsSection,
	summary:
		'A physics section where the simulation sits front and centre — learners manipulate force and mass sliders before reading the formal F = ma explanation.'
};
