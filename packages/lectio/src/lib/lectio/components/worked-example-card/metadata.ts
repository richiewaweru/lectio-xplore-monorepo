import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'WorkedExampleCard',
	id: 'worked-example-card',
	name: 'WorkedExampleCard',
	phase: 3,

	role: "Shows reasoning in action step by step, each step justified",

	cognitiveJob: "Watch reasoning in action",
	subjects: ["universal"],
	behaviourModes: ['static', 'step-reveal', 'accordion', 'compare'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":false},
	capacity: {"stepsMax":6,"stepsWarning":4,"stepLabelMaxWords":12,"stepContentMaxWords":80},

	teachingIntent: 'show-how',
	status: 'stable',
	sectionField: 'worked_example',
	shadcnPrimitive: "Card + Collapsible"
} satisfies LectioComponentPublicMetadata;

