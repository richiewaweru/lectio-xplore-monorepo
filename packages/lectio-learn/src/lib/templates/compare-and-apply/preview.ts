import type { TemplatePreview } from '$lib/templates/types';

export const compareAndApplyPreview: TemplatePreview = {
	section: {
		section_id: 'chem-compare-01',
		template_id: 'compare-and-apply',
		header: {
			title: 'Alkanes vs alkenes',
			subtitle: 'Use the structural difference to predict behavior',
			subject: 'Chemistry',
			section_number: 'Section 06',
			grade_band: 'secondary',
			objectives:
				['Distinguish saturated and unsaturated hydrocarbons and apply the difference to reactivity.']
		},
		hook: {
			headline: 'Why do two hydrocarbon families act so differently in reactions?',
			body: 'At first glance they look similar, but one bond pattern changes what each family can do. That one structural difference is the whole lesson.',
			anchor: 'the learner must notice a structural contrast that changes behavior'
		},
		explanation: {
			body: 'Alkanes contain only single carbon-carbon bonds, so they are saturated with hydrogen. Alkenes contain at least one carbon-carbon double bond, making them unsaturated and more reactive in addition reactions. The contrast matters because structure drives what kinds of reactions are possible.',
			emphasis: ['single bonds', 'double bond', 'reactivity']
		},
		definition_family: {
			family_title: 'Hydrocarbon families',
			family_intro: 'These two families differ by one load-bearing structural feature.',
			definitions: [
				{
					term: 'Alkane',
					formal: 'A saturated hydrocarbon containing only carbon-carbon single bonds.',
					plain: 'A hydrocarbon family with no carbon-carbon double bonds.'
				},
				{
					term: 'Alkene',
					formal: 'An unsaturated hydrocarbon containing at least one carbon-carbon double bond.',
					plain: 'A hydrocarbon family defined by a carbon-carbon double bond.'
				}
			]
		},
		insight_strip: {
			cells: [
				{ label: 'Alkanes', value: 'Single bonds only', note: 'Lower reactivity' },
				{
					label: 'Alkenes',
					value: 'At least one double bond',
					note: 'More reactive',
					highlight: true
				}
			]
		},
		comparison_grid: {
			title: 'Compare the two families',
			intro: 'Keep the structural contrast visible while you read the consequences.',
			columns: [
				{
					id: 'alkane',
					title: 'Alkane',
					summary: 'Saturated hydrocarbons with only single bonds.',
					badge: 'Family A'
				},
				{
					id: 'alkene',
					title: 'Alkene',
					summary: 'Unsaturated hydrocarbons with at least one double bond.',
					badge: 'Family B',
					highlight: true
				}
			],
			rows: [
				{
					criterion: 'Bond pattern',
					values: ['Only single bonds', 'At least one double bond']
				},
				{
					criterion: 'Hydrogen status',
					values: ['Saturated', 'Unsaturated'],
					takeaway: 'This is the key vocabulary distinction'
				},
				{
					criterion: 'Typical reactivity',
					values: ['Lower', 'Higher in addition reactions']
				},
				{
					criterion: 'Example formula',
					values: ['C2H6', 'C2H4']
				}
			],
			apply_prompt:
				'If a molecule has a carbon-carbon double bond, classify it before you predict its reaction.'
		},
		pitfall: {
			misconception: 'All hydrocarbons behave the same',
			correction:
				'The double bond changes the reaction options available, so the family classification matters.',
			example: 'An addition reaction is a clue that the hydrocarbon is unsaturated.'
		},
		practice: {
			problems: [
				{
					difficulty: 'warm',
					question: 'A molecule contains one C=C bond. Which family does it belong to?',
					hints: [{ level: 1, text: 'Use the bond pattern row in the comparison grid.' }],
					solution: {
						approach: 'Classify by the presence of the double bond.',
						answer: 'Alkene'
					},
					writein_lines: 2
				},
				{
					difficulty: 'medium',
					question: 'Why is ethene generally more reactive than ethane?',
					hints: [{ level: 1, text: 'Look at the structure row and the reactivity row together.' }],
					solution: {
						approach: 'Connect the double bond to unsaturation and reactivity.',
						answer: 'Because the double bond makes ethene unsaturated and more reactive.'
					},
					writein_lines: 3
				}
			]
		},
		what_next: {
			body: 'With the family distinction secure, the next step is seeing how alkenes participate in addition reactions.',
			next: 'Addition reactions',
			preview: 'The double bond becomes the site where new atoms can attach.'
		}
	},
	summary:
		'A chemistry contrast lesson that makes the structural comparison do the heavy lifting before practice.'
};
