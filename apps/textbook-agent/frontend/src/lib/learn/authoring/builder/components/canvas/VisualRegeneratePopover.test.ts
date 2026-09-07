import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { V3VisualBlock } from '$lib/api/v3';

const regenerateV3Visual = vi.hoisted(() => vi.fn());

vi.mock('$lib/api/v3', () => ({ regenerateV3Visual }));

import VisualRegeneratePopover from './VisualRegeneratePopover.svelte';

const visual: V3VisualBlock = {
	visual_id: 'vis-1',
	attaches_to: 'build',
	mode: 'diagram',
	image_url: 'https://old/image.png',
	qc_correction_hint: 'Make labels clearer.'
};

describe('VisualRegeneratePopover', () => {
	beforeEach(() => {
		regenerateV3Visual.mockReset();
		regenerateV3Visual.mockResolvedValue({ ...visual, image_url: 'https://new/image.png' });
	});

	it('prefills the correction hint and makes one regeneration request', async () => {
		const onCompleted = vi.fn();
		const onRegenerated = vi.fn();
		render(VisualRegeneratePopover, {
			props: {
				presentation: 'inline',
				generationId: 'gen-1',
				visual,
				onCompleted,
				onRegenerated
			}
		});

		expect((screen.getByLabelText('Regeneration note') as HTMLTextAreaElement).value).toBe(
			'Make labels clearer.'
		);
		await fireEvent.click(screen.getByRole('button', { name: 'Regenerate image' }));

		await waitFor(() => expect(regenerateV3Visual).toHaveBeenCalledTimes(1));
		expect(regenerateV3Visual).toHaveBeenCalledWith({
			generation_id: 'gen-1',
			visual_id: 'vis-1',
			teacher_hint: 'Make labels clearer.'
		});
		expect(onCompleted).toHaveBeenCalledWith(
			expect.objectContaining({ image_url: 'https://new/image.png' })
		);
		expect(onRegenerated).toHaveBeenCalledTimes(1);
	});

	it('shows the unavailable state and disables regeneration without an exact match', () => {
		render(VisualRegeneratePopover, {
			props: { presentation: 'inline', generationId: 'gen-1' }
		});

		expect(
			screen.getByText('This image will be generated on the next lesson build')
		).not.toBeNull();
		expect(
			(screen.getByRole('button', { name: 'Regenerate image' }) as HTMLButtonElement).disabled
		).toBe(true);
		expect(regenerateV3Visual).not.toHaveBeenCalled();
	});

	it('retains the issue callback when regeneration fails', async () => {
		regenerateV3Visual.mockRejectedValueOnce(new Error('provider failed'));
		const onCompleted = vi.fn();
		render(VisualRegeneratePopover, {
			props: { presentation: 'inline', generationId: 'gen-1', visual, onCompleted }
		});
		await fireEvent.click(screen.getByRole('button', { name: 'Regenerate image' }));

		expect((await screen.findByRole('alert')).textContent).toContain('provider failed');
		expect(onCompleted).not.toHaveBeenCalled();
	});
});
