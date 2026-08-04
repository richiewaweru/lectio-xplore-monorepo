import { describe, expect, it } from 'vitest';

import { validateDiagramFile } from './media-utils';

describe('validateDiagramFile', () => {
	it('classifies valid raster files', () => {
		const file = new File(['x'], 'diagram.png', { type: 'image/png' });
		expect(validateDiagramFile(file)).toEqual({ ok: true, kind: 'raster' });
	});

	it('classifies valid svg files by extension', () => {
		const file = new File(['<svg></svg>'], 'diagram.svg', { type: '' });
		expect(validateDiagramFile(file)).toEqual({ ok: true, kind: 'svg' });
	});

	it('rejects unsupported file types', () => {
		const file = new File(['x'], 'diagram.txt', { type: 'text/plain' });
		const result = validateDiagramFile(file);
		expect(result.ok).toBe(false);
		if (!result.ok) {
			expect(result.reason).toBe('Use PNG, JPEG, WebP, or GIF.');
		}
	});
});
