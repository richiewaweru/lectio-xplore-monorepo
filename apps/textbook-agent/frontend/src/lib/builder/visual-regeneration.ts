import type { BlockInstance, MediaReference } from 'lectio';
import type { V3VisualBlock } from '$lib/api/v3';

const REGENERATABLE_COMPONENT_IDS = new Set(['diagram-block', 'image-block']);

export function isSingleAssetVisualBlock(componentId: string): boolean {
	return REGENERATABLE_COMPONENT_IDS.has(componentId);
}

function sectionRefMatches(reference: string, sectionId: string): boolean {
	return (
		reference === sectionId ||
		reference.startsWith(`${sectionId}.`) ||
		reference.replace(/\d+$/, '') === sectionId
	);
}

export function currentBlockImageUrl(
	block: BlockInstance,
	media: Record<string, MediaReference>
): string | undefined {
	if (block.component_id === 'diagram-block') {
		return typeof block.content.image_url === 'string' && block.content.image_url
			? block.content.image_url
			: undefined;
	}
	if (block.component_id === 'image-block') {
		const mediaId = typeof block.content.media_id === 'string' ? block.content.media_id : '';
		const reference = mediaId ? media[mediaId] : undefined;
		return reference?.type === 'image' && reference.url ? reference.url : undefined;
	}
	return undefined;
}

export function resolveBlockVisual(
	block: BlockInstance,
	sectionId: string,
	visuals: V3VisualBlock[],
	media: Record<string, MediaReference> = {}
): V3VisualBlock | undefined {
	if (!isSingleAssetVisualBlock(block.component_id)) return undefined;
	const imageUrl = currentBlockImageUrl(block, media);
	if (!imageUrl) return undefined;
	const matches = visuals.filter(
		(visual) => sectionRefMatches(visual.attaches_to, sectionId) && visual.image_url === imageUrl
	);
	return matches.length === 1 ? matches[0] : undefined;
}
