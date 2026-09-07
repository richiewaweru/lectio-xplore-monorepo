import type { TemplatePreview } from '$lib/templates/types';

export const classificationPreview: TemplatePreview = {
	section: {
		section_id: 'civics-distinction-01',
		template_id: 'classification',
		header: {
			title: 'Unitary, federal, and confederal systems',
			subtitle: 'Classify where power mainly sits and how it is shared',
			subject: 'Civics',
			section_number: 'Section 07',
			grade_band: 'secondary',
			objectives:
				['Distinguish how three government systems distribute power between national and regional levels.']
		},
		hook: {
			headline: 'When one country has several regions, who really holds the power?',
			body: 'The answer changes depending on the system. If learners mix the systems together, the political consequences become hard to reason about.',
			anchor: 'power distribution is the decision point that separates the systems'
		},
		explanation: {
			body: 'A unitary system concentrates final authority at the national level. A federal system divides power between national and regional governments under a shared constitution. A confederal system keeps primary power with the member states, which cooperate through a weaker central body. The differences matter because they shape lawmaking, autonomy, and conflict resolution.',
			emphasis: ['concentrates', 'divides power', 'member states']
		},
		definition_family: {
			family_title: 'Government systems',
			family_intro:
				'Each system answers the same question differently: where does final authority sit?',
			definitions: [
				{
					term: 'Unitary system',
					formal: 'A state in which final authority rests with the national government.',
					plain: 'The center holds the main power.'
				},
				{
					term: 'Federal system',
					formal:
						'A state that constitutionally divides authority between national and regional governments.',
					plain: 'Power is shared between levels.'
				},
				{
					term: 'Confederal system',
					formal:
						'A union of states that keep primary authority while delegating limited powers to a central body.',
					plain: 'The member states stay strongest.'
				}
			]
		},
		insight_strip: {
			cells: [
				{ label: 'Unitary', value: 'Center strongest', note: 'Least regional autonomy' },
				{
					label: 'Federal',
					value: 'Power shared',
					note: 'Balanced structure',
					highlight: true
				},
				{ label: 'Confederal', value: 'States strongest', note: 'Weak central body' }
			]
		},
		comparison_grid: {
			title: 'Classify the systems',
			intro: 'Use the same criteria across all three categories before you judge any example.',
			columns: [
				{
					id: 'unitary',
					title: 'Unitary',
					summary: 'National government holds final authority.'
				},
				{
					id: 'federal',
					title: 'Federal',
					summary: 'Authority is divided between levels.',
					highlight: true
				},
				{
					id: 'confederal',
					title: 'Confederal',
					summary: 'Member states keep primary authority.'
				}
			],
			rows: [
				{
					criterion: 'Power center',
					values: ['National level', 'Shared levels', 'Member states']
				},
				{
					criterion: 'Regional autonomy',
					values: ['Limited', 'Protected', 'Very high']
				},
				{
					criterion: 'Central body strength',
					values: ['Strong', 'Strong but limited', 'Weaker']
				},
				{
					criterion: 'Best clue',
					values: [
						'One clear center',
						'Constitutional sharing',
						'Alliance of strong states'
					]
				}
			],
			apply_prompt:
				'When you classify a real country, ask first where final authority can overrule the others.'
		},
		practice: {
			problems: [
				{
					difficulty: 'warm',
					question:
						'A country constitutionally splits powers between a national parliament and regional states. Which system does that describe?',
					hints: [{ level: 1, text: 'Find the row about power center and autonomy.' }],
					solution: {
						approach: 'Match the constitutional power-sharing clue to the grid.',
						answer: 'Federal system'
					},
					writein_lines: 2
				},
				{
					difficulty: 'medium',
					question:
						'Why would a confederal system usually give more autonomy to member states than a unitary system?',
					hints: [{ level: 1, text: 'Compare where final authority sits in each system.' }],
					solution: {
						approach: 'Use the final-authority row to explain the autonomy difference.',
						answer:
							'Because member states keep primary authority in a confederal system, unlike a unitary system where the center is strongest.'
					},
					writein_lines: 4
				}
			]
		},
		what_next: {
			body: 'Once the systems are classified, the next step is applying the distinction to real-world countries and constitutions.',
			next: 'Constitutions in practice',
			preview: 'Examples become easier once the classification criteria are stable.'
		}
	},
	summary:
		'A civics classification lesson that uses a three-way comparison grid to keep the categories separate.'
};
