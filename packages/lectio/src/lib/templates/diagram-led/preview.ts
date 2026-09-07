import type { TemplatePreview } from '$lib/templates/types';

const mitosisStep1 = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 220" fill="none">
  <rect width="420" height="220" rx="26" fill="#F0FDF4"/>
  <circle cx="210" cy="110" r="78" fill="#DCFCE7" stroke="#16A34A" stroke-width="4"/>
  <circle cx="210" cy="110" r="30" fill="#BBF7D0" stroke="#15803D" stroke-width="3"/>
  <path d="M184 90C200 70 220 70 236 90" stroke="#2563EB" stroke-width="6" stroke-linecap="round"/>
  <path d="M184 130C200 150 220 150 236 130" stroke="#2563EB" stroke-width="6" stroke-linecap="round"/>
</svg>`;
const mitosisStep2 = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 220" fill="none">
  <rect width="420" height="220" rx="26" fill="#F0FDF4"/>
  <circle cx="210" cy="110" r="78" fill="#DCFCE7" stroke="#16A34A" stroke-width="4"/>
  <path d="M180 76L200 110L180 144" stroke="#2563EB" stroke-width="6" stroke-linecap="round"/>
  <path d="M240 76L220 110L240 144" stroke="#2563EB" stroke-width="6" stroke-linecap="round"/>
  <line x1="210" y1="44" x2="210" y2="176" stroke="#F97316" stroke-width="4" stroke-dasharray="8 8"/>
</svg>`;
const mitosisStep3 = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 220" fill="none">
  <rect width="420" height="220" rx="26" fill="#F0FDF4"/>
  <circle cx="150" cy="110" r="58" fill="#DCFCE7" stroke="#16A34A" stroke-width="4"/>
  <circle cx="270" cy="110" r="58" fill="#DCFCE7" stroke="#16A34A" stroke-width="4"/>
  <path d="M138 94C146 80 154 80 162 94" stroke="#2563EB" stroke-width="5" stroke-linecap="round"/>
  <path d="M258 126C266 140 274 140 282 126" stroke="#2563EB" stroke-width="5" stroke-linecap="round"/>
</svg>`;

export const diagramLedPreview: TemplatePreview = {
	section: {
		section_id: 'bio-diagram-led-01',
		template_id: 'diagram-led',
		header: {
			title: 'Stages of mitosis',
			subtitle: 'Use the sequence of cell changes as the teaching spine',
			subject: 'Biology',
			section_number: 'Section 09',
			grade_band: 'secondary',
			objectives: ['Track how one cell moves through visible mitosis stages before division.']
		},
		diagram: {
			svg_content: mitosisStep1,
			caption: 'A cell in prophase — chromosomes condense inside the nucleus.',
			alt_text: 'Diagram of a cell in prophase showing condensed chromosomes inside a circular nucleus.'
		},
		hook: {
			headline: 'How does one cell become two identical cells?',
			body: 'Mitosis makes sense when the learner sees the cell change stage by stage. The sequence is the explanation.',
			anchor: 'cell division is easiest to understand as a visible progression'
		},
		explanation: {
			body: 'In mitosis, the cell first prepares duplicated genetic material, then aligns it, separates it, and finally finishes division. The stage order matters because each visible change sets up the next one. Watching the sequence gives the learner a map for the vocabulary.',
			emphasis: ['aligns', 'separates', 'stage order']
		},
		diagram_series: {
			title: 'Mitosis sequence',
			diagrams: [
				{
					svg_content: mitosisStep1,
					step_label: 'Prophase',
					caption: 'Chromosomes condense and the nucleus begins to reorganize.'
				},
				{
					svg_content: mitosisStep2,
					step_label: 'Metaphase',
					caption: 'Chromosomes line up across the middle of the cell.'
				},
				{
					svg_content: mitosisStep3,
					step_label: 'Telophase',
					caption: 'Two nuclei form as the cell finishes separating.'
				}
			]
		},
		process: {
			title: 'Read the sequence',
			intro: 'Use the visuals in order so the vocabulary lands on something concrete.',
			steps: [
				{
					number: 1,
					action: 'Spot the structural shift',
					detail: 'Ask what changed in the cell compared with the stage before it.'
				},
				{
					number: 2,
					action: 'Name the stage',
					detail: 'Attach the stage label only after the visible change is clear.'
				},
				{
					number: 3,
					action: 'Predict the next stage',
					detail: 'Use the current stage to anticipate what the next image should show.'
				}
			]
		},
		glossary: {
			terms: [
				{
					term: 'Mitosis',
					definition: 'The process that produces two genetically similar cells.'
				},
				{
					term: 'Metaphase',
					definition: 'The stage where chromosomes align in the middle.'
				}
			]
		},
		practice: {
			problems: [
				{
					difficulty: 'warm',
					question: 'Which stage is defined by chromosomes lining up across the middle?',
					hints: [{ level: 1, text: 'Look for the central alignment diagram.' }],
					solution: {
						approach: 'Match the visible arrangement to the stage name.',
						answer: 'Metaphase'
					},
					writein_lines: 2
				},
				{
					difficulty: 'medium',
					question: 'Why does the order of mitosis stages matter for understanding the process?',
					hints: [{ level: 1, text: 'Each stage prepares the next visible change.' }],
					solution: {
						approach: 'Describe the sequence as a chain of setup and consequence.',
						answer: 'Because each stage creates the conditions for the next stage to happen.'
					},
					writein_lines: 3
				}
			]
		},
		what_next: {
			body: 'Once the visible sequence is secure, the next step is comparing mitosis with meiosis.',
			next: 'Mitosis vs meiosis',
			preview:
				'The distinction matters because only one process produces genetically varied cells.'
		}
	},
	summary:
		'A biology lesson where a staged diagram sequence carries the core meaning of the page.'
};
