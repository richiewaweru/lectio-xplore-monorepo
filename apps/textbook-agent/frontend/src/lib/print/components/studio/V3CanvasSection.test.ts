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
				stage2Preview: null,
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
				stage2Preview: null,
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
				stage2Preview: null,
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

	it('renders stage 2 preview content while components are still pending', () => {
		render(V3CanvasSection, {
			section: {
				id: 'sec-preview',
				title: 'Preview Section',
				teacher_labels: 'hook-hero',
				order: 0,
				sectionStatus: 'running',
				stage2Preview: {
					componentIntents: [{ componentId: 'hook-hero', intent: 'Open with a concrete anchor.' }],
					questionPrompts: ['Which two fractions show the same amount?'],
					visualSubject: 'Fraction strip comparison'
				},
				renderable: true,
				missingComponents: [],
				missingVisuals: [],
				diagnosticWarnings: [],
				components: [{ id: 'hook-hero', teacher_label: 'Hook', status: 'pending', data: null }],
				visual: null,
				questions: [],
				mergedFields: {}
			},
			templateId: 'guided-concept-path'
		});

		expect(screen.getByText('Planning…')).toBeTruthy();
		expect(screen.getByText('hook-hero:')).toBeTruthy();
		expect(screen.getByText(/Open with a concrete anchor\./)).toBeTruthy();
		expect(screen.getByText(/Q1: Which two fractions show the same amount\?/)).toBeTruthy();
		expect(screen.getByText(/Diagram: Fraction strip comparison/)).toBeTruthy();
	});

	it('hides stage 2 preview once a component is ready', () => {
		render(V3CanvasSection, {
			section: {
				id: 'sec-ready',
				title: 'Ready Section',
				teacher_labels: 'hook-hero',
				order: 0,
				sectionStatus: 'complete',
				stage2Preview: {
					componentIntents: [{ componentId: 'hook-hero', intent: 'Open with a concrete anchor.' }],
					questionPrompts: ['Which two fractions show the same amount?'],
					visualSubject: null
				},
				renderable: true,
				missingComponents: [],
				missingVisuals: [],
				diagnosticWarnings: [],
				components: [{ id: 'hook-hero', teacher_label: 'Hook', status: 'ready', data: { body: 'filled' } }],
				visual: null,
				questions: [],
				mergedFields: {}
			},
			templateId: 'guided-concept-path'
		});

		expect(screen.queryByText(/Q1:/)).toBeNull();
		expect(screen.queryByText(/Open with a concrete anchor\./)).toBeNull();
	});
});
