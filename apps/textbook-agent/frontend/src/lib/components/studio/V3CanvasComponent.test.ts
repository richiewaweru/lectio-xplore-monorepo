import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import V3CanvasComponent from './V3CanvasComponent.svelte';

describe('V3CanvasComponent', () => {
	it('shows inspect toggle when component data exists', () => {
		render(V3CanvasComponent, {
			component: {
				id: 'c1',
				teacher_label: 'Hook',
				status: 'ready',
				data: { headline: 'Intro' }
			}
		});

		expect(screen.getByText('Inspect data')).toBeTruthy();
		expect(screen.getByText(/"headline": "Intro"/)).toBeTruthy();
	});

	it('hides inspect toggle when component data is null', () => {
		render(V3CanvasComponent, {
			component: {
				id: 'c1',
				teacher_label: 'Hook',
				status: 'pending',
				data: null
			}
		});

		expect(screen.queryByText('Inspect data')).toBeNull();
	});
});

