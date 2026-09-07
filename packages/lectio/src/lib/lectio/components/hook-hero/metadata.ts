import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'HookHero',
	id: 'hook-hero',
	name: 'HookHero',
	phase: 1,

	role: "Creates felt need before explanation arrives",

	cognitiveJob: "Create felt need",
	subjects: ["universal"],
	behaviourModes: ['static'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":true,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":false},
	capacity: {"headlineMaxWords":12,"bodyMaxWords":80},

	teachingIntent: 'engage',
	status: 'stable',
	sectionField: 'hook',
	shadcnPrimitive: "none - pure layout",
	generationHint:
		'Create felt need before explanation arrives. Can include an image via image for visual hooks.'
} satisfies LectioComponentPublicMetadata;

