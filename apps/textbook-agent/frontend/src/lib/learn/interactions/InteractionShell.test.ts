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
		await fireEvent.click(screen.getByRole('radio', { name: 'Soil' }));
		await fireEvent.click(screen.getByTestId('interaction-check'));

		expect(screen.getByRole('status').textContent).toBe(
			'Saved; revisit this after the evidence.'
		);
		expect(screen.queryByText('Correct')).toBeNull();
		expect(screen.queryByText('Not yet')).toBeNull();
	});
});
