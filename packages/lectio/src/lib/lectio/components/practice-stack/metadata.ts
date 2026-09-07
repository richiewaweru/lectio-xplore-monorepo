import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'PracticeStack',
	id: 'practice-stack',
	name: 'PracticeStack',
	phase: 4,

	role: "Problems at calibrated difficulty with progressive hints and optional solutions",

	cognitiveJob: "Apply understanding under calibrated difficulty",
	subjects: ["universal"],
	behaviourModes: ['hint-toggle', 'accordion', 'progressive-hints', 'flat-list'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":true,"acceptsQuestions":true,"producesAnswerKey":true,"interactive":false,"isMedia":false},
	capacity: {"problemsMin":2,"problemsMax":5,"hintsPerProblemMax":3,"questionMaxWords":100,"hintMaxWords":60},

	teachingIntent: 'practice',
	status: 'stable',
	sectionField: 'practice',
	shadcnPrimitive: "Accordion + Collapsible"
} satisfies LectioComponentPublicMetadata;

