// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
	goto: vi.fn(),
	getStreamIntoBuilder: vi.fn(),
	listBuilderLessons: vi.fn(),
	getBuilderLesson: vi.fn(),
	getV3Generations: vi.fn(),
	fetchV3Document: vi.fn(),
	getChunkedPlanStatus: vi.fn(),
	logout: vi.fn()
}));

vi.mock('$app/navigation', () => ({ goto: mocks.goto }));
vi.mock('$lib/settings/flags', () => ({ getStreamIntoBuilder: mocks.getStreamIntoBuilder }));
vi.mock('$lib/builder/api/lesson-crud', () => ({
	listBuilderLessons: mocks.listBuilderLessons,
	getBuilderLesson: mocks.getBuilderLesson
}));
vi.mock('$lib/api/v3', () => ({
	getV3Generations: mocks.getV3Generations,
	fetchV3Document: mocks.fetchV3Document,
	getChunkedPlanStatus: mocks.getChunkedPlanStatus
}));
vi.mock('$lib/stores/auth', () => ({
	authUser: {
		subscribe(run: (value: null) => void) {
			run(null);
			return () => undefined;
		}
	},
	logout: mocks.logout
}));

import LessonsPage from './+page.svelte';

const lessons = [
	{
		id: 'writing',
		source_generation_id: 'gen-writing',
		source_type: 'v3_generation',
		title: 'Photosynthesis',
		class_label: 'Year 7 Science',
		created_at: '2026-07-27T08:00:00Z',
		updated_at: '2026-07-27T10:00:00Z'
	},
	{
		id: 'attention',
		source_generation_id: 'gen-attention',
		source_type: 'v3_generation',
		title: 'Stomata',
		class_label: 'Year 8 Science',
		created_at: '2026-07-27T07:00:00Z',
		updated_at: '2026-07-27T09:00:00Z'
	},
	{
		id: 'ready',
		source_generation_id: 'gen-ready',
		source_type: 'v3_generation',
		title: 'Irregular shapes',
		class_label: null,
		created_at: '2026-07-26T07:00:00Z',
		updated_at: '2026-07-26T09:00:00Z'
	},
	{
		id: 'draft',
		source_generation_id: null,
		source_type: 'manual',
		title: 'Untitled lesson',
		class_label: null,
		created_at: '2026-07-25T07:00:00Z',
		updated_at: '2026-07-25T09:00:00Z'
	}
];

const generations = [
	{
		id: 'gen-writing',
		subject: 'Science',
		title: 'Photosynthesis',
		status: 'running',
		booklet_status: 'streaming_preview',
		section_count: 4,
		document_section_count: 2,
		template_id: 'guided-concept-path',
		created_at: '',
		completed_at: null
	},
	{
		id: 'gen-attention',
		subject: 'Science',
		title: 'Stomata',
		status: 'completed',
		booklet_status: 'final_with_warnings',
		section_count: 2,
		document_section_count: 2,
		template_id: 'guided-concept-path',
		created_at: '',
		completed_at: ''
	},
	{
		id: 'gen-ready',
		subject: 'Mathematics',
		title: 'Irregular shapes',
		status: 'completed',
		booklet_status: 'final_ready',
		section_count: 3,
		document_section_count: 3,
		template_id: 'guided-concept-path',
		created_at: '',
		completed_at: ''
	}
];

function packFor(id: string) {
	if (id === 'gen-writing') {
		return {
			status: 'streaming_preview',
			progress: { stage: 'running', sections: { intro: 'ready', explain: 'ready' } },
			sections: [{ section_id: 'intro' }, { section_id: 'explain' }]
		};
	}
	if (id === 'gen-attention') {
		return {
			status: 'final_with_warnings',
			progress: { stage: 'completed', sections: { intro: 'ready', practice: 'ready' } },
			sections: [{ section_id: 'intro' }, { section_id: 'practice' }],
			section_diagnostics: [],
			booklet_issues: [
				{
					issue_id: 'image-review',
					section_id: 'practice',
					category: 'visual_quality_flagged',
					message: 'Review image'
				}
			]
		};
	}
	return {
		status: 'final_ready',
		progress: { stage: 'completed', sections: { one: 'ready', two: 'ready', three: 'ready' } },
		sections: [{ section_id: 'one' }, { section_id: 'two' }, { section_id: 'three' }],
		section_diagnostics: [],
		booklet_issues: []
	};
}

describe('/lessons', () => {
	beforeEach(() => {
		Object.values(mocks).forEach((mock) => mock.mockReset());
		mocks.goto.mockReset();
		mocks.getStreamIntoBuilder.mockReturnValue(true);
		mocks.listBuilderLessons.mockResolvedValue(lessons);
		mocks.getV3Generations.mockResolvedValue(generations);
		mocks.getBuilderLesson.mockImplementation(async (id: string) => ({
			...lessons.find((lesson) => lesson.id === id),
			document: { version: 1, id, title: id, subject: 'Science', sections: [], blocks: {}, media: {} }
		}));
		mocks.fetchV3Document.mockImplementation(async (id: string) => packFor(id));
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-writing',
			stage: 'stage2_running',
			doc_version: null,
			failed_sections: [],
			blueprint_id: null,
			execution_started: true,
			next_action: 'generation_running'
		});
	});

	afterEach(cleanup);

	it('redirects to the unchanged dashboard when the flag is off', async () => {
		mocks.getStreamIntoBuilder.mockReturnValue(false);
		render(LessonsPage);
		await waitFor(() =>
			expect(mocks.goto).toHaveBeenCalledWith('/dashboard', { replaceState: true })
		);
		expect(mocks.listBuilderLessons).not.toHaveBeenCalled();
	});

	it('renders all four groups, class labels, and row actions', async () => {
		render(LessonsPage);
		expect(await screen.findByText('Writing now')).toBeTruthy();
		expect(screen.getByText('Needs you')).toBeTruthy();
		expect(screen.getByText('Ready to print')).toBeTruthy();
		expect(screen.getByText('Drafts')).toBeTruthy();
		expect(screen.getByText('· Year 7 Science')).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Review' }).getAttribute('href')).toBe(
			'/builder/attention'
		);
		expect(screen.getByRole('link', { name: 'Print' }).getAttribute('href')).toBe(
			'/builder/print/ready'
		);
		expect(screen.getByRole('link', { name: 'Continue' }).getAttribute('href')).toBe(
			'/builder/draft'
		);
		expect(screen.getByRole('link', { name: 'Photosynthesis · Year 7 Science' }).getAttribute('href')).toBe(
			'/builder/writing?generation_id=gen-writing'
		);
	});

	it('renders one empty state without empty group headings', async () => {
		mocks.listBuilderLessons.mockResolvedValue([]);
		mocks.getV3Generations.mockResolvedValue([]);
		render(LessonsPage);
		expect(await screen.findByText(/No lessons yet/)).toBeTruthy();
		expect(screen.queryByText('Writing now')).toBeNull();
		expect(screen.getAllByRole('link', { name: '+ New lesson' })).toHaveLength(1);
	});

	it('moves a writing row to ready when the shared poller observes a terminal snapshot', async () => {
		let resolveStatus!: (value: Record<string, unknown>) => void;
		mocks.getChunkedPlanStatus.mockReturnValue(
			new Promise((resolve) => {
				resolveStatus = resolve;
			})
		);
		let writingFetches = 0;
		mocks.fetchV3Document.mockImplementation(async (id: string) => {
			if (id !== 'gen-writing') return packFor(id);
			writingFetches += 1;
			return writingFetches === 1
				? packFor(id)
				: {
						status: 'final_ready',
						progress: {
							stage: 'completed',
							sections: { intro: 'ready', explain: 'ready', practice: 'ready', close: 'ready' }
						},
						sections: [
							{ section_id: 'intro' },
							{ section_id: 'explain' },
							{ section_id: 'practice' },
							{ section_id: 'close' }
						],
						section_diagnostics: [],
						booklet_issues: []
					};
		});

		render(LessonsPage);
		expect(await screen.findByText('Writing now')).toBeTruthy();
		resolveStatus({
			generation_id: 'gen-writing',
			stage: 'complete',
			doc_version: 'doc-v2',
			failed_sections: [],
			blueprint_id: 'blueprint-1',
			execution_started: true,
			next_action: 'done'
		});

		await waitFor(() => expect(screen.queryByText('Writing now')).toBeNull());
		expect(screen.getByRole('link', { name: 'Photosynthesis · Year 7 Science' }).getAttribute('href')).toBe(
			'/builder/writing'
		);
		expect(mocks.getChunkedPlanStatus).toHaveBeenCalledTimes(1);
		expect(writingFetches).toBe(2);
	});
});
