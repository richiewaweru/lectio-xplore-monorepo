import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'VideoEmbed',
	id: 'video-embed',
	name: 'VideoEmbed',
	phase: 1,

	role: "Embeds a video with caption and print fallback",

	cognitiveJob: "Engage through multimedia",
	subjects: ["universal"],
	behaviourModes: ['static'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":true},
	capacity: {"captionMaxWords":40},

	teachingIntent: 'visualize',
	status: 'stable',
	sectionField: 'video_embed',
	shadcnPrimitive: "iframe"
} satisfies LectioComponentPublicMetadata;

