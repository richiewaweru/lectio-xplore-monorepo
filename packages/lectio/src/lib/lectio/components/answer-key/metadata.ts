import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'AnswerKey',
	id: 'answer-key',
	name: 'AnswerKey',
	phase: 4,

	role: 'Provides correct answers with misconception evidence for each diagnostic distractor',
	cognitiveJob: 'Support diagnostic marking',
	subjects: ['universal'],
	behaviourModes: ['static'] as const satisfies readonly BehaviourMode[],

	capabilities: {
		acceptsMedia: false,
		acceptsQuestions: true,
		producesAnswerKey: true,
		interactive: false,
		isMedia: false
	},
	capacity: { entriesMin: 0, entriesMax: 50 },

	teachingIntent: 'practice',
	status: 'stable',
	sectionField: 'answer_key',
	shadcnPrimitive: 'Card'
} satisfies LectioComponentPublicMetadata;
