import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/svelte';
import { afterEach, beforeEach, vi } from 'vitest';

declare global {
	interface Window {
		__setMockViewportWidth?: (width: number) => void;
	}
}

let mockViewportWidth = 1280;

afterEach(() => {
	cleanup();
	if (typeof window !== 'undefined') {
		window.localStorage.clear();
	}
});

class ResizeObserverMock {
	observe() {}
	unobserve() {}
	disconnect() {}
}

function matchesQuery(query: string) {
	const minWidth = query.match(/\(min-width:\s*(\d+)px\)/);
	if (minWidth) {
		return mockViewportWidth >= Number(minWidth[1]);
	}

	const maxWidth = query.match(/\(max-width:\s*(\d+)px\)/);
	if (maxWidth) {
		return mockViewportWidth <= Number(maxWidth[1]);
	}

	return false;
}

if (typeof window !== 'undefined') {
	Object.defineProperty(window, 'matchMedia', {
		writable: true,
		value: (query: string) => ({
			matches: matchesQuery(query),
			media: query,
			onchange: null,
			addListener: vi.fn(),
			removeListener: vi.fn(),
			addEventListener: vi.fn(),
			removeEventListener: vi.fn(),
			dispatchEvent: vi.fn()
		})
	});

	window.__setMockViewportWidth = (width: number) => {
		mockViewportWidth = width;
	};

	beforeEach(() => {
		mockViewportWidth = 1280;
		window.localStorage.clear();
	});
} else {
	beforeEach(() => {
		mockViewportWidth = 1280;
	});
}

Object.defineProperty(globalThis, 'ResizeObserver', {
	writable: true,
	value: ResizeObserverMock
});

if (typeof window !== 'undefined' && !window.HTMLElement.prototype.scrollIntoView) {
	window.HTMLElement.prototype.scrollIntoView = vi.fn();
}
