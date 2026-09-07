import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import { getStableComponents } from '$lib/schema/registry';
import AppSidebar from '$lib/navigation/AppSidebar.svelte';
import { getSidebarNavigation } from '$lib/navigation/sidebar-navigation';
import { templateRegistry } from '$lib/templates/registry';

describe('sidebar navigation', () => {
	it('derives component and template links from the live registries in order', () => {
		const navigation = getSidebarNavigation();

		expect(navigation.components.map((item) => item.label)).toEqual(
			getStableComponents().map((component) => component.name)
		);
		expect(navigation.templates.map((item) => item.label)).toEqual([
			'Template gallery',
			...templateRegistry.map((definition) => definition.contract.name)
		]);
	});

	it('renders the sidebar with stable component and template links', () => {
		render(AppSidebar, {
			props: { frameworkLabel: 'SvelteKit' }
		});

		expect(screen.getByRole('navigation', { name: /primary navigation/i })).toBeInTheDocument();
		expect(screen.getByRole('link', { name: /ComparisonGrid/i })).toHaveAttribute(
			'href',
			'/components#comparison-grid'
		);
		expect(screen.getByRole('link', { name: /TimelineBlock/i })).toHaveAttribute(
			'href',
			'/components#timeline-block'
		);
		expect(screen.getByRole('link', { name: /SimulationBlock/i })).toHaveAttribute(
			'href',
			'/components#simulation-block'
		);
		expect(screen.getByRole('link', { name: /Template gallery/i })).toHaveAttribute(
			'href',
			'/templates'
		);
		expect(screen.getByRole('link', { name: /Guided Concept Path/i })).toHaveAttribute(
			'href',
			'/templates/guided-concept-path'
		);
	});
});
