import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import { componentRenderMap } from '$lib/lectio/registry/render-map';
import { componentRegistry } from '$lib/schema/registry';
import { getPreviewContent } from '$lib/teacher/content-factories';
import LectioBlockRuntimeSurface from '$lib/runtime/LectioBlockRuntimeSurface.svelte';

describe('LectioBlockRuntimeSurface', () => {
	it('maps every registry component id to a runtime component', () => {
		for (const meta of Object.values(componentRegistry)) {
			expect(componentRenderMap[meta.id], meta.id).toBeDefined();
		}
	});

	it('renders a known component by id', () => {
		render(LectioBlockRuntimeSurface, {
			props: {
				componentId: 'explanation-block',
				content: getPreviewContent('explanation-block') ?? {},
				media: {}
			}
		});

		expect(screen.queryByText('Unknown component: explanation-block')).not.toBeInTheDocument();
		expect(screen.getByText('Explanation')).toBeInTheDocument();
	});

	it('shows a fallback for unknown component ids', () => {
		render(LectioBlockRuntimeSurface, {
			props: {
				componentId: 'unknown-component-id',
				content: {},
				media: {}
			}
		});

		expect(screen.getByText('Unknown component: unknown-component-id')).toBeInTheDocument();
	});
});

