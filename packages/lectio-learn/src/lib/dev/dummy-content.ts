import type { SectionContent } from '../schema/types';

const instantSpeedDiagramSvg = `<svg viewBox="0 0 360 220" xmlns="http://www.w3.org/2000/svg" class="w-full h-auto">
  <rect x="28" y="28" width="304" height="164" rx="14" fill="hsl(213 37% 17% / 0.04)" stroke="hsl(213 37% 17% / 0.18)" stroke-width="2"/>
  <line x1="56" y1="166" x2="304" y2="166" stroke="hsl(213 37% 17% / 0.35)" stroke-width="2"/>
  <line x1="72" y1="150" x2="72" y2="174" stroke="hsl(213 37% 17% / 0.22)" stroke-width="2"/>
  <line x1="168" y1="150" x2="168" y2="174" stroke="hsl(213 37% 17% / 0.22)" stroke-width="2"/>
  <line x1="264" y1="150" x2="264" y2="174" stroke="hsl(213 37% 17% / 0.22)" stroke-width="2"/>
  <circle cx="72" cy="108" r="12" fill="hsl(24 95% 53%)"/>
  <circle cx="168" cy="78" r="12" fill="hsl(24 95% 53% / 0.72)"/>
  <circle cx="264" cy="58" r="12" fill="hsl(24 95% 53% / 0.5)"/>
  <path d="M72 108 C112 100, 132 88, 168 78 S236 62, 264 58" fill="none" stroke="hsl(24 95% 53%)" stroke-width="3"/>
  <text x="54" y="191" font-size="12" fill="hsl(213 37% 17% / 0.7)">t = 1</text>
  <text x="146" y="191" font-size="12" fill="hsl(213 37% 17% / 0.7)">t = 2</text>
  <text x="242" y="191" font-size="12" fill="hsl(213 37% 17% / 0.7)">t = 3</text>
  <text x="116" y="50" font-size="13" fill="hsl(213 37% 17%)">Average speed changes over time</text>
</svg>`;

// ─────────────────────────────────────────────
// CALCULUS SECTION — exercises original 8 components
// ─────────────────────────────────────────────

export const calculusSection: SectionContent = {
	section_id: 'calc-01',
	template_id: 'guided_concept_path_v1',

	header: {
		title: 'Why does calculus exist?',
		subtitle: 'Two questions algebra cannot answer',
		subject: 'Mathematics',
		grade_band: 'secondary',
		objectives: ['Understand the motivation for calculus and distinguish it from algebra'],
	},

	hook: {
		headline: 'How fast is something moving at this exact instant?',
		body: 'You can measure where a ball is at two moments and calculate how far it moved. But what if you need its speed at one precise instant — not over a span, but at a single frozen moment? Algebra gives you averages. It cannot give you an instant.',
		anchor: 'the gap between average speed and instantaneous speed',
		svg_content: `<svg viewBox="0 0 160 200" xmlns="http://www.w3.org/2000/svg" class="w-full h-full" preserveAspectRatio="xMidYMid meet">
  <!-- Ruler on the right -->
  <rect x="130" y="10" width="16" height="180" rx="2" fill="hsl(38 30% 92%)" stroke="hsl(213 37% 17% / 0.3)" stroke-width="1"/>
  <line x1="130" y1="50" x2="146" y2="50" stroke="hsl(213 37% 17% / 0.3)" stroke-width="0.5"/>
  <line x1="130" y1="90" x2="146" y2="90" stroke="hsl(213 37% 17% / 0.3)" stroke-width="0.5"/>
  <line x1="130" y1="130" x2="146" y2="130" stroke="hsl(213 37% 17% / 0.3)" stroke-width="0.5"/>
  <line x1="130" y1="170" x2="146" y2="170" stroke="hsl(213 37% 17% / 0.3)" stroke-width="0.5"/>
  <!-- Motion trail -->
  <circle cx="70" cy="35" r="14" fill="hsl(24 95% 53% / 0.04)"/>
  <circle cx="70" cy="50" r="18" fill="hsl(24 95% 53% / 0.08)"/>
  <!-- Ball frozen mid-fall -->
  <circle cx="70" cy="85" r="22" fill="hsl(24 95% 53% / 0.85)"/>
  <circle cx="62" cy="78" r="6" fill="hsl(24 95% 53% / 0.4)"/>
  <!-- Velocity arrow -->
  <line x1="70" y1="110" x2="70" y2="155" stroke="hsl(213 37% 17% / 0.6)" stroke-width="2"/>
  <polygon points="64,155 70,168 76,155" fill="hsl(213 37% 17% / 0.6)"/>
  <text x="85" y="140" font-size="10" fill="hsl(213 37% 17% / 0.5)">v = ?</text>
</svg>`,
	},

	explanation: {
		body: 'This question forced mathematicians to invent an entirely new branch of mathematics. Algebra can find averages — how fast something moved over ten seconds, how much water flowed in an hour. But it breaks down at the boundary: the speed at one instant, the exact area under a curve. Calculus was invented to cross that boundary. It introduced two core tools: derivatives (which measure instantaneous rates of change) and integrals (which measure total accumulation). These tools turn out to be opposites of each other — a discovery called the Fundamental Theorem of Calculus that connects the two halves into one unified framework. Before calculus, every measurement was an average over some interval of time or space. The derivative asks what happens when that interval shrinks to zero — a question that looks impossible until you define a limit carefully. The integral asks how to add up infinitely many infinitesimal pieces — the area under a curve, the total distance travelled, the work done by a changing force. Together they let engineers predict orbits, economists model growth, and biologists track populations. Students often meet calculus first as a collection of rules, but the historical motivation was always practical: motion, area, and accumulation in the real world.',
		emphasis: ['derivatives', 'integrals', 'opposites of each other'],
		callouts: [
			{
				type: 'insight',
				text: 'Derivatives and integrals being inverses of each other is not obvious — it took Newton and Leibniz to see it, and it remains the most important single theorem in calculus.',
			},
			{
				type: 'remember',
				text: 'Derivative = rate of change. Integral = total accumulation. They undo each other.',
			},
		],
	},

	definition: {
		term: 'Calculus',
		formal:
			'The mathematical study of continuous change, consisting of differential calculus (rates of change and slopes of curves) and integral calculus (accumulation of quantities and areas under or between curves).',
		plain: 'A branch of mathematics built to answer two questions: how fast is something changing right now, and how much has it accumulated over time?',
		etymology: 'From Latin calculus — a small stone used for counting.',
		examples: [
			'Differential calculus focuses on rates; integral calculus focuses on accumulation.',
			'The calculus of variations extends these ideas to functions of functions.',
		],
		related_terms: ['Derivative', 'Integral', 'Limit'],
	},

	worked_example: {
		diagram: {
			svg_content: instantSpeedDiagramSvg,
			caption: 'A simple motion trace showing a ball moving through three time points as the average speed changes.',
			alt_text: 'A motion trace with points at t equals 1, 2, and 3 showing a ball moving along a curved path as average speed changes over time.',
			figure_ref: 'Figure 1.1',
			description:
				'The ball moves farther in each equal time step, so average speed increases. Shrinking the interval between measurements approaches the instantaneous speed at a single moment.'
		},
		title: 'Finding instantaneous speed from a position function',
		setup: "A ball dropped from a 100-foot building has height h(t) = 100 − 16t² at time t seconds. What is the ball's speed at exactly t = 2?",
		steps: [
			{
				label: 'Find the position at t = 2',
				content:
					'h(2) = 100 − 16(4) = 36 feet. The ball is 36 feet above the ground at t = 2.',
			},
			{
				label: 'Calculate average speed over one second',
				content:
					'h(3) = −44 feet. Average speed = (−44 − 36) ÷ 1 = −80 ft/s. But this is an average, not instantaneous.',
			},
			{
				label: 'Shrink the interval',
				content:
					'Over 0.1 seconds the average is −65.6 ft/s. Over 0.01 seconds it is −64.16 ft/s. The numbers are converging.',
			},
			{
				label: 'The limit gives the exact answer',
				content:
					'As the interval approaches zero, the average speed approaches −64 ft/s. This limit is the derivative — the instantaneous speed.',
			},
		],
		conclusion:
			'The instantaneous speed at t = 2 is exactly −64 ft/s — found by taking the limit of average speeds as the time interval shrinks to zero.',
		answer: '−64 ft/s downward',
		alternatives: [
			"Use the power rule directly: h'(t) = −32t, so h'(2) = −64 ft/s.",
			'Graphical method: find the slope of the tangent line to h(t) at t = 2.',
		],
	},

	key_fact: {
		fact: 'The limit of average speed as Δt → 0 gives instantaneous speed',
		formula: 'v_{instant} = \\lim_{\\Delta t \\to 0} \\frac{\\Delta x}{\\Delta t}',
		context: 'This limit definition is the foundation of the derivative.'
	},

	pitfall: {
		label: 'Exam Trap',
		misconception: 'Calculus is just faster algebra for the same problems',
		correction:
			'Calculus solves problems algebra genuinely cannot. Instantaneous speed, exact areas under curves, and rates of change at a point are all impossible with algebra alone.',
		example:
			'Any algebraic attempt to find instantaneous speed requires dividing by zero — an operation algebra forbids but calculus resolves through limits.',
		examples: [
			'Any algebraic attempt to find instantaneous speed requires dividing by zero — an operation algebra forbids but calculus resolves through limits.',
			'Trying to find the exact area under y = x² from 0 to 1 with algebra only gives approximations, never the exact value.',
		],
		why: 'Because algebra handles every other speed calculation students have seen, it is natural to assume it handles this one too.',
	},

	practice: {
		problems: [
			{
				difficulty: 'warm',
				diagram: {
					svg_content: instantSpeedDiagramSvg,
					caption: 'A simple motion trace that helps compare the changing average speed across intervals.',
					alt_text: 'A motion trace with three marked times showing how average speed changes across intervals.',
				},
				question:
					"A car is at mile marker 10 at 1 PM, mile marker 35 at 2 PM, and mile marker 80 at 4 PM. What is the car's average speed from 1–2 PM? From 2–4 PM? Why can't these averages tell you the car's speed at exactly 3 PM?",
				hints: [
					{ level: 1, text: 'Average speed = distance ÷ time. Calculate separately for each interval.' },
					{ level: 2, text: 'Think about what could happen between 2 and 4 PM — the car could speed up, slow down, or stop.' },
				],
				solution: {
					approach: 'Compute average speed for each interval, then reason about the gap.',
					answer: '25 mph for 1–2 PM, 22.5 mph for 2–4 PM. The car could have been going any speed at 3 PM — averages hide the instantaneous value.',
				},
				writein_lines: 4,
			},
			{
				difficulty: 'medium',
				question:
					'The height of a ball thrown upward is h(t) = 40t − 5t². Calculate the average speed over [1, 2], then [1, 1.5], then [1, 1.1]. What does the pattern suggest about the speed at t = 1?',
				hints: [
					{ level: 1, text: 'Start by calculating h(1), h(2), h(1.5), and h(1.1) using the formula.' },
					{ level: 2, text: 'Use (h(b) − h(a)) ÷ (b − a) for each interval.' },
					{ level: 3, text: 'Watch what happens to the average speed as the interval shrinks — that limit is the instantaneous speed.' },
				],
				solution: {
					approach: 'Calculate h at each time, find average speed for each interval, observe convergence.',
					answer: 'The averages converge toward 30 m/s, suggesting the instantaneous speed at t = 1 is 30 m/s.',
					worked: 'h(1) = 35, h(2) = 60, h(1.5) = 48.75, h(1.1) = 37.95. Average over [1,2] = 25 m/s, over [1,1.5] = 27.5 m/s, over [1,1.1] = 29.5 m/s. As the interval shrinks, the average approaches 30 m/s.',
				},
				writein_lines: 5,
			},
			{
				difficulty: 'cold',
				question:
					'Explain without calculus why it is impossible to find the speed of an object at a single instant using only algebra. What fundamental operation breaks down?',
				hints: [
					{ level: 1, text: 'Speed is defined as distance divided by time.' },
					{ level: 2, text: 'At a single instant, the time interval is zero — what does dividing by zero mean?' },
					{ level: 3, text: 'Algebra has no tool for dividing by zero. Calculus invented limits to get around this.' },
				],
				writein_lines: 6,
			},
		],
	},

	glossary: {
		terms: [
			{
				term: 'Derivative',
				definition: 'The instantaneous rate of change of a function at a given point.',
				used_in: 'Explanation, Worked Example',
				related: ['Limit', 'Integral'],
			},
			{
				term: 'Integral',
				definition: 'The total accumulated change — the area under a curve over an interval.',
				used_in: 'Explanation',
				related: ['Derivative', 'Limit'],
			},
			{
				term: 'Limit',
				definition: 'What a value approaches as a variable gets infinitely close to a target.',
				used_in: 'Worked Example',
				related: ['Derivative', 'Instantaneous'],
			},
			{
				term: 'Instantaneous',
				definition: 'At a single exact moment, not averaged over any interval.',
				related: ['Limit', 'Derivative'],
			},
			{
				term: 'Continuous Function',
				definition: 'A function with no breaks, jumps, or holes in its graph.',
				used_in: 'Explanation',
				related: ['Limit', 'Differentiable'],
			},
			{
				term: 'Secant Line',
				definition: 'A straight line connecting two points on a curve.',
				used_in: 'Worked Example',
				related: ['Tangent Line', 'Derivative'],
			},
			{
				term: 'Tangent Line',
				definition: 'A line touching a curve at one point, showing instantaneous rate of change.',
				used_in: 'Worked Example',
				related: ['Secant Line', 'Derivative', 'Limit'],
			},
			{
				term: 'Fundamental Theorem',
				definition: 'The theorem linking differentiation and integration as inverse operations.',
				related: ['Derivative', 'Integral'],
			},
		],
	},

	what_next: {
		body: 'Now that we understand why calculus exists, we need the precise tool that makes instantaneous measurement possible.',
		next: 'Section 2 — Limits: The Foundation of Calculus',
		prerequisites: ['Average rate of change', 'Function notation', 'Algebraic fractions'],
	},
};

// ─────────────────────────────────────────────
// PHYSICS SECTION — exercises all new components
// ─────────────────────────────────────────────

const forceArrowSvg = `<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg" class="w-full h-auto">
  <rect x="140" y="60" width="120" height="80" rx="8" fill="hsl(213 37% 17% / 0.08)" stroke="hsl(213 37% 17% / 0.3)" stroke-width="2"/>
  <text x="200" y="105" text-anchor="middle" font-size="14" fill="hsl(213 37% 17%)">m = 5 kg</text>
  <!-- Applied force arrow -->
  <line x1="270" y1="100" x2="370" y2="100" stroke="hsl(24 95% 53%)" stroke-width="3"/>
  <polygon points="370,92 390,100 370,108" fill="hsl(24 95% 53%)"/>
  <text x="330" y="88" text-anchor="middle" font-size="12" font-weight="bold" fill="hsl(24 95% 53%)">F = 20 N</text>
  <!-- Friction arrow -->
  <line x1="130" y1="100" x2="50" y2="100" stroke="hsl(0 70% 50%)" stroke-width="2" stroke-dasharray="6,3"/>
  <polygon points="50,94 35,100 50,106" fill="hsl(0 70% 50%)"/>
  <text x="90" y="88" text-anchor="middle" font-size="11" fill="hsl(0 70% 50%)">f = 5 N</text>
  <!-- Net force annotation -->
  <text x="200" y="180" text-anchor="middle" font-size="13" fill="hsl(213 37% 17% / 0.6)">F_net = 20 − 5 = 15 N →</text>
</svg>`;

const beforeAccelerationSvg = `<svg viewBox="0 0 300 160" xmlns="http://www.w3.org/2000/svg" class="w-full h-auto">
  <text x="150" y="24" text-anchor="middle" font-size="14" font-weight="bold" fill="hsl(213 37% 17%)">v = 0</text>
  <rect x="100" y="40" width="100" height="70" rx="8" fill="hsl(213 37% 17% / 0.08)" stroke="hsl(213 37% 17% / 0.3)" stroke-width="2"/>
  <text x="150" y="82" text-anchor="middle" font-size="16" font-weight="bold" fill="hsl(213 37% 17%)">5 kg</text>
  <line x1="60" y1="115" x2="240" y2="115" stroke="hsl(213 37% 17% / 0.15)" stroke-width="1.5"/>
  <text x="150" y="145" text-anchor="middle" font-size="13" font-weight="600" fill="hsl(213 37% 17% / 0.6)">Net force = 0 N</text>
</svg>`;

const afterAccelerationSvg = `<svg viewBox="0 0 300 160" xmlns="http://www.w3.org/2000/svg" class="w-full h-auto">
  <text x="150" y="24" text-anchor="middle" font-size="14" font-weight="bold" fill="hsl(24 95% 53%)">a = 3 m/s²</text>
  <rect x="100" y="40" width="100" height="70" rx="8" fill="hsl(24 95% 53% / 0.12)" stroke="hsl(24 95% 53%)" stroke-width="2"/>
  <text x="150" y="82" text-anchor="middle" font-size="16" font-weight="bold" fill="hsl(213 37% 17%)">5 kg</text>
  <line x1="210" y1="70" x2="265" y2="70" stroke="hsl(24 95% 53%)" stroke-width="3"/>
  <polygon points="265,63 278,70 265,77" fill="hsl(24 95% 53%)"/>
  <text x="240" y="58" text-anchor="middle" font-size="11" font-weight="bold" fill="hsl(24 95% 53%)">15 N</text>
  <line x1="60" y1="115" x2="240" y2="115" stroke="hsl(213 37% 17% / 0.15)" stroke-width="1.5"/>
  <text x="150" y="145" text-anchor="middle" font-size="13" font-weight="600" fill="hsl(24 95% 53%)">F_net = 15 N →</text>
</svg>`;

const seriesSvg1 = `<svg viewBox="0 0 300 120" xmlns="http://www.w3.org/2000/svg" class="w-full h-auto">
  <rect x="110" y="35" width="80" height="50" rx="6" fill="hsl(213 37% 17% / 0.08)" stroke="hsl(213 37% 17% / 0.3)" stroke-width="2"/>
  <text x="150" y="65" text-anchor="middle" font-size="12" fill="hsl(213 37% 17%)">m</text>
  <text x="150" y="105" text-anchor="middle" font-size="11" fill="hsl(213 37% 17% / 0.5)">No force, no acceleration</text>
</svg>`;

const seriesSvg2 = `<svg viewBox="0 0 300 120" xmlns="http://www.w3.org/2000/svg" class="w-full h-auto">
  <rect x="100" y="35" width="80" height="50" rx="6" fill="hsl(213 37% 17% / 0.08)" stroke="hsl(213 37% 17% / 0.3)" stroke-width="2"/>
  <text x="140" y="65" text-anchor="middle" font-size="12" fill="hsl(213 37% 17%)">m</text>
  <line x1="190" y1="60" x2="260" y2="60" stroke="hsl(24 95% 53%)" stroke-width="3"/>
  <polygon points="260,53 275,60 260,67" fill="hsl(24 95% 53%)"/>
  <text x="225" y="48" text-anchor="middle" font-size="11" font-weight="bold" fill="hsl(24 95% 53%)">F</text>
  <text x="150" y="105" text-anchor="middle" font-size="11" fill="hsl(213 37% 17% / 0.5)">Force applied → object accelerates</text>
</svg>`;

const seriesSvg3 = `<svg viewBox="0 0 300 120" xmlns="http://www.w3.org/2000/svg" class="w-full h-auto">
  <rect x="90" y="35" width="60" height="40" rx="6" fill="hsl(24 95% 53% / 0.12)" stroke="hsl(24 95% 53%)" stroke-width="2"/>
  <text x="120" y="60" text-anchor="middle" font-size="11" fill="hsl(213 37% 17%)">m</text>
  <rect x="170" y="25" width="80" height="60" rx="6" fill="hsl(213 37% 17% / 0.08)" stroke="hsl(213 37% 17% / 0.3)" stroke-width="2"/>
  <text x="210" y="60" text-anchor="middle" font-size="11" fill="hsl(213 37% 17%)">2m</text>
  <line x1="160" y1="55" x2="130" y2="55" stroke="hsl(24 95% 53%)" stroke-width="2"/>
  <text x="150" y="105" text-anchor="middle" font-size="11" fill="hsl(213 37% 17% / 0.5)">Same force, more mass → less acceleration</text>
</svg>`;

export const physicsSection: SectionContent = {
	section_id: 'phys-02',
	template_id: 'enriched_learning_path_v1',

	header: {
		title: "Newton's Second Law of Motion",
		subtitle: 'Force, mass, and acceleration — the equation that runs the universe',
		subject: 'Physics',
		section_number: 'Section 02',
		grade_band: 'secondary',
		objectives: ['Apply F = ma to predict the motion of objects under known forces'],
		level_pills: [
			{ label: 'All levels', variant: 'all' },
			{ label: 'Warm-up', variant: 'warm' },
			{ label: 'Challenge', variant: 'cold' },
		],
	},

	prerequisites: {
		label: 'Before we begin',
		items: [
			{ concept: 'Velocity vs. speed', refresher: 'Velocity includes direction — 5 m/s east, not just 5 m/s. Speed is the magnitude of velocity.' },
			{ concept: 'What is a force?', refresher: 'A push or pull on an object. Measured in Newtons (N). Contact forces and field forces.' },
			{ concept: 'Net force', refresher: 'The vector sum of all forces acting on an object. If forces balance, net force is zero.' },
			{ concept: 'Units: kg, m/s², N', refresher: '1 Newton = 1 kg × 1 m/s². This is the unit connection behind F = ma.' },
		],
	},

	hook: {
		headline: 'Why does a tennis ball fly but a bowling ball barely moves?',
		body: 'You can hit both with the same force. The tennis ball rockets across the room. The bowling ball barely budges. Same push, wildly different results. The difference is not about the force — it is about what resists the force.',
		anchor: 'the relationship between force, mass, and how things accelerate',
		type: 'question',
		question_options: [
			'The tennis ball is bouncier',
			'The bowling ball has more mass',
			'The force acts differently on each',
		],
	},

	explanation: {
		body: "Newton's Second Law states that the acceleration of an object is directly proportional to the net force acting on it and inversely proportional to its mass. Written as F = ma, this single equation connects three fundamental quantities: force (measured in Newtons), mass (in kilograms), and acceleration (in metres per second squared). If you double the force on an object, its acceleration doubles. If you double the mass, its acceleration halves. This is why the tennis ball accelerates so much more than the bowling ball — same force, far less mass. The law also works in reverse: if you know the acceleration and mass, you can calculate exactly how much force is being applied.",
		emphasis: ['F = ma', 'directly proportional', 'inversely proportional'],
		callouts: [
			{
				type: 'insight',
				text: 'F = ma is deceptively simple. It governs everything from car crashes to rocket launches to the orbit of planets.',
			},
			{
				type: 'remember',
				text: 'More force → more acceleration. More mass → less acceleration. Always net force, not just any single force.',
			},
		],
	},

	insight_strip: {
		cells: [
			{
				label: 'Double the force',
				value: '2× acceleration',
				note: 'Direct proportionality — force and acceleration scale together',
			},
			{
				label: 'Double the mass',
				value: '½ acceleration',
				note: 'Inverse proportionality — mass resists acceleration',
				highlight: true,
			},
			{
				label: 'Zero net force',
				value: 'Zero acceleration',
				note: "Newton's First Law — the special case where F_net = 0",
			},
		],
	},

	definition_family: {
		family_title: 'The three quantities in F = ma',
		family_intro: 'Each quantity has a precise physical meaning. Mixing them up is the most common source of errors.',
		definitions: [
			{
				term: 'Force (F)',
				formal: 'A vector quantity representing the interaction between two objects, measured in Newtons (N), that causes or tends to cause a change in the state of motion of an object.',
				plain: 'A push or pull that can change how something moves. Has both a size and a direction.',
				notation: 'F_{net} = ma',
				symbol: 'F',
				related_terms: ['Newton', 'Net Force'],
			},
			{
				term: 'Mass (m)',
				formal: 'A scalar quantity representing the amount of matter in an object and its resistance to acceleration, measured in kilograms (kg).',
				plain: 'How much stuff is in an object — and how hard it is to get that stuff moving or to stop it.',
				symbol: 'm',
				related_terms: ['Inertia', 'Weight'],
			},
			{
				term: 'Acceleration (a)',
				formal: 'The rate of change of velocity with respect to time, measured in metres per second squared (m/s²). A vector quantity.',
				plain: 'How quickly something speeds up, slows down, or changes direction. Not the same as speed.',
				notation: 'a = \\frac{\\Delta v}{\\Delta t}',
				symbol: 'a',
				related_terms: ['Velocity', 'Deceleration'],
			},
		],
	},

	diagram: {
		svg_content: forceArrowSvg,
		caption: 'A 5 kg block on a surface with an applied force of 20 N and friction of 5 N. The net force is 15 N to the right.',
		alt_text: 'Free body diagram showing a 5 kg block with a 20 Newton force arrow pointing right and a 5 Newton friction arrow pointing left, with net force annotation below.',
		zoom_label: 'Expand diagram',
		figure_number: 1,
		figure_ref: 'Figure 2.1',
		description:
			'The applied force and friction act in opposite directions. Net force is the vector sum — here 15 N to the right, which determines the acceleration via F = ma.',
		callouts: [
			{ id: 'c1', x: 82, y: 45, label: 'Applied force', explanation: 'The external push of 20 Newtons applied to the right side of the block.' },
			{ id: 'c2', x: 18, y: 45, label: 'Friction', explanation: 'Opposes motion at 5 N. Always acts opposite to the direction of movement.' },
			{ id: 'c3', x: 50, y: 85, label: 'Net force', explanation: '20 − 5 = 15 N to the right. This is the force that actually causes acceleration.' },
		],
	},

	diagram_compare: {
		before_svg: beforeAccelerationSvg,
		after_svg: afterAccelerationSvg,
		before_label: 'At rest',
		after_label: 'Accelerating',
		before_details: [
			'Mass stays 5 kg.',
			'Net force is 0 N.',
			'Acceleration is 0 m/s², so the object remains at rest.',
		],
		after_details: [
			'Mass is still 5 kg.',
			'A 15 N net force acts to the right.',
			'Acceleration becomes 3 m/s² to the right.',
		],
		caption: 'A 5 kg object at rest on the left compared with the same object accelerating at 3 m/s² under a 15 N net force on the right.',
		alt_text: 'Comparison of a stationary 5 kg block and the same block accelerating at 3 metres per second squared under 15 N.',
	},

	diagram_series: {
		title: 'How mass affects acceleration',
		diagrams: [
			{ svg_content: seriesSvg1, step_label: 'No force', caption: 'An object at rest with no applied force remains at rest (First Law).' },
			{ svg_content: seriesSvg2, step_label: 'Force applied', caption: 'Applying force F to mass m produces acceleration a = F/m.' },
			{ svg_content: seriesSvg3, step_label: 'More mass, same force', caption: 'Doubling the mass halves the acceleration for the same applied force.' },
		],
	},

	worked_example: {
		title: 'Finding acceleration from force and mass',
		setup: 'A 5 kg block is pushed with 20 N of force across a surface with 5 N of friction. Find the acceleration.',
		method_label: 'Method A: Direct calculation',
		steps: [
			{
				label: 'Identify all forces',
				content: 'Applied force = 20 N (right). Friction = 5 N (left). Normal force and gravity cancel vertically.',
				note: 'Always draw a free body diagram first.',
			},
			{
				label: 'Calculate net force',
				content: 'F_net = 20 − 5 = 15 N to the right.',
				formula: 'F_{net} = F_{applied} - f = 20 - 5 = 15 \\text{ N}',
			},
			{
				label: 'Apply F = ma',
				content: 'a = F_net ÷ m = 15 ÷ 5 = 3 m/s² to the right.',
				formula: 'a = \\frac{F_{net}}{m} = \\frac{15}{5} = 3 \\text{ m/s}^2',
			},
		],
		conclusion: 'The block accelerates at 3 m/s² to the right. The friction reduces the effect of the applied force but does not stop acceleration.',
		answer: '3 m/s² to the right',
	},

	process: {
		title: 'Solving any F = ma problem',
		intro: 'Use this procedure every time you encounter a force-and-motion problem. The order matters.',
		steps: [
			{
				number: 1,
				action: 'Draw a free body diagram',
				detail: 'Sketch the object and draw arrows for every force acting on it. Label each arrow with its magnitude and direction.',
				output: 'A diagram with all forces visible',
				warning: 'Do not include forces the object exerts on other things — only forces on it.',
			},
			{
				number: 2,
				action: 'Choose a coordinate system',
				detail: 'Pick positive direction (usually the direction of motion). Align one axis with the expected acceleration.',
				output: 'Positive and negative directions defined',
			},
			{
				number: 3,
				action: 'Sum forces in each direction',
				detail: 'Add all forces along each axis. Forces in the positive direction are positive; opposite are negative.',
				input: 'Force arrows from diagram',
				output: 'F_net for each axis',
			},
			{
				number: 4,
				action: 'Apply F = ma',
				detail: 'Set F_net = ma and solve for the unknown (usually acceleration, sometimes force or mass).',
				input: 'F_net and known values',
				output: 'The unknown quantity',
			},
			{
				number: 5,
				action: 'Check units and direction',
				detail: 'Verify that your answer has correct units (m/s² for acceleration, N for force, kg for mass) and a sensible direction.',
				warning: 'A negative acceleration means the object decelerates — not that you made an error.',
			},
		],
		checklist_mode: true,
	},

	pitfall: {
		misconception: 'Heavier objects always fall faster',
		correction: 'In a vacuum, all objects fall at the same rate regardless of mass. Air resistance, not mass, causes differences in everyday experience. The gravitational force is stronger on heavier objects, but they also have more inertia — the effects exactly cancel.',
		example: 'A hammer and a feather dropped on the Moon (no air) hit the ground at the same time — Apollo 15 demonstrated this.',
		severity: 'major',
		why: 'Daily experience with dropping things in air strongly reinforces this intuition.',
	},

	pitfalls: [
		{
			misconception: 'Force is needed to keep something moving',
			correction: "Newton's First Law says an object in motion stays in motion unless a net force acts. You need force to start or stop motion, not to maintain it. On Earth, friction creates the illusion that force is needed to keep moving.",
			severity: 'major',
		},
		{
			misconception: 'Mass and weight are the same thing',
			correction: 'Mass is the amount of matter (kg). Weight is the gravitational force on that mass (N). Your mass is the same on the Moon, but your weight is 1/6th.',
			severity: 'minor',
		},
	],

	quiz: {
		question: 'A 10 kg object experiences a net force of 40 N. What is its acceleration?',
		options: [
			{ text: '0.25 m/s²', correct: false, explanation: 'This would be mass ÷ force (10/40). Remember: a = F/m, not m/F.' },
			{ text: '4 m/s²', correct: true, explanation: 'Correct! a = F/m = 40/10 = 4 m/s².' },
			{ text: '400 m/s²', correct: false, explanation: 'This is F × m. You need to divide, not multiply.' },
			{ text: '30 m/s²', correct: false, explanation: 'This is F − m. The relationship is division, not subtraction.' },
		],
		feedback_correct: 'Exactly right. a = F/m is the direct application of Newton\'s Second Law.',
		feedback_incorrect: 'Not quite. Remember: rearrange F = ma to get a = F ÷ m.',
	},

	practice: {
		label: 'Practice Problems',
		problems: [
			{
				difficulty: 'warm',
				question: 'A 2 kg toy car is pushed with a net force of 6 N. What is its acceleration?',
				context: 'Assume a frictionless surface.',
				hints: [
					{ level: 1, text: 'Write down F = ma and identify what you know.' },
					{ level: 2, text: 'You know F = 6 N and m = 2 kg. Solve for a.' },
				],
				solution: {
					approach: 'Direct substitution into F = ma, solving for a.',
					answer: 'a = 6 ÷ 2 = 3 m/s²',
				},
				writein_lines: 3,
			},
			{
				difficulty: 'medium',
				question: 'A 1500 kg car accelerates from rest to 20 m/s in 10 seconds. What net force is required? Assume constant acceleration.',
				hints: [
					{ level: 1, text: 'First find the acceleration using a = Δv / Δt.' },
					{ level: 2, text: 'a = (20 − 0) / 10 = 2 m/s². Now use F = ma.' },
					{ level: 3, text: 'F = 1500 × 2 = 3000 N.' },
				],
				solution: {
					approach: 'Find acceleration from velocity change, then apply F = ma.',
					answer: '3000 N in the direction of motion',
					worked: 'Step 1: a = Δv/Δt = (20 − 0)/10 = 2 m/s². Step 2: F = ma = 1500 × 2 = 3000 N.',
				},
				writein_lines: 5,
			},
			{
				difficulty: 'cold',
				question: 'Two blocks (3 kg and 7 kg) are connected by a string on a frictionless surface. A 50 N force is applied to the 7 kg block. Find the acceleration of the system and the tension in the string between the blocks.',
				hints: [
					{ level: 1, text: 'Treat both blocks as one system first to find acceleration.' },
					{ level: 2, text: 'Total mass = 10 kg. a = 50/10 = 5 m/s². Now find the tension.' },
					{ level: 3, text: 'For the 3 kg block alone, the only horizontal force is tension: T = 3 × 5 = 15 N.' },
				],
				solution: {
					approach: 'Treat system as whole for acceleration, then isolate one block for tension.',
					answer: 'a = 5 m/s², T = 15 N',
					worked: 'System: F = (m₁ + m₂)a → 50 = 10a → a = 5 m/s². For 3 kg block: T = m₁a = 3 × 5 = 15 N.',
				},
				writein_lines: 6,
			},
		],
		solutions_available: true,
	},

	reflection: {
		prompt: 'If Newton\'s Second Law suddenly stopped working, what everyday activity would change most dramatically?',
		type: 'open',
		space: 4,
	},

	simulation: {
		explanation:
			'Drag the force slider to see how acceleration changes for a fixed mass. A simple, direct test of F = ma.',
		html_content: `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,sans-serif;background:#fff7ed;color:#1c1917;padding:16px;display:flex;flex-direction:column;gap:12px;height:100vh;overflow:hidden}
.row{display:flex;align-items:center;gap:12px}
label{font-size:13px;font-weight:600;color:#44403c;min-width:52px}
label span{color:#f97316;font-variant-numeric:tabular-nums}
input[type=range]{flex:1;accent-color:#f97316;height:6px;cursor:pointer}
.result{flex:1;display:flex;align-items:center;justify-content:center;gap:16px;min-height:0}
.eq{font-size:26px;font-weight:700;font-variant-numeric:tabular-nums}
.eq .hl{color:#f97316}
.bar-wrap{width:48px;height:140px;background:#fef3c7;border:2px solid #f59e0b33;border-radius:10px;position:relative;overflow:hidden;display:flex;align-items:flex-end}
.bar-fill{width:100%;background:linear-gradient(180deg,#f97316,#ea580c);border-radius:0 0 8px 8px;transition:height .15s ease}
.bar-lbl{font-size:10px;color:#78716c;text-align:center}
</style></head><body>
<div class="row">
  <label>Force <span id="fv">10 N</span></label>
  <input type="range" id="force" min="1" max="40" value="10">
</div>
<div class="row" style="font-size:13px;color:#78716c">Mass fixed at <strong style="margin-left:4px">5 kg</strong></div>
<div class="result">
  <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
    <div class="bar-wrap"><div class="bar-fill" id="bar"></div></div>
    <div class="bar-lbl">Acceleration</div>
  </div>
  <div class="eq">a = <span class="hl" id="av">2.00</span> m/s²</div>
</div>
<script>
const fs=document.getElementById('force'),fv=document.getElementById('fv');
const bar=document.getElementById('bar'),av=document.getElementById('av');
function upd(){const f=+fs.value,a=f/5;fv.textContent=f+' N';av.textContent=a.toFixed(2);bar.style.height=Math.min(a/8*100,100)+'%'}
fs.addEventListener('input',upd);upd();
</script></body></html>`,
		spec: {
			type: 'graph_slider',
			goal: 'Discover how changing force and mass affects acceleration in Newton\'s Second Law.',
			anchor_content: { equation: 'F = ma', starting_mass: 5, starting_force: 15 },
			context: {
				learner_level: 'secondary',
				template_id: 'enriched_learning_path_v1',
				color_mode: 'light',
				accent_color: '#f97316',
				surface_color: '#fff7ed',
				font_mono: 'ui-monospace'
			},
			dimensions: { width: '100%', height: 280, resizable: false },
			print_translation: 'static_diagram'
		},
		fallback_diagram: {
			svg_content: forceArrowSvg,
			caption:
				'Fallback view of the free-body setup while the interactive simulation is unavailable.',
			alt_text:
				'Fallback diagram showing a 5 kilogram block with applied force and friction arrows.'
		}
	},

	callout: {
		variant: 'exam-tip',
		heading: 'Exam technique',
		body: 'Always state Newton\'s Second Law before substituting numbers: write F = ma, identify each symbol, then solve. Examiners award method marks for this.',
	},

	summary: {
		heading: 'In summary',
		items: [
			{ text: 'F = ma links net force, mass, and acceleration in a single equation.' },
			{ text: 'Acceleration is directly proportional to net force and inversely proportional to mass.' },
			{ text: 'Always use net force — the vector sum of all forces — not a single applied force.' },
			{ text: 'Units: force in Newtons (N), mass in kg, acceleration in m/s².' },
		],
		closing: 'Master the free-body diagram and the rest of dynamics falls into place.',
	},

	divider: {
		label: 'Exam practice',
	},

	key_fact: {
		fact: 'Newton\'s Second Law of Motion',
		formula: 'F_{net} = ma',
		context: 'Net force equals mass times acceleration — the equation that links force, mass, and motion.',
		source: 'SI base units definition',
	},

	student_textbox: {
		prompt: 'In your own words, explain why a fully loaded lorry takes much longer to stop than an empty one, even if both brakes apply the same force.',
		lines: 5,
		label: 'Your explanation',
	},

	short_answer: {
		question: 'A net force of 18 N acts on a 3 kg object. Calculate the acceleration. Show your working. [2 marks]',
		marks: 2,
		lines: 4,
		mark_scheme: '1 mark: correct rearrangement a = F/m. 1 mark: correct answer 6 m/s² with unit.',
	},

	fill_in_blank: {
		instruction: 'Complete the passage using the words in the box.',
		segments: [
			{ text: "Newton's Second Law states that the ", is_blank: false },
			{ text: 'acceleration', is_blank: true, answer: 'acceleration' },
			{ text: ' of an object is directly proportional to the ', is_blank: false },
			{ text: 'net force', is_blank: true, answer: 'net force' },
			{ text: ' acting on it and inversely proportional to its ', is_blank: false },
			{ text: 'mass', is_blank: true, answer: 'mass' },
			{ text: '. Doubling the force ', is_blank: false },
			{ text: 'doubles', is_blank: true, answer: 'doubles' },
			{ text: ' the acceleration. The SI unit of force is the ', is_blank: false },
			{ text: 'Newton', is_blank: true, answer: 'Newton' },
			{ text: '.', is_blank: false },
		],
		word_bank: ['acceleration', 'net force', 'mass', 'doubles', 'halves', 'Newton', 'kilogram'],
	},

	interview: {
		prompt: "Explain to them why a fully loaded shopping trolley is harder to push than an empty one, using Newton's Second Law.",
		audience: 'a curious 10-year-old',
		follow_up: 'Now explain why the trolley keeps rolling after you stop pushing.',
	},

	glossary: {
		terms: [
			{
				term: 'Force',
				definition: 'A push or pull on an object, measured in Newtons (N).',
				used_in: 'Explanation, Worked Example',
				pronunciation: 'fɔːrs',
				related: ['Net Force', 'Newton'],
			},
			{
				term: 'Mass',
				definition: 'The amount of matter in an object and its resistance to acceleration.',
				used_in: 'Explanation',
				pronunciation: 'mæs',
				related: ['Inertia', 'Weight'],
			},
			{
				term: 'Acceleration',
				definition: 'The rate of change of velocity, measured in m/s².',
				used_in: 'Explanation, Worked Example',
				related: ['Velocity', 'Force'],
			},
			{
				term: 'Net Force',
				definition: 'The vector sum of all forces acting on an object.',
				used_in: 'Process Steps',
				related: ['Force', 'Equilibrium'],
			},
			{
				term: 'Inertia',
				definition: "An object's tendency to resist changes in its state of motion.",
				related: ['Mass', "Newton's First Law"],
			},
			{
				term: 'Newton (unit)',
				definition: 'The SI unit of force: 1 N = 1 kg·m/s².',
				pronunciation: 'njuːtən',
				related: ['Force', 'Mass'],
			},
			{
				term: 'Free Body Diagram',
				definition: 'A sketch showing all forces acting on a single object.',
				used_in: 'Process Steps, Worked Example',
				related: ['Force', 'Net Force'],
			},
			{
				term: 'Equilibrium',
				definition: 'When net force is zero and an object has no acceleration.',
				related: ['Net Force', "Newton's First Law"],
			},
		],
	},

	what_next: {
		body: "Now that you can predict acceleration from force, the next question is: what happens when forces aren't constant?",
		next: "Section 3 — Newton's Third Law and Action-Reaction Pairs",
		preview: 'Every force has an equal and opposite partner — but they act on different objects.',
	},
};
