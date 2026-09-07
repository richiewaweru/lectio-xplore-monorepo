import { lectioComponentModules } from '$lib/lectio/registry/components';
import type { LectioContentModule } from '$lib/lectio/core/types';

export const CONTENT_CONTRACT_TEMPLATE_IDS = ['guided-concept-path', 'open-canvas'] as const;
export const CONTENT_CONTRACT_EXCLUDED_COMPONENT_IDS = ['image-block', 'video-embed', 'glossary-inline'] as const;

const EXCLUDED_IDS = new Set<string>(CONTENT_CONTRACT_EXCLUDED_COMPONENT_IDS);

export function isContentContractEligible(module: LectioContentModule): boolean {
	return module.metadata.sectionField !== null && !EXCLUDED_IDS.has(module.metadata.id);
}

export const CONTENT_CONTRACT_COMPONENT_IDS = lectioComponentModules
	.filter((module) => isContentContractEligible(module))
	.map((module) => module.metadata.id);
