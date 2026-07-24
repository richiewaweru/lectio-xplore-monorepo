import { describe, expect, it } from 'vitest';
import type { BlockInstance, MediaReference } from 'lectio';
import type { V3VisualBlock } from '$lib/api/v3';
import {
	currentBlockImageUrl,
	isSingleAssetVisualBlock,
	resolveBlockVisual
} from './visual-regeneration';

const visual = {
	visual_id: 'visual-1',
	attaches_to: 'section-a',
	mode: 'diagram',
	image_url: 'https://example.test/generated.png'
} as V3VisualBlock;

function block(componentId: string, content: Record<string, unknown>): BlockInstance {
	return { id: componentId, component_id: componentId, content, position: 0 };
}

describe('visual regeneration matching', () => {
	it('matches a diagram by section and exact current URL', () => {
		const diagram = block('diagram-block', { image_url: visual.image_url });
		expect(resolveBlockVisual(diagram, 'section-a', [visual])).toBe(visual);
		expect(resolveBlockVisual(diagram, 'section-b', [visual])).toBeUndefined();
		expect(resolveBlockVisual(diagram, 'section-a', [{ ...visual, image_url: 'other' }])).toBeUndefined();
	});

	it('resolves an image block URL through its media reference', () => {
		const image = block('image-block', { media_id: 'media-1' });
		const media = {
			'media-1': { id: 'media-1', type: 'image', url: visual.image_url }
		} as Record<string, MediaReference>;
		expect(currentBlockImageUrl(image, media)).toBe(visual.image_url);
		expect(resolveBlockVisual(image, 'section-a', [visual], media)).toBe(visual);
	});

	it('rejects ambiguous and unsupported visual blocks', () => {
		const diagram = block('diagram-block', { image_url: visual.image_url });
		expect(resolveBlockVisual(diagram, 'section-a', [visual, { ...visual }])).toBeUndefined();
		for (const componentId of [
			'diagram-series',
			'diagram-compare',
			'simulation-block',
			'video-embed'
		]) {
			expect(isSingleAssetVisualBlock(componentId)).toBe(false);
			expect(resolveBlockVisual(block(componentId, {}), 'section-a', [visual])).toBeUndefined();
		}
	});
});
