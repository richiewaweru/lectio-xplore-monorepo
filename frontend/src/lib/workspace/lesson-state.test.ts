import type { LessonDocument } from 'lectio';
import { describe, expect, it } from 'vitest';

import type { BuilderLessonSummary } from '$lib/builder/api/lesson-crud';
import type { V3PackDocument } from '$lib/studio/v3-pack-to-lectio-document';
import type { V3GenerationHistoryItem } from '$lib/types/v3';
import fixture from './__fixtures__/lesson-state.json';
import { deriveLessonRows } from './lesson-state';

const lessons = fixture.lessons as BuilderLessonSummary[];
const generations = fixture.generations as V3GenerationHistoryItem[];

const writingPack = {
	status: 'streaming_preview',
	progress: { stage: 'running', sections: { intro: 'ready', explain: 'ready', practice: 'pending' } },
	sections: [{ section_id: 'intro' }, { section_id: 'explain' }]
} as unknown as V3PackDocument;

const attentionPack = {
	status: 'final_with_warnings',
	progress: { stage: 'completed', sections: { intro: 'ready', practice: 'ready' } },
	sections: [{ section_id: 'intro' }, { section_id: 'practice' }],
	section_diagnostics: [],
	booklet_issues: [
		{
			issue_id: 'visual-issue',
			section_id: 'practice',
			severity: 'minor',
			category: 'visual_quality_flagged',
			message: 'Review this image.'
		}
	]
} as unknown as V3PackDocument;

const readyPack = {
	status: 'final_ready',
	progress: { stage: 'completed', sections: { intro: 'ready', explain: 'ready', practice: 'ready' } },
	sections: [{ section_id: 'intro' }, { section_id: 'explain' }, { section_id: 'practice' }],
	section_diagnostics: [],
	booklet_issues: []
} as unknown as V3PackDocument;

describe('deriveLessonRows', () => {
	it('derives writing, attention, ready, draft, and failed states in updated order', () => {
		const rows = deriveLessonRows({
			lessons,
			generations,
			generationDocumentsById: {
				'gen-writing': writingPack,
				'gen-attention': attentionPack,
				'gen-ready': readyPack
			}
		});

		expect(rows.map((row) => [row.id, row.state])).toEqual([
			['lesson-writing', 'writing'],
			['lesson-attention', 'attention'],
			['lesson-ready', 'ready'],
			['lesson-draft', 'draft'],
			['lesson-failed', 'attention']
		]);
		expect(rows[0]).toMatchObject({
			classLabel: 'Year 7 Science',
			subject: 'Science',
			sectionsDone: 2,
			sectionsTotal: 4,
			href: '/builder/lesson-writing?generation_id=gen-writing'
		});
		expect(rows[1].flagCount).toBe(1);
		expect(rows[2].href).toBe('/builder/lesson-ready');
	});

	it('excludes resolved and dismissed flags', () => {
		const resolvedDocument = {
			sections: [
				{
					id: 'practice',
					meta: {
						issues: [
							{
								id: 'visual-issue',
								severity: 'minor',
								message: 'Review this image.',
								kind: 'visual_quality_flagged',
								resolved: true
							}
						]
					}
				}
			]
		} as unknown as LessonDocument;

		const [resolved] = deriveLessonRows({
			lessons: [lessons[1]],
			generations,
			generationDocumentsById: { 'gen-attention': attentionPack },
			lessonDocumentsById: { 'lesson-attention': resolvedDocument }
		});
		expect(resolved.state).toBe('ready');
		expect(resolved.flagCount).toBe(0);

		const [dismissed] = deriveLessonRows({
			lessons: [lessons[1]],
			generations,
			generationDocumentsById: { 'gen-attention': attentionPack },
			dismissedIssueIdsByLessonId: { 'lesson-attention': ['visual-issue'] }
		});
		expect(dismissed.state).toBe('ready');
		expect(dismissed.flagCount).toBe(0);
	});

	it('keeps terminal generations without sections in draft', () => {
		const [row] = deriveLessonRows({
			lessons: [{ ...lessons[2], id: 'empty', source_generation_id: 'gen-ready' }],
			generations: generations.map((generation) =>
				generation.id === 'gen-ready'
					? { ...generation, document_section_count: 0 }
					: generation
			),
			generationDocumentsById: {
				'gen-ready': { ...readyPack, sections: [] } as V3PackDocument
			}
		});
		expect(row.state).toBe('draft');
	});
});
