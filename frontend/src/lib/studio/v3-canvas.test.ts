import { describe, expect, it } from 'vitest';

import type { BlueprintPreviewDTO } from '$lib/types/v3';

import {
	buildCanvasSkeleton,
	mergeComponentField,
	mergeDiagramFrame,
	mergePracticeProblem
} from './v3-canvas';

const blueprintFixture = (): BlueprintPreviewDTO => ({
	blueprint_id: 'bp-1',
	resource_type: 'lesson',
	title: 'Test',
	template_id: 'guided-concept-path',
	anchor: null,
	section_plan: [
		{
			id: 'sec-a',
			title: 'Intro',
			order: 2,
			learning_intent: '',
			visual_required: true,
			components: [
				{
					component_id: 'c1',
					teacher_label: 'Hook',
					content_intent: ''
				}
			]
		},
		{
			id: 'sec-b',
			title: 'Body',
			order: 1,
			learning_intent: '',
			visual_required: false,
			components: []
		}
	],
	question_plan: [
		{
			id: 'q1',
			difficulty: 'warm',
			expected_answer: '',
			diagram_required: false,
			attaches_to_section_id: 'sec-a'
		}
	],
	register_summary: '',
	support_summary: []
});

describe('buildCanvasSkeleton', () => {
	it('sorts sections by order and wires questions to sections', () => {
		const sections = buildCanvasSkeleton(blueprintFixture());
		expect(sections.map((s) => s.id)).toEqual(['sec-b', 'sec-a']);
		const secA = sections.find((s) => s.id === 'sec-a');
		expect(secA?.visual).not.toBeNull();
		expect(secA?.questions.map((q) => q.id)).toEqual(['q1']);
		const secB = sections.find((s) => s.id === 'sec-b');
		expect(secB?.visual).toBeNull();
	});

	it('initialises mergedFields as empty objects', () => {
		const sections = buildCanvasSkeleton(blueprintFixture());
		for (const s of sections) {
			expect(s.mergedFields).toEqual({});
		}
	});
});

describe('merge helpers', () => {
	it('mergeComponentField sets keyed Lectio fields', () => {
		const next = mergeComponentField({}, 'hook', { headline: 'Hi' });
		expect(next.hook).toEqual({ headline: 'Hi' });
	});

	it('mergeDiagramFrame single-frame uses diagram', () => {
		const next = mergeDiagramFrame({}, { image_url: 'http://x', frame_index: null });
		expect(next.diagram).toMatchObject({ image_url: 'http://x' });
	});

	it('mergeDiagramFrame series expands diagrams array', () => {
		let merged = mergeDiagramFrame({}, { image_url: 'u0', frame_index: 0 });
		merged = mergeDiagramFrame(merged, { image_url: 'u1', frame_index: 1 });
		const ds = merged.diagram_series as { diagrams: Array<{ image_url: string }> };
		expect(ds.diagrams).toHaveLength(2);
		expect(ds.diagrams[0].image_url).toBe('u0');
		expect(ds.diagrams[1].image_url).toBe('u1');
	});

	it('mergePracticeProblem upserts rows keyed by _qid', () => {
		let merged = mergePracticeProblem({}, 'q1', 'warm', {
			question: 'Two plus two?',
			hints: []
		});
		let practice = merged.practice as { problems: Array<{ _qid?: string; question: string }> };
		expect(practice.problems).toHaveLength(1);
		expect(practice.problems[0]._qid).toBe('q1');

		merged = mergePracticeProblem(merged, 'q1', 'warm', {
			question: 'Updated?',
			hints: []
		});
		practice = merged.practice as { problems: Array<{ question: string }> };
		expect(practice.problems).toHaveLength(1);
		expect(practice.problems[0].question).toBe('Updated?');
	});
});
