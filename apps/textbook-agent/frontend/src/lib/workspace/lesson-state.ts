import type { LessonDocument } from 'lectio';

import { partitionGenerationIssues } from '$lib/builder/generation-issues';
import type { BuilderIssue, IssueSection } from '$lib/builder/issues';
import { isTerminalGenerationDocument } from '$lib/builder/streaming/generation-stream';
import type { BuilderLessonSummary } from '$lib/builder/api/lesson-crud';
import type { V3GenerationHistoryItem } from '$lib/types/v3';
import type { V3PackDocument } from '$lib/studio/v3-pack-to-lectio-document';

export type LessonState = 'writing' | 'attention' | 'ready' | 'draft';

export interface LessonRow {
	id: string;
	title: string;
	classLabel: string | null;
	subject: string | null;
	state: LessonState;
	sectionsDone: number | null;
	sectionsTotal: number | null;
	flagCount: number;
	awaitingReview: boolean;
	updatedAt: string;
	href: string;
}

export interface DeriveLessonRowsInput {
	lessons: BuilderLessonSummary[];
	generations: V3GenerationHistoryItem[];
	generationDocumentsById?: Record<string, V3PackDocument | undefined>;
	lessonDocumentsById?: Record<string, LessonDocument | undefined>;
	dismissedIssueIdsByLessonId?: Record<string, string[] | undefined>;
}

function allLessonIssues(document: LessonDocument | undefined): BuilderIssue[] {
	if (!document) return [];
	return document.sections.flatMap((section) => (section as IssueSection).meta?.issues ?? []);
}

function sectionIds(pack: V3PackDocument): string[] {
	return (pack.sections ?? [])
		.map((section) => {
			if (!section || typeof section !== 'object') return '';
			const record = section as Record<string, unknown>;
			const value = record.section_id ?? record.id;
			return typeof value === 'string' ? value : '';
		})
		.filter(Boolean);
}

function unresolvedFlagCount(
	pack: V3PackDocument | undefined,
	lessonDocument: LessonDocument | undefined,
	dismissedIssueIds: string[]
): number {
	const dismissed = new Set(dismissedIssueIds);
	const persisted = allLessonIssues(lessonDocument);
	const resolved = new Set(persisted.filter((issue) => issue.resolved).map((issue) => issue.id));

	if (!pack) {
		return persisted.filter((issue) => !issue.resolved && !dismissed.has(issue.id)).length;
	}

	const partitioned = partitionGenerationIssues(pack, sectionIds(pack));
	const generated = [
		...Object.values(partitioned.sectionIssues).flat(),
		...partitioned.documentLevelIssues
	];
	return new Set(
		generated
			.filter((issue) => !resolved.has(issue.id) && !dismissed.has(issue.id))
			.map((issue) => issue.id)
	).size;
}

function progressCounts(
	generation: V3GenerationHistoryItem,
	pack: V3PackDocument | undefined
): { done: number | null; total: number | null } {
	const statuses = pack?.progress?.sections;
	const done = statuses
		? Object.values(statuses).filter((status) => status === 'ready').length
		: generation.document_section_count;
	const total = generation.section_count || (statuses ? Object.keys(statuses).length : 0);
	return {
		done: Number.isFinite(done) ? done : null,
		total: total > 0 ? total : null
	};
}

function isFailedGeneration(generation: V3GenerationHistoryItem): boolean {
	return generation.status === 'failed' || generation.status.startsWith('failed_');
}

function isTerminalGeneration(
	generation: V3GenerationHistoryItem,
	pack: V3PackDocument | undefined
): boolean {
	return (
		isFailedGeneration(generation) ||
		isTerminalGenerationDocument(pack ?? { status: generation.booklet_status })
	);
}

export function deriveLessonRows({
	lessons,
	generations,
	generationDocumentsById = {},
	lessonDocumentsById = {},
	dismissedIssueIdsByLessonId = {}
}: DeriveLessonRowsInput): LessonRow[] {
	const generationsById = new Map(generations.map((generation) => [generation.id, generation]));

	return lessons
		.map((lesson): LessonRow => {
			const generation = lesson.source_generation_id
				? generationsById.get(lesson.source_generation_id)
				: undefined;
			const pack = generation ? generationDocumentsById[generation.id] : undefined;
			const progress = generation ? progressCounts(generation, pack) : { done: null, total: null };
			const flags = unresolvedFlagCount(
				pack,
				lessonDocumentsById[lesson.id],
				dismissedIssueIdsByLessonId[lesson.id] ?? []
			);
			const failed = generation ? isFailedGeneration(generation) : false;
			const awaitingReview = generation?.status === 'awaiting_review';
			const terminal = generation ? isTerminalGeneration(generation, pack) : false;
			const sectionCount = pack?.sections?.length ?? generation?.document_section_count ?? 0;
			const state: LessonState = !generation
				? 'draft'
				: awaitingReview
					? 'attention'
				: !terminal
					? 'writing'
					: failed || flags > 0
						? 'attention'
						: sectionCount > 0
							? 'ready'
							: 'draft';

			return {
				id: lesson.id,
				title: lesson.title || 'Untitled lesson',
				classLabel: lesson.class_label,
				subject: generation?.subject ?? lessonDocumentsById[lesson.id]?.subject ?? null,
				state,
				sectionsDone: generation ? progress.done : null,
				sectionsTotal: generation ? progress.total : null,
				flagCount: flags,
				awaitingReview,
				updatedAt: lesson.updated_at,
				href:
					(state === 'writing' || awaitingReview) && generation
						? `/builder/${lesson.id}?generation_id=${generation.id}`
						: `/builder/${lesson.id}`
			};
		})
		.sort((left, right) => Date.parse(right.updatedAt) - Date.parse(left.updatedAt));
}
