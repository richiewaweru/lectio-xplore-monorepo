import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'QuizCheck',
	id: 'quiz-check',
	name: 'QuizCheck',
	phase: 4,

	role: "Quick concept check with immediate feedback mid-section",

	cognitiveJob: "Verify understanding immediately",
	subjects: ["universal"],
	behaviourModes: ['static'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":true,"acceptsQuestions":true,"producesAnswerKey":true,"interactive":false,"isMedia":false},
	capacity: {"optionsMin":3,"optionsMax":4,"questionMaxWords":60,"optionMaxWords":20},

	teachingIntent: 'practice',
	status: 'stable',
	sectionField: 'quiz',
	shadcnPrimitive: "Card + Button"
} satisfies LectioComponentPublicMetadata;

