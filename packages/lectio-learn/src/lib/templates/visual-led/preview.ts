import type { TemplatePreview } from '$lib/templates/types';

const photosynthesisSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 280" fill="none">
  <rect width="480" height="280" rx="28" fill="#F0FDF4"/>
  <rect x="85" y="80" width="130" height="120" rx="26" fill="#22C55E" fill-opacity="0.18" stroke="#15803D" stroke-width="4"/>
  <rect x="265" y="70" width="130" height="138" rx="30" fill="#BBF7D0" stroke="#15803D" stroke-width="4"/>
  <circle cx="330" cy="135" r="46" fill="#166534" fill-opacity="0.18" stroke="#166534" stroke-width="3"/>
  <circle cx="330" cy="135" r="20" fill="#15803D" />
  <path d="M146 60C175 34 213 28 246 42" stroke="#FACC15" stroke-width="8" stroke-linecap="round"/>
  <path d="M252 44L237 30" stroke="#FACC15" stroke-width="8" stroke-linecap="round"/>
  <path d="M247 53L264 44" stroke="#FACC15" stroke-width="8" stroke-linecap="round"/>
  <path d="M44 150H81" stroke="#0EA5E9" stroke-width="8" stroke-linecap="round"/>
  <path d="M395 150H438" stroke="#0EA5E9" stroke-width="8" stroke-linecap="round"/>
  <path d="M178 224C215 248 254 247 296 228" stroke="#F97316" stroke-width="8" stroke-linecap="round"/>
  <text x="92" y="224" fill="#166534" font-size="18" font-family="Arial">Leaf cell</text>
  <text x="286" y="234" fill="#166534" font-size="18" font-family="Arial">Chloroplast</text>
</svg>`;

export const visualLedPreview: TemplatePreview = {
	section: {
		section_id: 'bio-figure-first-01',
		template_id: 'visual-led',
		header: {
			title: 'How photosynthesis moves energy',
			subtitle: 'See the chloroplast before the prose explains it',
			subject: 'Biology',
			section_number: 'Section 04',
			grade_band: 'secondary',
			objectives:
				['Trace how light energy enters the chloroplast and becomes stored chemical energy.']
		},
		hook: {
			headline: 'Where does the sunlight go once it reaches a leaf?',
			body: 'If photosynthesis feels abstract, the chloroplast makes it visible. The structure itself shows where energy enters, where carbon is fixed, and where sugar begins.',
			anchor: 'the learner needs a visible map of the process before the vocabulary',
			type: 'question',
			question_options: ['Into the chloroplast', 'Straight into the roots', 'Only into the veins']
		},
		explanation: {
			body: 'Photosynthesis starts when light energy is captured in the chloroplast. The chlorophyll-rich structures absorb light, water enters from the roots, and carbon dioxide enters from the air. The chloroplast then uses that energy to build glucose, storing energy in chemical form while oxygen leaves as a by-product.',
			emphasis: ['chloroplast', 'light energy', 'glucose'],
			callouts: [
				{
					type: 'insight',
					text: 'The diagram matters because each input enters a different part of the system.'
				}
			]
		},
		diagram: {
			svg_content: photosynthesisSvg,
			caption:
				'The chloroplast is the visible anchor for how light, water, and carbon dioxide become stored energy.',
			zoom_label: 'Inspect',
			alt_text:
				'A simplified leaf cell and chloroplast diagram with arrows for light, water, and glucose flow.',
			callouts: [
				{
					id: 'light',
					x: 44,
					y: 18,
					label: 'light',
					explanation:
						'Light energy is the signal that powers the first stage of photosynthesis.'
				},
				{
					id: 'chloroplast',
					x: 68,
					y: 48,
					label: 'chloroplast',
					explanation: 'This organelle is where the key reactions take place.'
				},
				{
					id: 'glucose',
					x: 58,
					y: 84,
					label: 'glucose',
					explanation: 'Stored chemical energy leaves the system in the form of sugar.'
				}
			]
		},
		process: {
			title: 'Read the figure in this order',
			intro: 'Use the figure as a map instead of scanning it randomly.',
			steps: [
				{
					number: 1,
					action: 'Find the energy input',
					detail: 'Start with the sunlight arrow because it tells you what activates the system.'
				},
				{
					number: 2,
					action: 'Trace the material inputs',
					detail: 'Follow how water and carbon dioxide move toward the chloroplast.'
				},
				{
					number: 3,
					action: 'Name the output',
					detail: 'Notice that glucose stores energy while oxygen leaves the process.'
				}
			]
		},
		pitfall: {
			misconception: 'Plants only make oxygen',
			correction:
				'Oxygen is a by-product. The main stored output is glucose, which keeps the captured energy.',
			example: 'The sugar product is the reason photosynthesis matters for growth.'
		},
		glossary: {
			terms: [
				{
					term: 'Chloroplast',
					definition: 'The plant organelle where photosynthesis happens.'
				},
				{
					term: 'Glucose',
					definition: 'A sugar molecule that stores chemical energy.'
				},
				{
					term: 'Carbon dioxide',
					definition: 'A gas from the air used to build glucose.'
				}
			]
		},
		practice: {
			problems: [
				{
					difficulty: 'warm',
					question: 'Why is the chloroplast the best place to start reading this diagram?',
					hints: [
						{ level: 1, text: 'It is where the light-driven reactions are centered.' }
					],
					solution: {
						approach: 'Start from the organelle doing the work.',
						answer: 'Because it is the structure where the key reactions happen.'
					},
					writein_lines: 3
				},
				{
					difficulty: 'medium',
					question: 'Name the two inputs that must reach the chloroplast before glucose can be made.',
					hints: [{ level: 1, text: 'One comes from the air and one comes from the roots.' }],
					solution: {
						approach: 'Look at the incoming arrows on the figure.',
						answer: 'Water and carbon dioxide.'
					},
					writein_lines: 3
				}
			]
		},
		what_next: {
			body: 'Once the structure is clear, the next step is separating the light reactions from the Calvin cycle.',
			next: 'Photosynthesis stages',
			preview: 'The two linked stages explain how capture becomes storage.'
		}
	},
	summary:
		'A biology section that makes the chloroplast diagram the anchor for the whole lesson.'
};
