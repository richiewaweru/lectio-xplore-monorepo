import { describe, expect, it } from 'vitest';

import { isDiagramComponentId, svgFieldFor } from './diagram-media-fields';

describe('diagram media field mapping', () => {
	it('detects diagram component ids', () => {
		expect(isDiagramComponentId('diagram-block')).toBe(true);
		expect(isDiagramComponentId('diagram-compare')).toBe(true);
		expect(isDiagramComponentId('diagram-series')).toBe(true);
		expect(isDiagramComponentId('image-block')).toBe(false);
	});

	it('maps diagram-compare media fields to their svg siblings', () => {
		expect(svgFieldFor('diagram-compare', 'before_media_id')).toBe('before_svg');
		expect(svgFieldFor('diagram-compare', 'after_media_id')).toBe('after_svg');
		expect(svgFieldFor('diagram-compare', 'media_id')).toBeNull();
	});

	it('maps diagram-block and diagram-series media fields to svg_content', () => {
		expect(svgFieldFor('diagram-block', 'media_id')).toBe('svg_content');
		expect(svgFieldFor('diagram-series', 'media_id')).toBe('svg_content');
		expect(svgFieldFor('video-embed', 'media_id')).toBeNull();
	});
});
