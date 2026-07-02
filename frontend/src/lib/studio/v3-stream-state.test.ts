import { describe, expect, it } from 'vitest';

import type { CanvasSection } from '$lib/types/v3';

import {
	applyComponentPatchedToCanvas,
	applyComponentReadyToCanvas,
	applySectionWriterFailedToCanvas,
	applyVisualFailedToCanvas
} from './v3-stream-state';

function baseCanvas(): CanvasSection[] {
	return [
		{
			id: 'sec-1',
			title: 'Section 1',
			teacher_labels: '',
			order: 0,
			sectionStatus: 'complete',
			stage2Preview: null,
			renderable: true,
			missingComponents: [],
			missingVisuals: [],
			diagnosticWarnings: [],
			components: [
				{ id: 'c1', teacher_label: 'Hook', status: 'pending', data: null },
				{ id: 'c2', teacher_label: 'Explain', status: 'pending', data: null }
			],
			visual: null,
			questions: [],
			mergedFields: {}
		}
	];
}

describe('v3 stream state reducers', () => {
	it('marks component failed when component_ready is missing section_field', () => {
		const result = applyComponentReadyToCanvas(baseCanvas(), {
			section_id: 'sec-1',
			component_id: 'c1',
			data: { body: 'hello' }
		});
		expect(result.warning).toContain('section_field');
		expect(result.canvas[0]?.components[0]?.status).toBe('failed');
		expect(result.canvas[0]?.components[0]?.data).toEqual({ body: 'hello' });
	});

	it('marks component failed when component_patched is missing section_field', () => {
		const result = applyComponentPatchedToCanvas(baseCanvas(), {
			section_id: 'sec-1',
			component_id: 'c2',
			data: { body: 'patched' }
		});
		expect(result.warning).toContain('section_field');
		expect(result.canvas[0]?.components[1]?.status).toBe('failed');
		expect(result.canvas[0]?.components[1]?.data).toEqual({ body: 'patched' });
	});

	it('marks all section components failed on section_writer_failed', () => {
		const result = applySectionWriterFailedToCanvas(baseCanvas(), {
			section_id: 'sec-1',
			errors: ['timeout'],
			warnings: ['retry exhausted']
		});
		expect(result.warning).toContain('sec-1');
		expect(result.canvas[0]?.components.every((c) => c.status === 'failed')).toBe(true);
		expect(result.canvas[0]?.components[0]?.data).toEqual({
			errors: ['timeout'],
			warnings: ['retry exhausted']
		});
	});

	it('merges component_ready into a skeleton-seeded section', () => {
		const canvas = baseCanvas();
		canvas[0] = {
			...canvas[0]!,
			id: 'build',
			components: [
				{
					id: 'explanation-card',
					teacher_label: 'Explain',
					status: 'pending',
					data: null
				}
			],
			mergedFields: { section_id: 'build' }
		};

		const result = applyComponentReadyToCanvas(canvas, {
			section_id: 'build',
			component_id: 'explanation-card',
			section_field: 'explanation',
			data: { body: 'Live explanation', emphasis: [] }
		});

		expect(result.warning).toBeNull();
		expect(result.canvas[0]?.components[0]?.status).toBe('ready');
		expect(result.canvas[0]?.components[0]?.data).toEqual({
			body: 'Live explanation',
			emphasis: []
		});
		expect(result.canvas[0]?.mergedFields.explanation).toEqual({
			body: 'Live explanation',
			emphasis: []
		});
	});

	it('marks section visual failed on visual_failed', () => {
		const canvas = baseCanvas();
		canvas[0]!.visual = {
			id: 'visual-sec-1',
			status: 'pending',
			mode: 'diagram',
			image_url: null,
			frame_index: null
		};

		const result = applyVisualFailedToCanvas(canvas, {
			visual_id: 'vis-1',
			attaches_to: 'sec-1',
			component_id: 'diagram-block',
			parent_visual_id: null,
			mode: 'diagram',
			frame_count: 1,
			error_summary: 'provider timeout'
		});

		expect(result.warning).toContain('provider timeout');
		expect(result.canvas[0]?.visual?.status).toBe('failed');
		expect(result.canvas[0]?.visual?.component_id).toBe('diagram-block');
		expect(result.canvas[0]?.visual?.error_message).toBe('provider timeout');
	});
});
