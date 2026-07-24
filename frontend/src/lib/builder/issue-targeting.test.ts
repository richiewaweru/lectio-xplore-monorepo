import { describe, expect, it, vi } from 'vitest';
import type { LessonDocument } from 'lectio';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

vi.mock('lectio', () => ({
	getEditSchema: (componentId: string) => componentId === 'unknown' ? null : { component_id: componentId, fields: [] },
	getEmptyContent: () => ({}),
	getFieldComponentMap: () => ({
		practice: 'practice-stack',
		quiz: 'quiz-check',
		short_answer: 'short-answer',
		reflection: 'reflection-prompt'
	})
}));

import {
	repairNoteForIssue,
	resolveTextIssueTarget,
	resolveVisualIssueTarget
} from './issue-targeting';

const document = {
	sections: [{ id: 'practice', block_ids: ['explain', 'practice-block', 'diagram', 'image'] }],
	blocks: {
		explain: { id: 'explain', component_id: 'explanation-block', content: {}, position: 0 },
		'practice-block': { id: 'practice-block', component_id: 'practice-stack', content: {}, position: 1 },
		diagram: { id: 'diagram', component_id: 'diagram-block', content: {}, position: 2 },
		image: { id: 'image', component_id: 'image-block', content: {}, position: 3 }
	}
} as unknown as LessonDocument;

describe('Builder issue targeting', () => {
	it('builds a bounded actionable repair note from the issue message', () => {
		const issue = {
			id: 'repair-note',
			severity: 'major',
			message: `  Missing planned content: ${'detail '.repeat(80)}  `,
			kind: 'missing_planned_content',
			resolved: false
		};
		const note = repairNoteForIssue(issue);

		expect(note).toMatch(/^Fix this issue in the block: Missing planned content:/);
		expect(note.length).toBeLessThanOrEqual(300);
		expect(note.endsWith('…')).toBe(true);
	});

	it('prefers a valid explicit AI-capable block target', () => {
		expect(resolveTextIssueTarget(document, 'practice', {
			id: 'i1', severity: 'major', message: 'Fix it', kind: 'clarity',
			target_block_id: 'explain', resolved: false
		})).toBe('explain');
	});

	it('resolves component and generated-reference targets', () => {
		expect(resolveTextIssueTarget(document, 'practice', {
			id: 'i2', severity: 'major', message: 'Fix it', kind: 'clarity',
			repair_target_id: 'component:practice:explanation-block', resolved: false
		})).toBe('explain');
		expect(resolveTextIssueTarget(document, 'practice', {
			id: 'i3', severity: 'major', message: 'Add questions', kind: 'missing_planned_content',
			generated_ref: 'practice.practice.problems[0].question',
			repair_target_id: 'questions:practice', resolved: false
		})).toBe('practice-block');
		expect(resolveTextIssueTarget(document, 'practice', {
			id: 'i4', severity: 'major', message: 'Add questions', kind: 'missing_planned_content',
			generated_ref: 'practice1.practice.problems[0].question',
			repair_target_id: 'questions:practice1', resolved: false
		})).toBe('practice-block');
	});

	it('does not guess when a generated reference has zero or multiple matching blocks', () => {
		const ambiguous = structuredClone(document);
		ambiguous.sections[0]!.block_ids.push('practice-block-2');
		ambiguous.blocks['practice-block-2'] = {
			id: 'practice-block-2',
			component_id: 'practice-stack',
			content: {},
			position: 4
		};
		const issue = {
			id: 'ambiguous',
			severity: 'minor',
			message: 'Rewrite the question.',
			kind: 'visual_mismatch',
			generated_ref: 'practice.practice.problems[0].question',
			repair_target_id: 'questions:practice',
			resolved: false
		};

		expect(resolveTextIssueTarget(ambiguous, 'practice', issue)).toBeUndefined();
		expect(resolveTextIssueTarget(document, 'practice', {
			...issue,
			generated_ref: 'practice.unknown.question'
		})).toBeUndefined();
	});

	it('leaves section-level, missing, and manual-only targets advisory', () => {
		for (const repair_target_id of [
			'section:practice',
			'component:practice:missing-component',
			'component:practice:image-block'
		]) {
			expect(resolveTextIssueTarget(document, 'practice', {
				id: repair_target_id, severity: 'major', message: 'Review', kind: 'anchor_drift',
				repair_target_id, resolved: false
			})).toBeUndefined();
		}
	});

	it('uses explicit then first visual block for visual editing', () => {
		expect(resolveVisualIssueTarget(document, 'practice', 'image')).toBe('image');
		expect(resolveVisualIssueTarget(document, 'practice')).toBe('diagram');
	});

	it('keeps the checked-in regression fixture wired to repair and advisory behavior', () => {
		const fixture = JSON.parse(readFileSync(
			join(process.cwd(), 'src/lib/builder/fixtures/block-ai-regression.json'),
			'utf8'
		)) as {
			lesson: LessonDocument;
			visual_blocks: Array<{ visual_id: string; status: string; qc_reasons: string[] }>
		};
		const section = fixture.lesson.sections[0] as typeof fixture.lesson.sections[0] & {
			meta: { issues: Array<Parameters<typeof resolveTextIssueTarget>[2]> }
		};
		const repair = section.meta.issues.find((issue) => issue.id === 'repair-practice')!;
		const advisory = section.meta.issues.find((issue) => issue.id === 'advisory-anchor')!;
		const ambiguousSection = fixture.lesson.sections.find((item) => item.id === 'ambiguous') as
			| (typeof fixture.lesson.sections[0] & {
					meta: { issues: Array<Parameters<typeof resolveTextIssueTarget>[2]> }
			  })
			| undefined;
		const ambiguous = ambiguousSection?.meta.issues.find(
			(issue) => issue.id === 'ambiguous-practice'
		);

		expect(resolveTextIssueTarget(fixture.lesson, section.id, repair)).toBe('practice-questions');
		expect(resolveTextIssueTarget(fixture.lesson, section.id, advisory)).toBeUndefined();
		expect(ambiguousSection).toBeDefined();
		expect(ambiguous).toBeDefined();
		expect(resolveTextIssueTarget(fixture.lesson, ambiguousSection!.id, ambiguous!)).toBeUndefined();
		expect(fixture.lesson.blocks['empty-explanation']?.content.body).toBe('');
		expect(fixture.lesson.blocks['written-explanation']?.content.body).toBe(
			'Plants turn light into stored chemical energy.'
		);
		expect(fixture.visual_blocks).toEqual([
			expect.objectContaining({
				visual_id: 'vis-build-0',
				status: 'flagged_quality',
				qc_reasons: expect.arrayContaining(['Reaction labels are incomplete'])
			})
		]);
		expect(section.meta.issues).toEqual(
			expect.arrayContaining([
				expect.objectContaining({
					id: 'repair-visual',
					kind: 'visual_quality_flagged',
					visual_id: 'vis-build-0'
				})
			])
		);
	});
});
