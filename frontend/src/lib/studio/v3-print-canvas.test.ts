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
		expect(canvas[0]?.sectionStatus).toBe('complete');
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

	it('adds failed diagnostic-only sections back into the canvas with planned metadata', () => {
		const canvas = mapPackSectionsToCanvas(
			[
				{
					section_id: 'orient',
					header: { title: 'Orientation' }
				}
			],
			[
				{
					section_id: 'orient',
					status: 'complete',
					renderable: true,
					missing_components: [],
					missing_visuals: [],
					warnings: []
				},
				{
					section_id: 'practice',
					status: 'failed',
					renderable: false,
					missing_components: ['practice-stack'],
					missing_visuals: [],
					warnings: ['Writer failed']
				}
			],
			[
				{
					id: 'orient',
					title: 'Orientation',
					role: 'orient',
					visual_required: false,
					transition_note: null,
					components: []
				},
				{
					id: 'practice',
					title: 'Practice',
					role: 'practice',
					visual_required: false,
					transition_note: null,
					components: []
				}
			]
		);

		expect(canvas).toHaveLength(2);
		expect(canvas[1]?.id).toBe('practice');
		expect(canvas[1]?.sectionStatus).toBe('failed');
		expect(canvas[1]?.title).toBe('Practice');
	});
});
