// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
	SECTION_HIGHLIGHT_CLASS,
	findSectionElement,
	focusSection,
	focusSectionWhenReady,
	sectionHref
} from './section-focus';

afterEach(() => {
	document.body.innerHTML = '';
	vi.useRealTimers();
});

describe('sectionHref', () => {
	it('builds the editor deep link and hides it when nothing is built', () => {
		expect(sectionHref('/builder/l1', 's 1')).toBe('/builder/l1?section=s%201');
		expect(sectionHref('/studio/print/g1', 's-1')).toBe('/studio/print/g1?section=s-1');
		expect(sectionHref(null, 's-1')).toBeNull();
		expect(sectionHref('/builder/l1', null)).toBeNull();
	});
});

describe('focusSection', () => {
	it('scrolls to and briefly highlights a data-section-id element', () => {
		vi.useFakeTimers();
		document.body.innerHTML = '<div data-section-id="s-2"></div>';
		const el = document.querySelector<HTMLElement>('[data-section-id="s-2"]')!;
		el.scrollIntoView = vi.fn();
		expect(focusSection('s-2')).toBe(true);
		expect(el.scrollIntoView).toHaveBeenCalled();
		expect(el.classList.contains(SECTION_HIGHLIGHT_CLASS)).toBe(true);
		vi.advanceTimersByTime(3000);
		expect(el.classList.contains(SECTION_HIGHLIGHT_CLASS)).toBe(false);
	});

	it('falls back to the Print renderer section id and ignores unknown sections', () => {
		document.body.innerHTML = '<section class="lectio-section" id="s-9"></section>';
		expect(findSectionElement('s-9')?.id).toBe('s-9');
		expect(focusSection('missing')).toBe(false);
		expect(focusSection(null)).toBe(false);
	});

	it('waits for the section to render', async () => {
		vi.useFakeTimers();
		const pending = focusSectionWhenReady('late', { attempts: 5, intervalMs: 50 });
		setTimeout(() => {
			document.body.innerHTML = '<div data-section-id="late"></div>';
		}, 80);
		await vi.advanceTimersByTimeAsync(300);
		expect(await pending).toBe(true);
	});
});
