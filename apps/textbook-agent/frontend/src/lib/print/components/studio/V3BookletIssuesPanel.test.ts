import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
	regenerateV3Visual: vi.fn()
}));

vi.mock('$lib/api/v3', () => ({
	regenerateV3Visual: mocks.regenerateV3Visual
}));

import V3BookletIssuesPanel from './V3BookletIssuesPanel.svelte';

describe('V3BookletIssuesPanel', () => {
	it('renders a flagged image and regenerates it with the editable QC hint', async () => {
		mocks.regenerateV3Visual.mockResolvedValue({
			visual_id: 'vis-1',
			attaches_to: 'practice',
			mode: 'diagram',
			status: 'ready',
			image_url: 'https://cdn.example/replacement.png'
		});
		const onRegenerated = vi.fn();

		render(V3BookletIssuesPanel, {
			props: {
				generationId: 'gen-1',
				issues: [
					{
						category: 'visual_quality_flagged',
						message: 'image flagged by quality review: label is faint',
						generated_ref: 'practice',
						repair_target_id: 'visual:vis-1'
					}
				],
				pack: {
					generation_id: 'gen-1',
					blueprint_id: 'bp-1',
					template_id: 'guided-concept-path',
					subject: 'Math',
					status: 'draft_needs_review',
					sections: [],
					visual_blocks: [
						{
							visual_id: 'vis-1',
							attaches_to: 'practice',
							mode: 'diagram',
							status: 'flagged_quality',
							image_url: 'https://cdn.example/flagged.png',
							qc_reasons: ['label is faint'],
							qc_correction_hint: 'make the label darker'
						}
					],
					warnings: [],
					section_diagnostics: [],
					booklet_issues: []
				},
				onRegenerated
			}
		});

		expect(screen.getByRole('img', { name: 'label is faint' })).toBeTruthy();
		const hint = screen.getByLabelText('Regeneration note');
		await fireEvent.input(hint, { target: { value: 'make every label darker' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Regenerate image' }));

		await waitFor(() =>
			expect(mocks.regenerateV3Visual).toHaveBeenCalledWith({
				generation_id: 'gen-1',
				visual_id: 'vis-1',
				teacher_hint: 'make every label darker'
			})
		);
		expect(onRegenerated).toHaveBeenCalledTimes(1);
	});
});
