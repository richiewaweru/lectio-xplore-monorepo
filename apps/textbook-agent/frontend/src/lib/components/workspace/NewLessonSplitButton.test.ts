// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';

import NewLessonSplitButton from './NewLessonSplitButton.svelte';

describe('NewLessonSplitButton native destination', () => {
	afterEach(cleanup);

	it('exposes one native lesson destination without legacy menu actions', () => {
		render(NewLessonSplitButton);
		const link = screen.getByRole('link', { name: '+ New lesson' });
		expect(link.getAttribute('href')).toBe('/units?new=1');
		expect(screen.queryByRole('button')).toBeNull();
		expect(screen.queryByRole('menu')).toBeNull();
		expect(screen.queryByRole('link', { name: /blank|builder|legacy/i })).toBeNull();
	});
});
