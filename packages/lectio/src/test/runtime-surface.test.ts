import { render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import TemplateDetailView from '$lib/templates/TemplateDetailView.svelte';
import TemplatePreviewSurface from '$lib/templates/TemplatePreviewSurface.svelte';
import TemplateRuntimeSurface from '$lib/templates/TemplateRuntimeSurface.svelte';
import { templateRegistryMap } from '$lib/templates/registry';

const templateId = 'guided-concept-path';
const definition = templateRegistryMap[templateId];
const guidedDiscoveryTemplateId = 'guided-discovery';
const guidedDiscoveryDefinition = templateRegistryMap[guidedDiscoveryTemplateId];
const guidedDiscoveryPresetId = guidedDiscoveryDefinition.presets[0].id;
const fallbackPresetId =
	definition.presets.find((preset) => preset.id === 'warm-paper')?.id ?? definition.presets[0].id;

describe('runtime surfaces', () => {
	beforeEach(() => {
		vi.spyOn(console, 'warn').mockImplementation(() => {});
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	it('renders preview content from templateId and presetId', () => {
		render(TemplatePreviewSurface, {
			props: { templateId, presetId: 'blue-classroom' }
		});

		expect(screen.getByText(definition.contract.name)).toBeInTheDocument();
		expect(screen.getByText(definition.preview.summary)).toBeInTheDocument();
		expect(document.querySelector('[data-lectio-preset="blue-classroom"]')).toBeInTheDocument();
	});

	it('respects showMetadata on the public preview surface', () => {
		render(TemplatePreviewSurface, {
			props: { templateId, showMetadata: false }
		});

		expect(screen.queryByText('Template preview')).not.toBeInTheDocument();
		expect(screen.getByText(definition.preview.summary)).toBeInTheDocument();
	});

	it('renders runtime content from templateId and section', () => {
		render(TemplateRuntimeSurface, {
			props: {
				templateId,
				presetId: 'blue-classroom',
				section: definition.preview.section
			}
		});

		expect(
			screen.getByText(definition.preview.section.header?.title ?? definition.contract.name)
		).toBeInTheDocument();
		expect(document.querySelector('[data-lectio-preset="blue-classroom"]')).toBeInTheDocument();
	});

	it('does not reserve guided-concept-path glossary columns when glossary is missing', () => {
		const { container } = render(TemplateRuntimeSurface, {
			props: {
				templateId,
				presetId: 'blue-classroom',
				section: {
					...definition.preview.section,
					glossary: undefined
				}
			}
		});

		expect(container.innerHTML).not.toContain('lg:grid-cols-[1fr_280px]');
	});

	it('reserves guided-concept-path glossary columns when glossary exists', () => {
		const { container } = render(TemplateRuntimeSurface, {
			props: {
				templateId,
				presetId: 'blue-classroom',
				section: definition.preview.section
			}
		});

		expect(container.innerHTML).toContain('lg:grid-cols-[1fr_280px]');
	});

	it('does not reserve guided-discovery glossary columns when glossary is missing', () => {
		const { container } = render(TemplateRuntimeSurface, {
			props: {
				templateId: guidedDiscoveryTemplateId,
				presetId: guidedDiscoveryPresetId,
				section: {
					...guidedDiscoveryDefinition.preview.section,
					glossary: undefined
				}
			}
		});

		expect(container.innerHTML).not.toContain('lg:grid-cols-[1fr_280px]');
	});

	it('reserves guided-discovery glossary columns when glossary exists', () => {
		const { container } = render(TemplateRuntimeSurface, {
			props: {
				templateId: guidedDiscoveryTemplateId,
				presetId: guidedDiscoveryPresetId,
				section: guidedDiscoveryDefinition.preview.section
			}
		});

		expect(container.innerHTML).toContain('lg:grid-cols-[1fr_280px]');
	});

	it('falls back to the default preset when presetId is invalid', () => {
		render(TemplateRuntimeSurface, {
			props: {
				templateId,
				presetId: 'not-a-real-preset',
				section: definition.preview.section
			}
		});

		expect(
			document.querySelector(`[data-lectio-preset="${fallbackPresetId}"]`)
		).toBeInTheDocument();
		expect(console.warn).toHaveBeenCalled();
	});

	it('shows friendly fallback content for unknown template ids', () => {
		render(TemplatePreviewSurface, {
			props: { templateId: 'unknown-template' }
		});

		expect(screen.getByText('Unknown Lectio template: unknown-template')).toBeInTheDocument();
	});

	it('keeps the template detail page wired through the public preview surface', () => {
		render(TemplateDetailView, {
			props: { templateId }
		});

		expect(screen.getByText(definition.preview.summary)).toBeInTheDocument();
		expect(
			screen.queryByText('Unknown Lectio template: guided-concept-path')
		).not.toBeInTheDocument();
	});
});
