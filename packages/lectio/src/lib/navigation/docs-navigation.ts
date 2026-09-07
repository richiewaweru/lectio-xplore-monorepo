export interface DocsNavItem {
	href: string;
	label: string;
	meta: string;
}

export interface DocsNavGroup {
	eyebrow: string;
	items: DocsNavItem[];
}

/** Primary documentation IA — used by sidebar and mobile doc nav. */
export function getDocsNavigation(): DocsNavGroup[] {
	return [
		{
			eyebrow: 'Start here',
			items: [
				{ href: '/docs', label: 'Documentation home', meta: 'Overview and section map' },
				{ href: '/docs/introduction', label: 'Introduction', meta: 'What Lectio is and who it is for' },
				{ href: '/docs/installation', label: 'Installation', meta: 'Package, deps, theme CSS' }
			]
		},
		{
			eyebrow: 'Using the library',
			items: [
				{ href: '/docs/concepts', label: 'Core concepts', meta: 'SectionContent, templates, presets' },
				{ href: '/docs/rendering', label: 'Rendering patterns', meta: 'Surfaces and layouts' },
				{ href: '/docs/best-practices', label: 'Best practices', meta: 'Teaching moves and quality' }
			]
		},
		{
			eyebrow: 'Integration',
			items: [
				{
					href: '/docs/examples/textbook-agent',
					label: 'Multi-section app example',
					meta: 'Theme surface and template.render'
				},
				{ href: '/docs/contracts', label: 'Contracts and pipelines', meta: 'JSON exports for agents' },
				{ href: '/docs/reference', label: 'Reference', meta: 'Repo markdown and showcase' }
			]
		}
	];
}

export function flattenDocsNavItems(): DocsNavItem[] {
	return getDocsNavigation().flatMap((g) => g.items);
}
