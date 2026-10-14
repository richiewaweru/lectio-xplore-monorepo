import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import InteractionShell from './InteractionShell.svelte';
import { attemptState, revealFor } from './attempt-rules';
import { evaluateLocalAttempt } from './local-eval';
import type { InteractionNode } from '$lib/learn/document/types';
import type { ServerEvaluation } from './types';

const fb = { correct: 'Right.', incorrect: 'Not quite.' };

function node(
	type: InteractionNode['interaction_type'],
	config: Record<string, unknown>,
	extra: Partial<InteractionNode> = {}
): InteractionNode {
	return {
		id: `n-${type}`,
		kind: 'interaction',
		interaction_type: type,
		prompt: 'Q?',
		role: 'practice',
		config,
		feedback: fb,
		...extra
	} as InteractionNode;
}

const check = () => screen.getByTestId('interaction-check') as HTMLButtonElement;
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const status = () => screen.getByRole('status');

const matchConfig = {
	pairs: [
		{ left: 'Roots', right: 'Water' },
		{ left: 'Leaves', right: 'Food' },
		{ left: 'Stem', right: 'Support' }
	]
};

describe('choice', () => {
	const choice = node('choice', {
		options: [
			{ id: 'a', text: 'Alpha' },
			{ id: 'b', text: 'Beta' }
		],
		correct_option_id: 'b'
	});

	it('needs a selection, clears, and marks the pick after a check', async () => {
		render(InteractionShell, { node: choice });
		expect(check().disabled).toBe(true);
		await click('Alpha');
		expect(check().disabled).toBe(false);
		await fireEvent.click(screen.getByTestId('interaction-clear'));
		expect(check().disabled).toBe(true);
		await click('Alpha');
		await fireEvent.click(check());
		expect(status().getAttribute('data-outcome')).toBe('incorrect');
		expect(screen.getByRole('button', { name: 'Alpha' }).getAttribute('data-mark')).toBe('wrong');
	});

	it('try again clears a wrong choice and unlocks the buttons', async () => {
		render(InteractionShell, { node: choice });
		await click('Alpha');
		await fireEvent.click(check());
		expect((screen.getByRole('button', { name: 'Alpha' }) as HTMLButtonElement).disabled).toBe(true);
		await fireEvent.click(screen.getByTestId('interaction-try-again'));
		expect(screen.getByRole('button', { name: 'Alpha' }).getAttribute('aria-pressed')).toBe('false');
		await click('Beta');
		await fireEvent.click(check());
		expect(status().getAttribute('data-outcome')).toBe('correct');
		expect(screen.queryByTestId('interaction-try-again')).toBeNull();
	});
});

describe('multi-select', () => {
	const multi = node('multi-select', {
		options: [
			{ id: 'a', text: 'Alpha' },
			{ id: 'b', text: 'Beta' },
			{ id: 'c', text: 'Gamma' }
		],
		correct_option_ids: ['a', 'b']
	});

	it('retry keeps the right picks and drops the wrong one', async () => {
		render(InteractionShell, { node: multi });
		const box = (name: string) => screen.getByRole('checkbox', { name });
		await fireEvent.click(box('Alpha'));
		await fireEvent.click(box('Beta'));
		await fireEvent.click(box('Gamma'));
		await fireEvent.click(check());
		expect(status().getAttribute('data-outcome')).toBe('partial');
		await fireEvent.click(screen.getByTestId('interaction-try-again'));
		expect(box('Alpha').getAttribute('aria-checked')).toBe('true');
		expect(box('Gamma').getAttribute('aria-checked')).toBe('false');
	});
});

describe('numeric and short-response', () => {
	it('numeric enables Check once non-empty and clears', async () => {
		render(InteractionShell, { node: node('numeric', { value: 4, tolerance: 0 }) });
		expect(check().disabled).toBe(true);
		const input = screen.getByLabelText('Answer') as HTMLInputElement;
		await fireEvent.input(input, { target: { value: '5' } });
		expect(check().disabled).toBe(false);
		await fireEvent.click(check());
		expect(status().getAttribute('data-outcome')).toBe('incorrect');
		await fireEvent.click(screen.getByTestId('interaction-try-again'));
		expect((screen.getByLabelText('Answer') as HTMLInputElement).value).toBe('');
		expect(check().disabled).toBe(true);
	});

	it('teacher-review short response is pending-review and locks', async () => {
		render(InteractionShell, {
			node: node('short-response', { evaluation: 'teacher-review' })
		});
		await fireEvent.input(screen.getByLabelText('Answer'), { target: { value: 'anything' } });
		await fireEvent.click(check());
		expect(status().getAttribute('data-outcome')).toBe('pending-review');
		expect(screen.queryByTestId('interaction-try-again')).toBeNull();
		expect(screen.queryByTestId('interaction-show-answer')).toBeNull();
	});
});

describe('fill-blank', () => {
	const fill = node('fill-blank', { answers: ['cat', ['dog', 'hound']] });

	it('shows progress, needs every blank, and retry keeps right blanks', async () => {
		render(InteractionShell, { node: fill });
		const [one, two] = screen.getAllByRole('textbox') as HTMLInputElement[];
		expect(screen.getByTestId('interaction-progress').textContent).toBe('0 of 2 filled');
		await fireEvent.input(one, { target: { value: 'cat' } });
		expect(check().disabled).toBe(true);
		expect(screen.getByTestId('interaction-progress').textContent).toBe('1 of 2 filled');
		await fireEvent.input(two, { target: { value: 'bird' } });
		expect(check().disabled).toBe(false);
		await fireEvent.click(check());
		expect(status().getAttribute('data-outcome')).toBe('partial');
		expect(one.getAttribute('data-mark')).toBe('right');
		expect(two.getAttribute('data-mark')).toBe('wrong');
		await fireEvent.click(screen.getByTestId('interaction-try-again'));
		expect(one.value).toBe('cat');
		expect(two.value).toBe('');
		expect(check().disabled).toBe(true);
	});

	it('accepts alternatives like the server', async () => {
		render(InteractionShell, { node: fill });
		const [one, two] = screen.getAllByRole('textbox') as HTMLInputElement[];
		await fireEvent.input(one, { target: { value: 'Cat' } });
		await fireEvent.input(two, { target: { value: 'hound' } });
		await fireEvent.click(check());
		expect(status().getAttribute('data-outcome')).toBe('correct');
	});
});

describe('match-pairs', () => {
	const match = node('match-pairs', matchConfig);

	it('select, undo, remove a placement, and clear', async () => {
		render(InteractionShell, { node: match });
		const roots = screen.getByRole('button', { name: 'Roots' });
		await fireEvent.click(roots);
		expect(roots.getAttribute('aria-pressed')).toBe('true');
		// tap again to unselect
		await fireEvent.click(roots);
		expect(roots.getAttribute('aria-pressed')).toBe('false');
		expect((screen.getByRole('button', { name: 'Water' }) as HTMLButtonElement).disabled).toBe(true);

		await fireEvent.click(roots);
		await click('Water');
		expect(screen.getByTestId('interaction-progress').textContent).toBe('1 of 3 placed');
		// tap a placed left item to return it
		await fireEvent.click(roots);
		expect(screen.getByTestId('interaction-progress').textContent).toBe('0 of 3 placed');

		await fireEvent.click(roots);
		await click('Water');
		// tap a placed right item to return it as well
		await click('Water');
		expect(roots.getAttribute('aria-pressed')).toBe('false');

		await fireEvent.click(roots);
		await click('Water');
		await fireEvent.click(screen.getByTestId('interaction-clear'));
		expect(roots.getAttribute('aria-pressed')).toBe('false');
	});

	it('Check waits for all pairs; retry keeps the right ones', async () => {
		render(InteractionShell, { node: match });
		for (const [l, r] of [
			['Roots', 'Water'],
			['Leaves', 'Support']
		]) {
			await click(l!);
			await click(r!);
		}
		expect(check().disabled).toBe(true);
		await click('Stem');
		await click('Food');
		expect(check().disabled).toBe(false);
		await fireEvent.click(check());
		expect(status().getAttribute('data-outcome')).toBe('partial');
		expect(screen.getByRole('button', { name: 'Roots' }).getAttribute('data-mark')).toBe('right');
		expect(screen.getByRole('button', { name: 'Leaves' }).getAttribute('data-mark')).toBe('wrong');
		await fireEvent.click(screen.getByTestId('interaction-try-again'));
		expect(screen.getByRole('button', { name: 'Roots' }).getAttribute('aria-pressed')).toBe('true');
		expect(screen.getByRole('button', { name: 'Leaves' }).getAttribute('aria-pressed')).toBe('false');
		expect(screen.getByTestId('interaction-progress').textContent).toBe('1 of 3 placed');
	});
});

describe('classify', () => {
	const classify = node('classify', {
		items: ['Sunflower', 'Hamster', 'Fern'],
		categories: ['Plant', 'Animal'],
		pairs: [
			{ left: 'Sunflower', right: 'Plant' },
			{ left: 'Hamster', right: 'Animal' },
			{ left: 'Fern', right: 'Plant' }
		]
	});

	it('returns a placed item on tap and keeps right ones on retry', async () => {
		render(InteractionShell, { node: classify });
		await click('Sunflower');
		await click('Plant');
		await click('Hamster');
		await click('Plant');
		await click('Fern');
		await click('Plant');
		// remove a placed item to return it, then place it correctly
		await click('Remove Hamster from Plant');
		expect(check().disabled).toBe(true);
		await click('Hamster');
		await click('Plant');
		await fireEvent.click(check());
		expect(status().getAttribute('data-outcome')).toBe('partial');
		await fireEvent.click(screen.getByTestId('interaction-try-again'));
		const placed = (label: string) => screen.getByText(label).closest('.chip') as HTMLElement;
		expect(placed('Sunflower').className).toContain('matched');
		expect(placed('Fern').className).toContain('matched');
		// Hamster went back to the pool as a tappable item
		expect(screen.getByRole('button', { name: 'Hamster' }).className).not.toContain('matched');
	});
});

describe('sequence', () => {
	const seq = node('sequence', { items: ['Seed', 'Sprout', 'Plant'], order: ['Seed', 'Sprout', 'Plant'] });

	it('does not start solved, marks positions, and retry keeps the order', async () => {
		render(InteractionShell, { node: seq });
		const listed = () => screen.getAllByRole('listitem').map((li) => li.textContent?.replace(/[↑↓\s]/g, ''));
		expect(listed()).not.toEqual(['Seed', 'Sprout', 'Plant']);
		expect(check().disabled).toBe(false);
		await fireEvent.click(check());
		expect(status().getAttribute('data-outcome')).not.toBe('correct');
		await fireEvent.click(screen.getByTestId('interaction-try-again'));
		await click('Move Seed up');
		await click('Move Seed up');
		await fireEvent.click(check());
		expect(status().getAttribute('data-outcome')).toBe('correct');
	});
});

describe('predict', () => {
	it('locks after one submit with no retry or reveal', async () => {
		render(InteractionShell, {
			node: node(
				'choice',
				{ options: [{ id: 'a', text: 'Alpha' }], correct_option_id: 'a' },
				{ role: 'predict' }
			)
		});
		await click('Alpha');
		await fireEvent.click(check());
		expect(screen.queryByTestId('interaction-check')).toBeNull();
		expect(screen.queryByTestId('interaction-try-again')).toBeNull();
		expect(screen.queryByTestId('interaction-show-answer')).toBeNull();
		expect((screen.getByRole('button', { name: 'Alpha' }) as HTMLButtonElement).disabled).toBe(true);
	});
});

describe('preview retry rules', () => {
	const choiceCfg = {
		options: [
			{ id: 'a', text: 'Alpha' },
			{ id: 'b', text: 'Beta' }
		],
		correct_option_id: 'b'
	};

	it('check role: second wrong try locks and reveals', async () => {
		render(InteractionShell, { node: node('choice', choiceCfg, { role: 'check' }) });
		await click('Alpha');
		await fireEvent.click(check());
		expect(screen.getByTestId('interaction-tries').textContent).toBe('1 try left');
		expect(screen.queryByTestId('interaction-show-answer')).toBeNull();
		await fireEvent.click(screen.getByTestId('interaction-try-again'));
		await click('Alpha');
		await fireEvent.click(check());
		expect(screen.queryByTestId('interaction-try-again')).toBeNull();
		await fireEvent.click(screen.getByTestId('interaction-show-answer'));
		expect(screen.getByTestId('correct-answer-label').textContent).toBe('Correct answer');
		expect(screen.getByRole('button', { name: 'Beta' }).getAttribute('aria-pressed')).toBe('true');
		await fireEvent.click(screen.getByTestId('interaction-show-answer'));
		expect(screen.getByRole('button', { name: 'Alpha' }).getAttribute('aria-pressed')).toBe('true');
	});

	it('practice role: reveal appears after two misses, retries stay open', async () => {
		render(InteractionShell, { node: node('choice', choiceCfg) });
		await click('Alpha');
		await fireEvent.click(check());
		expect(screen.queryByTestId('interaction-show-answer')).toBeNull();
		await fireEvent.click(screen.getByTestId('interaction-try-again'));
		await click('Alpha');
		await fireEvent.click(check());
		expect(screen.getByTestId('interaction-show-answer')).toBeTruthy();
		expect(screen.getByTestId('interaction-try-again')).toBeTruthy();
	});

	it('attempt-rules mirror the server', () => {
		const n = node('numeric', { value: 3 }, { role: 'check' });
		expect(attemptState(n, ['incorrect'])).toEqual({
			attempts_used: 1,
			attempts_left: 1,
			reveal: null
		});
		expect(attemptState(n, ['incorrect', 'incorrect']).reveal).toEqual({ value: 3 });
		expect(attemptState(n, ['correct']).attempts_left).toBe(0);
		expect(revealFor(node('fill-blank', { answers: [['a', 'b'], 'c'] }))).toEqual({
			blanks: ['a', 'c']
		});
		const pairs = evaluateLocalAttempt(
			node('match-pairs', matchConfig),
			{ matches: [{ left: 'Roots', right: 'Water' }] },
			{ correct: 'y', incorrect: 'n' },
			[]
		);
		expect(pairs.score_possible).toBe(3);
		expect(pairs.score_earned).toBe(1);
		expect(pairs.item_results).toEqual({ Roots: true, Leaves: false, Stem: false });
	});
});

describe('with a server (onSubmit)', () => {
	const choiceCfg = {
		options: [
			{ id: 'a', text: 'Alpha' },
			{ id: 'b', text: 'Beta' }
		]
	};

	it('hides Try again at attempts_left 0 and Show answer fills the reveal', async () => {
		const result: ServerEvaluation = {
			outcome: 'incorrect',
			feedback: 'Not quite.',
			item_results: { a: false },
			attempts_used: 2,
			attempts_left: 0,
			reveal: { selected_option_id: 'b' }
		};
		const onSubmit = vi.fn().mockResolvedValue(result);
		render(InteractionShell, { node: node('choice', choiceCfg, { role: 'check' }), onSubmit });
		await click('Alpha');
		await fireEvent.click(check());
		await waitFor(() => expect(screen.getByRole('status')).toBeTruthy());
		expect(onSubmit).toHaveBeenCalledWith({ selected_option_id: 'a' });
		expect(screen.queryByTestId('interaction-try-again')).toBeNull();
		await fireEvent.click(screen.getByTestId('interaction-show-answer'));
		expect(screen.getByRole('button', { name: 'Beta' }).getAttribute('aria-pressed')).toBe('true');
		expect((screen.getByRole('button', { name: 'Beta' }) as HTMLButtonElement).disabled).toBe(true);
	});

	it('shows Try again while tries remain', async () => {
		const onSubmit = vi.fn().mockResolvedValue({
			outcome: 'incorrect',
			feedback: 'No.',
			attempts_used: 1,
			attempts_left: 1,
			reveal: null
		});
		render(InteractionShell, { node: node('choice', choiceCfg, { role: 'check' }), onSubmit });
		await click('Alpha');
		await fireEvent.click(check());
		await waitFor(() => expect(screen.getByTestId('interaction-try-again')).toBeTruthy());
		expect(screen.getByTestId('interaction-tries').textContent).toBe('1 try left');
	});
});

describe('resume', () => {
	it('restores the saved answer with marks and offers Try again', () => {
		render(InteractionShell, {
			node: node('match-pairs', {
				left_items: ['Roots', 'Leaves'],
				right_items: ['Food', 'Water']
			}),
			initialResponse: {
				matches: [
					{ left: 'Roots', right: 'Water' },
					{ left: 'Leaves', right: 'Water' }
				]
			},
			initialEvaluation: {
				outcome: 'partial',
				feedback: 'One right.',
				item_results: { Roots: true, Leaves: false },
				attempts_used: 1,
				attempts_left: null,
				reveal: null
			}
		});
		const roots = screen.getByRole('button', { name: 'Roots' });
		expect(roots.getAttribute('aria-pressed')).toBe('true');
		expect(roots.getAttribute('data-mark')).toBe('right');
		expect(screen.getByRole('button', { name: 'Leaves' }).getAttribute('data-mark')).toBe('wrong');
		expect(screen.getByTestId('interaction-try-again')).toBeTruthy();
		expect(status().textContent).toContain('One right.');
	});

	it('restores a locked answer with no Try again', () => {
		render(InteractionShell, {
			node: node('fill-blank', { blank_count: 2 }, { role: 'check' }),
			initialResponse: { blanks: ['a', 'b'] },
			initialEvaluation: {
				outcome: 'incorrect',
				feedback: 'No.',
				item_results: [false, false],
				attempts_used: 2,
				attempts_left: 0,
				reveal: { blanks: ['x', 'y'] }
			}
		});
		const boxes = screen.getAllByRole('textbox') as HTMLInputElement[];
		expect(boxes.map((b) => b.value)).toEqual(['a', 'b']);
		expect(boxes.every((b) => b.disabled)).toBe(true);
		expect(screen.queryByTestId('interaction-try-again')).toBeNull();
		expect(screen.getByTestId('interaction-show-answer')).toBeTruthy();
	});
});

describe('fill-blank sentence', () => {
	it('renders inline gaps for [n] markers and keeps the {blanks} response', async () => {
		const onSubmit = vi.fn().mockResolvedValue({ outcome: 'correct', feedback: 'ok' });
		render(InteractionShell, {
			node: node('fill-blank', {
				blank_count: 2,
				sentence: 'Leaves absorb light with [2] and breathe through [1].'
			}),
			onSubmit
		});
		expect(screen.queryByLabelText('Blank 1')).toBeNull();
		await fireEvent.input(screen.getByLabelText('Gap 1'), { target: { value: 'stomata' } });
		await fireEvent.input(screen.getByLabelText('Gap 2'), { target: { value: 'chlorophyll' } });
		await fireEvent.click(check());
		await waitFor(() =>
			expect(onSubmit).toHaveBeenCalledWith({ blanks: ['stomata', 'chlorophyll'] })
		);
		expect(screen.getByText(/Leaves absorb light with/)).toBeTruthy();
	});

	it('falls back to numbered boxes without a sentence', () => {
		render(InteractionShell, { node: node('fill-blank', { blank_count: 2 }) });
		expect(screen.getByLabelText('Blank 1')).toBeTruthy();
		expect(screen.queryByLabelText('Gap 1')).toBeNull();
	});
});
