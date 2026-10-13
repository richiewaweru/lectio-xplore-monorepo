// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

const params = vi.hoisted(() => ({ learnerId: 'L1', unitId: 'U1' }));
vi.mock('$app/state', () => ({ page: { params } }));
vi.mock('$app/environment', () => ({ browser: true }));
const learnerFetch = vi.hoisted(() => vi.fn());
vi.mock('$lib/learn/student/api/learner-fetch', () => ({ learnerFetch }));

import Home from './+page.svelte';
import Roadmap from './topics/[unitId]/+page.svelte';

function lesson(over: Record<string, unknown>) {
	return {
		path_lesson_id: 'p',
		position: 1,
		title: 'Lesson',
		state: 'ready',
		instance_id: 'i',
		release_id: 'rel-secret',
		best_after_position: null,
		sections_done: 0,
		sections_total: 4,
		...over
	};
}

const body = {
	learner_id: 'L1',
	display_name: 'Richard',
	code: 'MANGO-7K4Q',
	topics: [
		{
			unit_id: 'U1',
			title: 'Photosynthesis',
			summary: 'Understand how plants make their own food',
			lessons_total: 5,
			lessons_done: 2,
			next_lesson_id: 'p3',
			lessons: [
				lesson({ path_lesson_id: 'p1', position: 1, title: 'Where food comes from', state: 'done', instance_id: 'i1' }),
				lesson({ path_lesson_id: 'p2', position: 2, title: 'Soil versus plant', state: 'done', instance_id: 'i2' }),
				lesson({ path_lesson_id: 'p3', position: 3, title: 'Raw materials and products', state: 'current', instance_id: 'i3' }),
				lesson({ path_lesson_id: 'p4', position: 4, title: 'Writing the word equation', state: 'ready', instance_id: 'i4', best_after_position: 3 }),
				lesson({ path_lesson_id: 'p5', position: 5, title: 'Using the equation', state: 'pending', instance_id: null, release_id: null, best_after_position: 4 })
			]
		},
		{
			unit_id: 'U2',
			title: 'Mixtures',
			summary: null,
			lessons_total: 3,
			lessons_done: 0,
			next_lesson_id: 'm1',
			lessons: [lesson({ path_lesson_id: 'm1', title: 'What is a mixture', instance_id: 'mi1' })]
		}
	],
	other_lessons: [] as Array<Record<string, string>>
};

function respond(payload: unknown, ok = true) {
	learnerFetch.mockResolvedValue({
		ok,
		status: ok ? 200 : 500,
		json: async () => payload,
		text: async () => JSON.stringify(payload),
		headers: new Headers({ 'content-type': 'application/json' })
	});
}

afterEach(() => {
	cleanup();
	learnerFetch.mockReset();
});

describe('student home topics', () => {
	it('shows loading then topic cards without duplicates or internal ids', async () => {
		respond(body);
		const { container } = render(Home);
		expect(screen.getByText(/Loading/)).toBeTruthy();
		await waitFor(() => expect(screen.getByText('Hi Richard')).toBeTruthy());
		expect(learnerFetch).toHaveBeenCalledWith('/api/v1/learn/learners/L1/topics');
		expect(screen.getByText('MANGO-7K4Q')).toBeTruthy();
		expect(screen.getAllByText('Photosynthesis')).toHaveLength(1);
		expect(screen.getAllByText('Mixtures')).toHaveLength(1);
		expect(screen.getByText('2 of 5 lessons')).toBeTruthy();
		expect(screen.getByText('0 of 3 lessons')).toBeTruthy();
		expect(screen.getByText('Continue: Raw materials and products →')).toBeTruthy();
		expect(screen.getByText('Start →')).toBeTruthy();
		expect(screen.queryByText('Other lessons')).toBeNull();
		expect(container.textContent).not.toMatch(/rel-secret|score|status/i);
		const mail = screen.getByText(/Get in touch/).closest('a');
		expect(mail?.getAttribute('href')).toMatch(/^mailto:rmainawaweru@gmail\.com/);
	});

	it('hides the code when null and shows Other lessons only when non-empty', async () => {
		respond({
			...body,
			code: null,
			other_lessons: [{ instance_id: 'o1', title: 'Manual lesson', state: 'ready' }]
		});
		render(Home);
		await waitFor(() => expect(screen.getByText('Hi Richard')).toBeTruthy());
		expect(screen.queryByText(/Your code/)).toBeNull();
		expect(screen.getByText('Other lessons')).toBeTruthy();
		expect(screen.getByText('Manual lesson').closest('a')?.getAttribute('href')).toBe(
			'/learn/instances/o1'
		);
	});

	it('shows View when every lesson is done', async () => {
		const done = { ...body.topics[0], lessons_done: 5, next_lesson_id: null };
		respond({ ...body, topics: [done] });
		render(Home);
		await waitFor(() => expect(screen.getByText('View →')).toBeTruthy());
	});
});

describe('topic roadmap', () => {
	it('renders states, best-after, and only links openable lessons', async () => {
		respond(body);
		render(Roadmap);
		await waitFor(() => expect(screen.getByText('Soil versus plant')).toBeTruthy());
		expect(screen.getAllByText('Done')).toHaveLength(2);
		expect(screen.getByText('you are here')).toBeTruthy();
		expect(screen.getByText('Best after Lesson 3')).toBeTruthy();
		expect(screen.getByText('Raw materials and products').closest('a')?.getAttribute('href')).toBe(
			'/learn/instances/i3'
		);
		expect(screen.getByText('Writing the word equation').closest('a')?.getAttribute('href')).toBe(
			'/learn/instances/i4'
		);
		expect(screen.getByText('Using the equation').closest('a')).toBeNull();
		expect(screen.getByText('Being prepared')).toBeTruthy();
		expect(screen.getAllByText('Soil versus plant')).toHaveLength(1);
	});

	it('does not link a ready lesson whose instance_id is null', async () => {
		const t = {
			...body.topics[0],
			lessons: [lesson({ path_lesson_id: 'x', title: 'Orphan', state: 'ready', instance_id: null })]
		};
		respond({ ...body, topics: [t] });
		render(Roadmap);
		await waitFor(() => expect(screen.getByText('Orphan')).toBeTruthy());
		expect(screen.getByText('Orphan').closest('a')).toBeNull();
		expect(screen.getByText('Being prepared')).toBeTruthy();
	});

	it('shows a quiet message for an unknown topic', async () => {
		params.unitId = 'NOPE';
		respond(body);
		render(Roadmap);
		await waitFor(() => expect(screen.getByText('This topic was not found.')).toBeTruthy());
		params.unitId = 'U1';
	});
});
