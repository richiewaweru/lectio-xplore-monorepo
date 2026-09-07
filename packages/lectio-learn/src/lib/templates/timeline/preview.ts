import type { TemplatePreview } from '$lib/templates/types';

export const timelinePreview: TemplatePreview = {
	section: {
		section_id: 'hist-timeline-01',
		template_id: 'timeline',
		header: {
			title: 'How germ theory took hold',
			subtitle: 'A chronology of evidence, debate, and acceptance',
			subject: 'History',
			section_number: 'Section 11',
			grade_band: 'secondary',
			objectives: ['Trace how observations and experiments shifted medicine toward germ theory.']
		},
		hook: {
			headline:
				'Why did doctors once reject the idea that invisible organisms caused disease?',
			body: 'The answer was not one experiment or one person. It was a sequence of observations, resistance, and stronger evidence over time.',
			anchor: 'scientific acceptance arrives through chronology, not one isolated fact'
		},
		explanation: {
			body: 'Germ theory took hold only after repeated observations and experiments made older explanations harder to defend. The chronology matters because each event strengthened the evidence, changed practice, or revealed the cost of ignoring contamination. Reading the sequence shows why acceptance was slow and why it eventually became unavoidable.',
			emphasis: ['observations', 'stronger evidence', 'changed practice']
		},
		timeline: {
			title: 'The road to germ theory',
			intro:
				'Follow the major turns in order and watch how the idea moved from suspicion to acceptance.',
			events: [
				{
					id: 'leeuwenhoek',
					year: '1670s',
					title: 'Microscopic life observed',
					summary:
						'Antonie van Leeuwenhoek described microscopic organisms, proving an unseen world existed.',
					impact: 'Observation made later germ explanations possible.',
					tags: ['Observation', 'Microscope']
				},
				{
					id: 'semmelweis',
					year: '1847',
					title: 'Handwashing evidence',
					summary:
						'Ignaz Semmelweis showed that physician handwashing sharply reduced deaths in maternity wards.',
					impact: 'Practice changed before the full theory was accepted.',
					tags: ['Evidence', 'Hospitals']
				},
				{
					id: 'pasteur',
					year: '1860s',
					title: 'Experiments challenge spontaneous generation',
					summary:
						'Louis Pasteur demonstrated that microorganisms came from contamination, not spontaneous generation.',
					impact: 'The older theory lost credibility.',
					tags: ['Experiment', 'Turning point']
				},
				{
					id: 'koch',
					year: '1880s',
					title: 'Specific microbes linked to disease',
					summary:
						'Robert Koch connected particular microbes to particular diseases through careful lab work.',
					impact: 'The theory gained precise medical force.',
					tags: ['Causation', 'Medicine']
				}
			],
			closing_takeaway:
				'Germ theory became persuasive because evidence accumulated across observation, practice, and experiment.'
		},
		reflection: {
			prompt: 'Which event feels like the strongest turning point in the story, and why?',
			type: 'open',
			space: 4
		},
		practice: {
			problems: [
				{
					difficulty: 'warm',
					question:
						'Why does Semmelweis appear before Pasteur in the timeline if Pasteur gave stronger theoretical support later?',
					hints: [{ level: 1, text: 'Think about evidence in practice versus theory.' }],
					solution: {
						approach:
							'Use the sequence to explain how practice and theory can arrive at different times.',
						answer:
							'Because evidence from handwashing came earlier, even before the theory was widely accepted.'
					},
					writein_lines: 3
				},
				{
					difficulty: 'medium',
					question:
						"How did Koch's work strengthen germ theory beyond Pasteur's challenge to spontaneous generation?",
					hints: [
						{
							level: 1,
							text: 'Compare general contamination evidence with disease-specific causation.'
						}
					],
					solution: {
						approach: 'Explain the move from general support to precise causation.',
						answer:
							"Koch linked specific microbes to specific diseases, giving the theory direct medical precision."
					},
					writein_lines: 4
				}
			]
		},
		what_next: {
			body: 'With the chronology secure, the next step is seeing how germ theory reshaped public health practice.',
			next: 'Public health after germ theory',
			preview: 'Sanitation, sterilization, and vaccination policies changed once the theory stuck.'
		}
	},
	summary:
		'A history-style lesson that uses a timeline spine to show why acceptance of germ theory unfolded over decades.'
};
