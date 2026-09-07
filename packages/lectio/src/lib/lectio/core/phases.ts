export const LECTIO_PHASES = {
	1: {
		id: 1 as const,
		name: 'Orient',
		description: 'Set direction, context, purpose, or closure.'
	},
	2: {
		id: 2 as const,
		name: 'Build Knowledge',
		description: 'Define, compare, organize, or anchor key knowledge.'
	},
	3: {
		id: 3 as const,
		name: 'Model',
		description: 'Show a method, example, or process before independent work.'
	},
	4: {
		id: 4 as const,
		name: 'Practice and Check',
		description:
			'Let students answer, practise, retrieve, reflect, or show thinking.'
	},
	5: {
		id: 5 as const,
		name: 'Address Mistakes',
		description: 'Warn against misconceptions or correct common errors.'
	},
	6: {
		id: 6 as const,
		name: 'Visualize',
		description:
			'Make spatial, relational, chronological, or visual structure visible.'
	},
	7: {
		id: 7 as const,
		name: 'Interact',
		description: 'Let learners manipulate, observe, or explore a concept interactively.'
	}
} as const;

export type LectioPhaseId = keyof typeof LECTIO_PHASES;
