import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { vi } from 'vitest';

vi.mock('./V3CanvasComponent.svelte', async () => ({
	default: (await import('../../../routes/studio/__fixtures__/MockGeneric.svelte')).default
}));
vi.mock('./V3CanvasVisual.svelte', async () => ({
	default: (await import('../../../routes/studio/__fixtures__/MockGeneric.svelte')).default
}));
vi.mock('./V3LectioSectionEmbed.svelte', async () => ({
	default: (await import('../../../routes/studio/__fixtures__/MockGeneric.svelte')).default
}));

import V3CanvasSection from './V3CanvasSection.svelte';

describe('V3CanvasSection', () => {
	it('shows inspect section toggle with merged field payload', () => {
		render(V3CanvasSection, {
			section: {
				id: 'sec-1',
				title: 'Section 1',
				teacher_labels: '',
				order: 0,
				sectionStatus: 'complete',
				renderable: true,
				missingComponents: [],
				missingVisuals: [],
				diagnosticWarnings: [],
				components: [],
				visual: null,
				questions: [],
				mergedFields: { header: { title: 'Section 1' } }
			},
			templateId: 'guided-concept-path'
		});

		expect(screen.getByText('Inspect section')).toBeTruthy();
		expect(screen.getByText(/"header":/)).toBeTruthy();
	});

	it('hides inspect section payload outside debug mode', () => {
		render(V3CanvasSection, {
			section: {
				id: 'sec-1',
				title: 'Section 1',
				teacher_labels: '',
				order: 0,
				sectionStatus: 'complete',
				renderable: true,
				missingComponents: [],
				missingVisuals: [],
				diagnosticWarnings: [],
				components: [],
				visual: null,
				questions: [],
				mergedFields: { header: { title: 'Section 1' } }
			},
			templateId: 'guided-concept-path',
			debugInspect: false
		});

		expect(screen.queryByText('Inspect section')).toBeNull();
		expect(screen.queryByText(/"header":/)).toBeNull();
	});

	it('shows a retryable failure card for failed sections', () => {
		render(V3CanvasSection, {
			section: {
				id: 'sec-failed',
				title: 'Failed Section',
				teacher_labels: 'practice',
				order: 1,
				sectionStatus: 'failed',
				renderable: false,
				missingComponents: ['practice-stack'],
				missingVisuals: [],
				diagnosticWarnings: ['Section writer failed after retries.'],
				components: [],
				visual: null,
				questions: [],
				mergedFields: {}
			},
			templateId: 'guided-concept-path',
			onRetrySection: () => {}
		});

		expect(screen.getByText('Section failed')).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Retry section' })).toBeTruthy();
	});
});
