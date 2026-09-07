import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it } from 'vitest';

import ComparisonGrid from '$lib/components/lectio/ComparisonGrid.svelte';
import GlossaryRail from '$lib/components/lectio/GlossaryRail.svelte';
import PracticeStack from '$lib/components/lectio/PracticeStack.svelte';
import ProcessSteps from '$lib/components/lectio/ProcessSteps.svelte';
import TimelineBlock from '$lib/components/lectio/TimelineBlock.svelte';
import { getStableComponents } from '$lib/schema/registry';
import { templateRegistry, validateAllTemplates } from '$lib/templates/registry';
import TemplateDetailView from '$lib/templates/TemplateDetailView.svelte';
import TemplatesGallery from '$lib/templates/TemplatesGallery.svelte';
import { compareAndApplyPreview } from '$lib/templates/compare-and-apply/preview';
import { visualLedPreview } from '$lib/templates/visual-led/preview';
import { lowLoadPreview } from '$lib/templates/low-load/preview';
import { procedurePreview } from '$lib/templates/procedure/preview';
import { timelinePreview } from '$lib/templates/timeline/preview';

const STORAGE_KEY = 'template-contract-drawer-open';
const testWindow = window as Window & { __setMockViewportWidth: (width: number) => void };

function setViewportWidth(width: number) {
	testWindow.__setMockViewportWidth(width);
}

beforeEach(() => {
	setViewportWidth(1280);
	window.localStorage.clear();
});

describe('template registry', () => {
	it('registers all shipped templates with valid contracts and previews', () => {
		expect(templateRegistry.length).toBeGreaterThan(0);
		expect(templateRegistry.map((definition) => definition.contract.id)).toEqual(
			expect.arrayContaining(['guided-concept-path', 'interactive-lab', 'guided-discovery'])
		);

		const results = validateAllTemplates();

		expect(results).toHaveLength(templateRegistry.length);
		const allErrors = results.flatMap((r) => r.errors);
		expect(allErrors).toEqual([]);
	});

	it('publishes the new components into the stable registry', () => {
		const stableComponents = getStableComponents();
		const stableNames = stableComponents.map((component) => component.name);

		expect(stableNames).toEqual(expect.arrayContaining(['ComparisonGrid', 'TimelineBlock']));
	});
});

describe('new components', () => {
	it('renders the comparison grid with visible criteria and columns', () => {
		render(ComparisonGrid, {
			props: { content: compareAndApplyPreview.section.comparison_grid! }
		});

		expect(screen.getByText(/Compare the two families/i)).toBeInTheDocument();
		expect(screen.getByText(/^Bond pattern$/i)).toBeInTheDocument();
		expect(screen.getAllByText(/^Alkene$/i).length).toBeGreaterThan(0);
	});

	it('advances the timeline scrubber when the next button is pressed', async () => {
		render(TimelineBlock, {
			props: { content: timelinePreview.section.timeline! }
		});

		expect(screen.getByText(/Microscopic life observed/i)).toBeInTheDocument();

		await fireEvent.click(screen.getByRole('button', { name: /next/i }));

		expect(screen.getByText(/Handwashing evidence/i)).toBeInTheDocument();
	});
});

describe('adapted behaviours', () => {
	it('renders flat-list practice without requiring accordion expansion', async () => {
		render(PracticeStack, {
			props: { content: lowLoadPreview.section.practice!, mode: 'flat-list' }
		});

		expect(screen.getByText(/A circle is split into 4 equal pieces/i)).toBeInTheDocument();
		expect(
			screen.getByText(/A rectangle is split into 3 pieces/i)
		).toBeInTheDocument();

		await fireEvent.click(screen.getAllByRole('button', { name: /show hint/i })[0]);

		expect(
			screen.getByText(/The denominator is the total number of equal parts/i)
		).toBeInTheDocument();
	});

	it('reveals process steps progressively in step-reveal mode', async () => {
		render(ProcessSteps, {
			props: {
				content: procedurePreview.section.process!,
				mode: 'step-reveal'
			}
		});

		expect(screen.getByText(/Count atoms first/i)).toBeInTheDocument();
		expect(
			screen.queryByText(/Adjust one substance with coefficients/i)
		).not.toBeInTheDocument();

		await fireEvent.click(screen.getByRole('button', { name: /show next step/i }));

		expect(
			screen.getByText(/Adjust one substance with coefficients/i)
		).toBeInTheDocument();
	});

	it('supports glossary drawer and inline-strip variants', async () => {
		const glossary = visualLedPreview.section.glossary!;
		const { rerender } = render(GlossaryRail, {
			props: { content: glossary, mode: 'drawer' }
		});

		await fireEvent.click(screen.getByRole('button', { name: /show key terms/i }));
		expect(screen.getByText(/Chloroplast/i)).toBeInTheDocument();

		await rerender({ content: glossary, mode: 'inline-strip' });

		expect(screen.getByText(/Glossary strip/i)).toBeInTheDocument();
		expect(screen.getAllByText(/^Glucose$/i).length).toBeGreaterThan(0);
	});
});

describe('template pages', () => {
	it('filters the gallery client-side', async () => {
		render(TemplatesGallery, {
			props: {
				templates: templateRegistry.map((definition) => definition.contract)
			}
		});

		await fireEvent.click(screen.getByRole('button', { name: /visual-first/i }));

		expect(screen.getByText(/Visual Led/i)).toBeInTheDocument();
		expect(screen.getByText(/Diagram Led/i)).toBeInTheDocument();
		expect(screen.queryByText(/^Timeline$/i)).not.toBeInTheDocument();
	});

	it('keeps the persistent contract panel hidden on md+ until toggled open and remembers the preference', async () => {
		render(TemplateDetailView, {
			props: { templateId: 'timeline' }
		});

		expect(screen.getByRole('heading', { name: /^Timeline$/i, level: 1 })).toBeInTheDocument();
		expect(screen.getByText(/How germ theory took hold/i)).toBeInTheDocument();
		expect(screen.getByText(/The road to germ theory/i)).toBeInTheDocument();
		expect(
			screen.queryByRole('heading', { name: /template contract/i })
		).not.toBeInTheDocument();
		expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

		await fireEvent.click(screen.getByRole('button', { name: /show contract/i }));

		expect(
			await screen.findByRole('heading', { name: /template contract/i })
		).toBeInTheDocument();
		expect(screen.getByText(/Best for/i)).toBeInTheDocument();
		expect(window.localStorage.getItem(STORAGE_KEY)).toBe('true');
		expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
		expect(
			screen
				.getByLabelText(/template contract/i)
				.compareDocumentPosition(screen.getByText(/^seeded preview$/i)) &
				Node.DOCUMENT_POSITION_FOLLOWING
		).toBeTruthy();

		await fireEvent.click(screen.getByRole('button', { name: /hide contract/i }));

		await waitFor(() => {
			expect(
				screen.queryByRole('heading', { name: /template contract/i })
			).not.toBeInTheDocument();
		});
		expect(window.localStorage.getItem(STORAGE_KEY)).toBe('false');
	});

	it('restores the remembered desktop drawer state on a different template detail page', async () => {
		window.localStorage.setItem(STORAGE_KEY, 'true');

		render(TemplateDetailView, {
			props: { templateId: 'visual-led' }
		});

		expect(await screen.findByRole('heading', { name: /template contract/i })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: /hide contract/i })).toBeInTheDocument();
		expect(screen.getByText(/Visual Led/i)).toBeInTheDocument();
	});

	it('keeps the mobile contract closed on first render and opens it as a temporary sheet', async () => {
		setViewportWidth(480);
		window.localStorage.setItem(STORAGE_KEY, 'true');

		render(TemplateDetailView, {
			props: { templateId: 'timeline' }
		});

		expect(
			screen.queryByRole('heading', { name: /template contract/i })
		).not.toBeInTheDocument();
		expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
		expect(screen.getByText(/How germ theory took hold/i)).toBeInTheDocument();

		await fireEvent.click(screen.getByRole('button', { name: /show contract/i }));

		const dialog = await screen.findByRole('dialog');

		expect(dialog).toBeInTheDocument();
		expect(screen.getByText(/Best for/i)).toBeInTheDocument();
		expect(window.localStorage.getItem(STORAGE_KEY)).toBe('true');
		expect(dialog.className).toContain('left-0');
		expect(dialog.className).toContain('rounded-r-[1.75rem]');

		await fireEvent.click(screen.getByRole('button', { name: /close contract/i }));

		await waitFor(() => {
			expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
		});
	});
});
