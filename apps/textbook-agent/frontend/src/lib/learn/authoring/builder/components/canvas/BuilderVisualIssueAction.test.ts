import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const regenerateV3Visual = vi.hoisted(() => vi.fn());

vi.mock('$lib/api/v3', () => ({ regenerateV3Visual }));

import BuilderVisualIssueAction from './BuilderVisualIssueAction.svelte';

describe('BuilderVisualIssueAction', () => {
	it('regenerates the flagged image with the edited hint and then requests a snapshot poll', async () => {
		regenerateV3Visual.mockResolvedValue({ visual_id: 'vis-1', image_url: 'https://new/image.png' });
		const onRegenerated = vi.fn();
		const onResolved = vi.fn();
		render(BuilderVisualIssueAction, {
			props: {
				issue: { id: 'issue-1', severity: 'major', message: 'Image flagged.', kind: 'visual_quality_flagged', visual_id: 'vis-1', resolved: false },
				generationId: 'gen-1',
				visual: {
					visual_id: 'vis-1', attaches_to: 'build', mode: 'diagram',
					image_url: 'https://old/image.png', qc_reasons: ['labels unclear'],
					qc_correction_hint: 'Make labels clearer.'
				},
				onResolved,
				onRegenerated
			}
		});

		expect(screen.getByRole('img').getAttribute('src')).toBe('https://old/image.png');
		const hint = screen.getByLabelText('Regeneration note');
		await fireEvent.input(hint, { target: { value: 'Use darker labels.' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Regenerate image' }));

		await waitFor(() => expect(regenerateV3Visual).toHaveBeenCalledWith({
			generation_id: 'gen-1', visual_id: 'vis-1', teacher_hint: 'Use darker labels.'
		}));
		expect(onResolved).toHaveBeenCalledWith(expect.objectContaining({ id: 'issue-1' }));
		expect(onRegenerated).toHaveBeenCalledTimes(1);
		expect(onResolved.mock.invocationCallOrder[0]).toBeLessThan(
			onRegenerated.mock.invocationCallOrder[0]!
		);
	});
});
