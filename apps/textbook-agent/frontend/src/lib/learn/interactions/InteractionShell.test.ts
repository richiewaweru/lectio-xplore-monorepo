import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import InteractionShell from './InteractionShell.svelte';
import type { InteractionNode } from '$lib/learn/document/types';

const predictionNode: InteractionNode = {
	id: 'predict-1',
	kind: 'interaction',
	interaction_type: 'choice',
	prompt: 'Full context about the evidence.',
	display_prompt: 'Where will the evidence point?',
	role: 'predict',
	config: {
		options: [
			{ id: 'soil', text: 'Soil' },
			{ id: 'light', text: 'Light' }
		],
		correct_option_id: 'light'
	},
	feedback: { saved: 'Saved; revisit this after the evidence.' }
};

describe('InteractionShell task roles', () => {
	it('saves predictions without showing grading language', async () => {
		render(InteractionShell, { node: predictionNode });

		expect(screen.getByText('Where will the evidence point?')).toBeTruthy();
		const soil = screen.getByRole('button', { name: 'Soil' });
		await fireEvent.click(soil);
		expect(soil.getAttribute('aria-pressed')).toBe('true');
		await fireEvent.click(screen.getByTestId('interaction-check'));

		expect(screen.getByRole('status').textContent).toBe(
			'Saved; revisit this after the evidence.'
		);
		expect(screen.queryByText('Correct')).toBeNull();
		expect(screen.queryByText('Not yet')).toBeNull();
	});
});

const matchNode: InteractionNode = {
	id: 'match-1',
	kind: 'interaction',
	interaction_type: 'match-pairs',
	prompt: 'Match each part to its job.',
	role: 'practice',
	config: {
		pairs: [
			{ left: 'Roots', right: 'Take in water' },
			{ left: 'Leaves', right: 'Make food' }
		]
	},
	feedback: { correct: 'Both pairs are right.', incorrect: 'Look at the jobs again.' }
};

describe('InteractionShell match-pairs', () => {
	it('uses native buttons with a pressed state on both columns', async () => {
		render(InteractionShell, { node: matchNode });

		const roots = screen.getByRole('button', { name: 'Roots' });
		expect(roots.tagName).toBe('BUTTON');
		expect(roots.getAttribute('aria-pressed')).toBe('false');
		await fireEvent.click(roots);
		expect(roots.getAttribute('aria-pressed')).toBe('true');

		const water = screen.getByRole('button', { name: 'Take in water' });
		expect(water.getAttribute('aria-pressed')).toBe('false');
		await fireEvent.click(water);
		expect(water.getAttribute('aria-pressed')).toBe('true');
		// the left item stays marked once it has a match
		expect(roots.getAttribute('aria-pressed')).toBe('true');
	});

	it('shows a green check icon only on correct feedback', async () => {
		render(InteractionShell, { node: matchNode });
		for (const [l, r] of [['Roots', 'Take in water'], ['Leaves', 'Make food']]) {
			await fireEvent.click(screen.getByRole('button', { name: l }));
			await fireEvent.click(screen.getByRole('button', { name: r }));
		}
		await fireEvent.click(screen.getByTestId('interaction-check'));
		const status = screen.getByRole('status');
		expect(status.textContent).toBe('Both pairs are right.');
		const icon = screen.getByTestId('feedback-correct-icon');
		expect(icon.getAttribute('aria-hidden')).toBe('true');
		expect(icon.innerHTML).toContain('#1B5E40');
	});

	it('shows no check icon on incorrect feedback', async () => {
		render(InteractionShell, { node: matchNode });
		await fireEvent.click(screen.getByRole('button', { name: 'Roots' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Make food' }));
		await fireEvent.click(screen.getByTestId('interaction-check'));
		expect(screen.getByRole('status').getAttribute('data-outcome')).not.toBe('correct');
		expect(screen.queryByTestId('feedback-correct-icon')).toBeNull();
	});
});

const classifyNode = (categories: unknown): InteractionNode => ({
	id: 'classify-1',
	kind: 'interaction',
	interaction_type: 'classify',
	prompt: 'Sort each living thing into its group.',
	role: 'practice',
	config: {
		items: ['Sunflower', 'Biscuit the hamster'],
		categories,
		pairs: [
			{ left: 'Sunflower', right: 'Plant' },
			{ left: 'Biscuit the hamster', right: 'Animal' }
		]
	},
	feedback: { correct: 'All sorted.', incorrect: 'Try again.' }
});

describe('InteractionShell classify with plain string items', () => {
	it.each([
		['string categories', ['Plant', 'Animal']],
		[
			'object categories',
			[
				{ id: 'plant', label: 'Plant' },
				{ id: 'animal', label: 'Animal' }
			]
		]
	])('renders string items and %s without throwing', (_name, categories) => {
		render(InteractionShell, { node: classifyNode(categories) });

		expect(screen.getByRole('button', { name: 'Sunflower' })).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Biscuit the hamster' })).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Plant' })).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Animal' })).toBeTruthy();
	});
});

const sequenceNode: InteractionNode = {
	id: 'sequence-1',
	kind: 'interaction',
	interaction_type: 'sequence',
	prompt: 'Put the life cycle in order.',
	role: 'practice',
	config: {
		items: ['Seed', 'Sprout', 'Plant'],
		order: ['Seed', 'Sprout', 'Plant']
	},
	feedback: { correct: 'Right order.', incorrect: 'Look again.' }
};

describe('InteractionShell sequence with plain string items', () => {
	it('renders every string item', () => {
		render(InteractionShell, { node: sequenceNode });

		expect(screen.getByText('Seed')).toBeTruthy();
		expect(screen.getByText('Sprout')).toBeTruthy();
		expect(screen.getByText('Plant')).toBeTruthy();
		expect(screen.getAllByRole('listitem')).toHaveLength(3);
	});
});
