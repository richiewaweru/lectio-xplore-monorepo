import { describe, expect, it } from 'vitest';

import { mapPackSectionsToCanvas } from './v3-print-canvas';

describe('mapPackSectionsToCanvas', () => {
	it('maps pack sections into CanvasSection objects with mergedFields payload', () => {
		const source = [
			{
				section_id: 'orient',
				header: { title: 'Orientation' },
				explanation: { body: 'hello' }
			}
		];

		const canvas = mapPackSectionsToCanvas(source);
		expect(canvas).toHaveLength(1);
		expect(canvas[0]?.id).toBe('orient');
		expect(canvas[0]?.title).toBe('Orientation');
		expect(canvas[0]?.mergedFields).toEqual(source[0]);
		expect(canvas[0]?.components).toEqual([]);
	});

	it('falls back to section_id for title when header title is missing', () => {
		const source = [{ section_id: 'practice-1', title: 'Legacy Title' }];
		const canvas = mapPackSectionsToCanvas(source);
		expect(canvas[0]?.title).toBe('practice-1');
	});

	it('preserves ordering metadata in mergedFields', () => {
		const source = [
			{
				section_id: 'ordered',
				header: { title: 'Ordered Section' },
				_component_order: ['diagram', 'explanation'],
				_component_positions: { diagram: 0, explanation: 1 },
				explanation: { body: 'Second block' },
				diagram: { image_url: 'https://cdn.example/first.png', caption: 'First block' }
			}
		];

		const canvas = mapPackSectionsToCanvas(source);
		expect(canvas[0]?.mergedFields._component_order).toEqual(['diagram', 'explanation']);
		expect(canvas[0]?.mergedFields._component_positions).toEqual({
			diagram: 0,
			explanation: 1
		});
	});
});
