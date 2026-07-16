// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { authStore } = vi.hoisted(() => {
	let current = {
		id: 'user-1',
		email: 'teacher@example.com',
		name: 'Alex',
		picture_url: null,
		has_profile: true,
		created_at: '2026-04-06T00:00:00Z',
		updated_at: '2026-04-06T00:00:00Z'
	};
	const subscribers = new Set<(value: unknown) => void>();

	return {
		authStore: {
			subscribe(callback: (value: unknown) => void) {
				subscribers.add(callback);
				callback(current);
				return () => subscribers.delete(callback);
			},
			set(value: typeof current) {
				current = value;
				for (const callback of subscribers) {
					callback(current);
				}
			}
		}
	};
});

const { goto } = vi.hoisted(() => ({
	goto: vi.fn()
}));

const { getProfile, getV3Generations, fetchV3Document, getPacks } = vi.hoisted(() => ({
	getProfile: vi.fn(),
	getV3Generations: vi.fn(),
	fetchV3Document: vi.fn(),
	getPacks: vi.fn()
}));

const { v3PackToBuilderDocument, createBuilderLesson, listBuilderLessons, saveDocument } = vi.hoisted(() => ({
	v3PackToBuilderDocument: vi.fn(),
	createBuilderLesson: vi.fn(),
	listBuilderLessons: vi.fn(),
	saveDocument: vi.fn()
}));

vi.mock('lectio', () => ({
	basePresetMap: {},
	templateRegistryMap: {}
}));

vi.mock('$app/navigation', () => ({
	goto
}));

vi.mock('$lib/api/profile', () => ({
	getProfile
}));

vi.mock('$lib/api/v3', () => ({
	getV3Generations,
	fetchV3Document
}));

vi.mock('$lib/api/learning-pack', () => ({
	getPacks
}));

vi.mock('$lib/api/errors', () => ({
	isApiError: () => false
}));

vi.mock('$lib/auth/routing', () => ({
	getOnboardingRoute: () => '/onboarding',
	resolveDashboardProfileFailure: () => ({ redirectTo: null, message: null })
}));

vi.mock('$lib/stores/auth', () => ({
	authUser: authStore,
	logout: vi.fn()
}));

vi.mock('$lib/generation/error-messages', () => ({
	friendlyGenerationErrorMessage: () => 'Generation failed.'
}));

vi.mock('$lib/builder/adapters/from-generation', () => ({
	v3PackToBuilderDocument
}));

vi.mock('$lib/builder/api/lesson-crud', () => ({
	createBuilderLesson,
	listBuilderLessons
}));

vi.mock('$lib/builder/persistence/idb-store', () => ({
	saveDocument
}));

import DashboardPage from './+page.svelte';

describe('dashboard teacher profile summary', () => {
	beforeEach(() => {
		localStorage.clear();
		getProfile.mockResolvedValue({
			id: 'profile-1',
			user_id: 'user-1',
			teacher_role: 'teacher',
			subjects: ['mathematics', 'physics'],
			default_grade_band: 'high_school',
			default_audience_description: 'Year 10 mixed-ability maths',
			curriculum_framework: 'GCSE AQA',
			classroom_context: 'Limited devices, mixed prior knowledge.',
			planning_goals: 'Better first drafts and more scaffolded practice.',
			school_or_org_name: 'Riverside High',
			delivery_preferences: {
				tone: 'supportive',
				reading_level: 'simple',
				explanation_style: 'concrete-first',
				example_style: 'everyday',
				brevity: 'tight',
				use_visuals: true,
				print_first: true,
				more_practice: true,
				keep_short: false
			},
			created_at: '2026-04-06T00:00:00Z',
			updated_at: '2026-04-06T00:00:00Z'
		});
		getV3Generations.mockResolvedValue([]);
		fetchV3Document.mockResolvedValue({});
		getPacks.mockResolvedValue([]);
		listBuilderLessons.mockResolvedValue([]);
		v3PackToBuilderDocument.mockReturnValue({
			version: 1,
			id: 'lesson-doc-1',
			title: 'Converted lesson',
			subject: 'Mathematics',
			preset_id: 'blue-classroom',
			source: 'generated',
			sections: [],
			blocks: {},
			media: {},
			created_at: '2026-05-14T00:00:00Z',
			updated_at: '2026-05-14T00:00:00Z'
		});
		createBuilderLesson.mockResolvedValue({
			id: 'builder-1',
			source_generation_id: 'gen-v3-1',
			source_type: 'v3_generation',
			title: 'Quadratic review',
			created_at: '2026-05-14T00:00:00Z',
			updated_at: '2026-05-14T00:00:00Z',
			document: {
				version: 1,
				id: 'lesson-doc-1',
				title: 'Converted lesson',
				subject: 'Mathematics',
				preset_id: 'blue-classroom',
				source: 'generated',
				sections: [],
				blocks: {},
				media: {},
				created_at: '2026-05-14T00:00:00Z',
				updated_at: '2026-05-14T00:00:00Z'
			}
		});
		saveDocument.mockResolvedValue(undefined);
	});

	afterEach(() => {
		cleanup();
		vi.clearAllMocks();
	});

	it('shows teacher-facing summary fields instead of learner labels', async () => {
		render(DashboardPage);

		await waitFor(() => expect(screen.getByText(/teacher setup/i)).toBeTruthy());

		expect(screen.getByText(/teacher role/i)).toBeTruthy();
		expect(screen.getByText(/default grade band/i)).toBeTruthy();
		expect(screen.getByText(/default audience/i)).toBeTruthy();
		expect(screen.getByText(/curriculum/i)).toBeTruthy();
		expect(screen.getByText(/classroom context/i)).toBeTruthy();
		expect(screen.getByText(/planning goals/i)).toBeTruthy();
		expect(screen.queryByText(/learning style/i)).toBeNull();
		expect(screen.queryByText(/learner description/i)).toBeNull();
	});

	it('persists the stream-into-builder toggle', async () => {
		render(DashboardPage);
		const toggle = await screen.findByRole('checkbox', {
			name: 'Stream new lessons into Builder (experimental)'
		});
		await fireEvent.click(toggle);
		expect(localStorage.getItem('lectio:stream-into-builder')).toBe('true');
	});

	it('loads V3 generation history and links open to the completed V3 viewer route', async () => {
		getV3Generations.mockResolvedValueOnce([
			{
				id: 'gen-v3-1',
				subject: 'Mathematics',
				title: 'Quadratic review',
				status: 'completed',
				booklet_status: 'final_ready',
				section_count: 5,
				document_section_count: 5,
				template_id: 'guided-concept-path',
				created_at: '2026-05-01T00:00:00Z',
				completed_at: '2026-05-01T00:05:00Z'
			}
		]);

		render(DashboardPage);

		await waitFor(() => expect(getV3Generations).toHaveBeenCalledTimes(1));
		expect(getV3Generations).toHaveBeenCalledWith();

		const openLink = await screen.findByRole('link', { name: 'Open' });
		expect(openLink.getAttribute('href')).toBe('/studio/generations/gen-v3-1');
		expect(screen.getByRole('button', { name: 'Edit in Builder' })).toBeTruthy();
	});

	it('opens completed V3 generations in the builder from dashboard history', async () => {
		getV3Generations.mockResolvedValueOnce([
			{
				id: 'gen-v3-1',
				subject: 'Mathematics',
				title: 'Quadratic review',
				status: 'completed',
				booklet_status: 'final_ready',
				section_count: 5,
				document_section_count: 5,
				template_id: 'guided-concept-path',
				created_at: '2026-05-01T00:00:00Z',
				completed_at: '2026-05-01T00:05:00Z'
			}
		]);
		fetchV3Document.mockResolvedValueOnce({
			kind: 'v3_booklet_pack',
			title: 'Quadratic review',
			sections: []
		});

		render(DashboardPage);

		await waitFor(() => expect(getV3Generations).toHaveBeenCalledTimes(1));
		await fireEvent.click(await screen.findByRole('button', { name: 'Edit in Builder' }));

		expect(fetchV3Document).toHaveBeenCalledWith('gen-v3-1');
		expect(v3PackToBuilderDocument).toHaveBeenCalledWith(
			expect.objectContaining({ kind: 'v3_booklet_pack' }),
			{ routeGenerationId: 'gen-v3-1' }
		);
		expect(createBuilderLesson).toHaveBeenCalledWith(
			expect.objectContaining({
				source_type: 'v3_generation',
				source_generation_id: 'gen-v3-1',
				title: 'Quadratic review'
			})
		);
		expect(saveDocument).toHaveBeenCalledWith(expect.objectContaining({ id: 'lesson-doc-1' }));
		await waitFor(() => expect(goto).toHaveBeenCalledWith('/builder/builder-1'));
	});

	it("doesn't show builder edit action for non-completed V3 generations", async () => {
		getV3Generations.mockResolvedValueOnce([
			{
				id: 'gen-v3-1',
				subject: 'Mathematics',
				title: 'Quadratic review',
				status: 'running',
				booklet_status: 'drafting',
				section_count: 5,
				document_section_count: 2,
				template_id: 'guided-concept-path',
				created_at: '2026-05-01T00:00:00Z',
				completed_at: null
			}
		]);

		render(DashboardPage);

		await waitFor(() => expect(getV3Generations).toHaveBeenCalledTimes(1));
		expect(screen.queryByRole('button', { name: 'Edit in Builder' })).toBeNull();
	});

	it('renders the unified flag-on lesson list with streaming and draft routes', async () => {
		localStorage.setItem('lectio:stream-into-builder', 'true');
		getV3Generations.mockResolvedValueOnce([
			{ id: 'gen-stream', subject: 'Math', title: 'Streaming lesson', status: 'running', booklet_status: 'drafting', section_count: 3, document_section_count: 1, template_id: 'guided-concept-path', created_at: '', completed_at: null },
			{ id: 'gen-old', subject: 'Science', title: 'Old generation', status: 'completed', booklet_status: 'final_ready', section_count: 2, document_section_count: 2, template_id: 'guided-concept-path', created_at: '', completed_at: '' }
		]);
		listBuilderLessons.mockResolvedValueOnce([
			{ id: 'builder-stream', source_generation_id: 'gen-stream', source_type: 'v3_generation', title: 'Streaming lesson', created_at: '', updated_at: '' },
			{ id: 'builder-draft', source_generation_id: null, source_type: 'manual', title: 'Manual draft', created_at: '', updated_at: '' }
		]);

		render(DashboardPage);

		expect(await screen.findByRole('heading', { name: 'Lessons' })).toBeTruthy();
		expect(screen.getByText('● streaming')).toBeTruthy();
		expect(screen.getByText('✎ draft')).toBeTruthy();
		const openLinks = screen.getAllByRole('link', { name: 'Open' });
		expect(openLinks.map((link) => link.getAttribute('href'))).toContain('/builder/builder-stream?generation_id=gen-stream');
		expect(openLinks.map((link) => link.getAttribute('href'))).toContain('/builder/builder-draft');
		expect(screen.getByText('Pre-Builder generation')).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Edit in Builder' })).toBeTruthy();
	});
});
