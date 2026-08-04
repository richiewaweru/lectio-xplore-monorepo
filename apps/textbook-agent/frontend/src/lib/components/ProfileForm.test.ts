// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('lectio', async () => {
	const MockTemplatePreviewSurface = (
		await import('./__fixtures__/MockTemplatePreviewSurface.svelte')
	).default;

	const blueClassroom = {
		id: 'blue-classroom',
		name: 'Blue Classroom',
		description: 'Professional classroom blue with strong structure for screen-first lessons.',
		palette: 'navy, sky, parchment'
	};

	const warmPaper = {
		id: 'warm-paper',
		name: 'Warm Paper',
		description: 'Editorial, warm neutral surfaces that feel close to a printed workbook.',
		palette: 'sand, amber, ink'
	};

	return {
		basePresets: [blueClassroom, warmPaper],
		templateRegistry: [
			{
				contract: {
					id: 'guided-concept-path',
					name: 'Guided Concept Path',
					family: 'guided-concept',
					intent: 'introduce-concept',
					tagline: 'Lead with felt need, then move steadily toward formal understanding.',
					learnerFit: ['general', 'scaffolded'],
					subjects: ['mathematics', 'science'],
					interactionLevel: 'medium'
				},
				preview: {
					summary:
						'A first-exposure calculus section that shows the full scaffold from hook to worked example to practice.',
					section: {
						header: { title: 'Why does calculus exist?' },
						hook: { headline: 'How fast is something moving at this exact instant?' }
					}
				},
				presets: [blueClassroom, warmPaper],
				render: null
			},
			{
				contract: {
					id: 'formal-track',
					name: 'Formal Track',
					family: 'guided-concept',
					intent: 'build-rigor',
					tagline: 'Minimal ornament, formal progression, and proof-aware structure.',
					learnerFit: ['analytical', 'advanced'],
					subjects: ['mathematics'],
					interactionLevel: 'none'
				},
				preview: {
					summary: 'A rigorous single-column presentation for proof-oriented content.',
					section: {
						header: { title: 'Limit laws as a formal system' },
						hook: { headline: 'Why formal steps matter when intuition stops helping.' }
					}
				},
				presets: [warmPaper],
				render: null
			}
		],
		TemplatePreviewSurface: MockTemplatePreviewSurface
	};
});

import ProfileForm from './ProfileForm.svelte';

describe('ProfileForm template runtime selection', () => {
	afterEach(() => {
		cleanup();
	});

	it('shows only the live preset and templates that support it, then opens the shared preview surface', async () => {
		const onsubmit = vi.fn();
		render(ProfileForm, { props: { onsubmit } });

		expect(screen.getByRole('button', { name: /blue classroom/i })).toBeTruthy();
		expect(screen.queryByRole('button', { name: /warm paper/i })).toBeNull();
		expect(screen.getByRole('button', { name: /preview guided concept path/i })).toBeTruthy();
		expect(screen.queryByRole('button', { name: /preview formal track/i })).toBeNull();

		await fireEvent.click(screen.getByRole('button', { name: /preview guided concept path/i }));

		expect(screen.getByRole('dialog', { name: /guided concept path preview/i })).toBeTruthy();
		expect(screen.getByTestId('template-preview-surface').getAttribute('data-preset')).toBe(
			'blue-classroom'
		);
		expect(
			screen.getByText(/a first-exposure calculus section that shows the full scaffold/i)
		).toBeTruthy();
		expect(screen.getByText(/why does calculus exist/i)).toBeTruthy();
		expect(screen.getByText(/blue classroom navy, sky, parchment/i)).toBeTruthy();

		await fireEvent.click(screen.getByRole('button', { name: /use template/i }));

		expect(screen.queryByRole('dialog')).toBeNull();
		expect(
			screen.getByRole('button', { name: /preview guided concept path/i }).classList.contains(
				'selected'
			)
		).toBe(true);
	});

	it('keeps the current request shape when the user previews before submitting', async () => {
		const onsubmit = vi.fn();
		render(ProfileForm, { props: { onsubmit } });

		await fireEvent.input(screen.getByLabelText(/^subject$/i), {
			target: { value: 'derivatives' }
		});
		await fireEvent.input(screen.getByLabelText(/^context$/i), {
			target: { value: 'show a scaffolded first pass through rate of change' }
		});

		await fireEvent.click(screen.getByRole('button', { name: /preview guided concept path/i }));
		await fireEvent.click(screen.getByRole('button', { name: /use template/i }));
		await fireEvent.click(screen.getByRole('button', { name: /start generation/i }));

		expect(onsubmit).toHaveBeenCalledWith({
			subject: 'derivatives',
			context: 'show a scaffolded first pass through rate of change',
			template_id: 'guided-concept-path',
			preset_id: 'blue-classroom',
			section_count: 4
		});
	});
});
