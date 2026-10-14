import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import InteractionShell from '../InteractionShell.svelte';
import type { InteractionNode } from '$lib/learn/document/types';

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

const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const check = () => screen.getByTestId('interaction-check');

describe('multi-select form', () => {
	const multi = node('multi-select', {
		options: [
			{ id: 'a', text: 'Alpha' },
			{ id: 'b', text: 'Beta' }
		]
	});

	it('shows the hint and toggles checkbox state', async () => {
		render(InteractionShell, { node: multi });
		expect(screen.getByTestId('multi-hint').textContent).toBe('Choose all that apply');
		expect(screen.getByRole('group', { name: 'Choose all that apply' })).toBeTruthy();
		const alpha = screen.getByRole('checkbox', { name: 'Alpha' });
		expect(alpha.getAttribute('aria-checked')).toBe('false');
		await fireEvent.click(alpha);
		expect(alpha.getAttribute('aria-checked')).toBe('true');
		await fireEvent.click(alpha);
		expect(alpha.getAttribute('aria-checked')).toBe('false');
	});
});

describe('numeric form', () => {
	it('shows the unit and passes through the number attributes', () => {
		render(InteractionShell, {
			node: node('numeric', { unit: 'cm', min: 0, max: 50, step: 0.5 })
		});
		const input = screen.getByLabelText('Answer') as HTMLInputElement;
		expect(input.getAttribute('inputmode')).toBe('decimal');
		expect(input.getAttribute('min')).toBe('0');
		expect(input.getAttribute('max')).toBe('50');
		expect(input.getAttribute('step')).toBe('0.5');
		const unit = screen.getByText('cm');
		expect(input.getAttribute('aria-describedby')).toBe(unit.id);
	});
});

describe('short-response form', () => {
	it('sizes the textarea from answer_lines and notes teacher review', () => {
		render(InteractionShell, {
			node: node('short-response', {
				answer_lines: 6,
				evaluation: 'teacher-review',
				max_length: 200
			})
		});
		const area = screen.getByLabelText('Answer') as HTMLTextAreaElement;
		expect(area.tagName).toBe('TEXTAREA');
		expect(area.rows).toBe(6);
		expect(screen.getByTestId('teacher-note').textContent).toBe('Your teacher will read this.');
		expect(screen.getByTestId('short-guide').textContent).toContain('0 / 200');
	});

	it('defaults to three rows', () => {
		render(InteractionShell, { node: node('short-response', {}) });
		expect((screen.getByLabelText('Answer') as HTMLTextAreaElement).rows).toBe(3);
	});
});

describe('fill-blank form', () => {
	it('renders one inline, labelled input per gap in a sentence', () => {
		const { container } = render(InteractionShell, {
			node: node('fill-blank', { blank_count: 2, sentence: 'A [1] and a [2].' })
		});
		const inputs = container.querySelectorAll('[data-testid="fill-blank-interaction"] input');
		expect(inputs).toHaveLength(2);
		expect(screen.getByLabelText('Gap 1')).toBeTruthy();
		expect(screen.getByLabelText('Gap 2')).toBeTruthy();
	});

	it('shows numbered boxes without a sentence', () => {
		const { container } = render(InteractionShell, {
			node: node('fill-blank', { blank_count: 2 })
		});
		expect(screen.getByLabelText('Blank 2')).toBeTruthy();
		const nums = [...container.querySelectorAll('.blank-num')].map((n) => n.textContent);
		expect(nums).toEqual(['1', '2']);
	});
});

describe('match-pairs form', () => {
	const match = node('match-pairs', {
		left_items: ['Leaf', 'Root'],
		right_items: ['water', 'stomata']
	});

	it('keeps the right column in config order, lettered, left numbered', () => {
		const { container } = render(InteractionShell, { node: match });
		const cols = container.querySelectorAll('ul.col');
		const buttons = (c: Element) =>
			[...c.querySelectorAll('button')].map((b) => b.textContent?.trim());
		expect(buttons(cols[1]!)).toEqual(['water', 'stomata']);
		const badges = (c: Element) => [...c.querySelectorAll('.badge')].map((b) => b.textContent);
		expect(badges(cols[0]!)).toEqual(['1', '2']);
		expect(badges(cols[1]!)).toEqual(['A', 'B']);
	});

	it('shows a pair together and undoes it on tap', async () => {
		render(InteractionShell, { node: match });
		await click('Leaf');
		await click('stomata');
		const chips = screen.getAllByText(/↔/).map((c) => c.textContent);
		expect(chips).toContain('↔ B · stomata');
		expect(chips).toContain('↔ 1');
		const leaf = screen.getByRole('button', { name: 'Leaf' });
		expect(leaf.getAttribute('aria-describedby')).toBeTruthy();
		expect(document.getElementById(leaf.getAttribute('aria-describedby')!)?.textContent).toBe(
			'Leaf, matched with stomata. Tap to undo.'
		);
		await fireEvent.click(leaf);
		expect(screen.queryAllByText(/↔/)).toHaveLength(0);
		expect(leaf.getAttribute('aria-pressed')).toBe('false');
	});
});

describe('classify form', () => {
	const classify = node('classify', {
		items: ['Sunflower', 'Hamster'],
		categories: [
			{ id: 'plant', label: 'Plant' },
			{ id: 'animal', label: 'Animal' }
		]
	});

	it('shows placed items inside the group, announces, and returns them with the cross', async () => {
		render(InteractionShell, { node: classify });
		const pool = screen.getByTestId('classify-pool');
		expect(within(pool).getByRole('button', { name: 'Sunflower' })).toBeTruthy();
		await click('Sunflower');
		await click('Plant');
		const groups = screen.getAllByTestId('classify-group');
		expect(within(groups[0]!).getByText('Sunflower')).toBeTruthy();
		expect(within(pool).queryByRole('button', { name: 'Sunflower' })).toBeNull();
		expect(screen.getByTestId('classify-live').textContent).toBe('Placed Sunflower in Plant');
		await click('Remove Sunflower from Plant');
		expect(within(pool).getByRole('button', { name: 'Sunflower' })).toBeTruthy();
		expect(within(groups[0]!).queryByText('Sunflower')).toBeNull();
	});
});

describe('sequence form', () => {
	const seq = node('sequence', { items: ['Seed', 'Sprout', 'Plant'] });

	it('has a handle and numbered rows, and reorders with the arrows', async () => {
		const { container } = render(InteractionShell, { node: seq });
		expect(screen.getAllByTestId('drag-handle')).toHaveLength(3);
		const nums = [...container.querySelectorAll('.num')].map((n) => n.textContent);
		expect(nums).toEqual(['1', '2', '3']);
		const labels = () =>
			[...container.querySelectorAll('.steps .label')].map((l) => l.textContent?.trim());
		expect(labels()).toEqual(['Seed', 'Sprout', 'Plant']);
		await click('Move Plant up');
		expect(labels()).toEqual(['Seed', 'Plant', 'Sprout']);
		await click('Move Seed down');
		expect(labels()).toEqual(['Plant', 'Seed', 'Sprout']);
	});
});

describe('marks after a check', () => {
	it('adds a glyph and screen-reader text, not just colour', async () => {
		const { container } = render(InteractionShell, {
			node: node('choice', {
				options: [
					{ id: 'a', text: 'Alpha' },
					{ id: 'b', text: 'Beta' }
				],
				correct_option_id: 'b'
			})
		});
		await click('Alpha');
		await fireEvent.click(check());
		const glyph = container.querySelector('[data-mark-glyph="wrong"]');
		expect(glyph?.textContent).toBe('✗');
		expect(container.querySelector('[data-mark-text]')?.textContent).toBe('not correct');
	});

	it('marks a correct classify chip with a check', async () => {
		const { container } = render(InteractionShell, {
			node: node('classify', {
				items: ['Sunflower'],
				categories: ['Plant', 'Animal'],
				pairs: [{ left: 'Sunflower', right: 'Plant' }]
			})
		});
		await click('Sunflower');
		await click('Plant');
		await fireEvent.click(check());
		expect(container.querySelector('[data-mark-glyph="right"]')?.textContent).toBe('✓');
		expect(container.querySelector('[data-mark-text]')?.textContent).toBe('correct');
	});
});
