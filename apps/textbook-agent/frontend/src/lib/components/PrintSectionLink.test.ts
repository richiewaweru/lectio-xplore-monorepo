// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { SectionContent } from 'lectio';

vi.mock('qrcode-generator', () => ({
	default: () => ({
		addData: vi.fn(),
		make: vi.fn(),
		createSvgTag: vi.fn(() => '<svg data-testid="qr-svg"></svg>')
	})
}));

import PrintSectionLink from './PrintSectionLink.svelte';

const baseSection: SectionContent = {
	section_id: 's-01',
	template_id: 'guided-concept-path',
	header: {
		title: 'Interactive Section',
		subject: 'Calculus',
		grade_band: 'secondary'
	},
	hook: {
		headline: 'Hook',
		body: 'Body',
		anchor: 'anchor'
	},
	explanation: {
		body: 'Explain',
		emphasis: ['limits']
	},
	practice: {
		problems: []
	},
	what_next: {
		body: 'Next',
		next: 'Continuity'
	}
};

describe('PrintSectionLink', () => {
	afterEach(() => {
		cleanup();
	});

	it('renders a QR block for sections with a simulation', () => {
		render(PrintSectionLink, {
			generationId: 'gen-123',
			section: {
				...baseSection,
				simulation: {
					spec: {
						type: 'graph_slider',
						goal: 'Explore slope',
						anchor_content: {},
						context: {
							learner_level: 'secondary',
							template_id: 'guided-concept-path',
							color_mode: 'light',
							accent_color: '#2563eb',
							surface_color: '#ffffff',
							font_mono: 'ui-monospace'
						},
						print_translation: 'static_midstate',
						dimensions: { width: '100%', height: 400, resizable: false }
					}
				}
			}
		});

		expect(screen.getByText(/interactive simulation/i)).toBeTruthy();
		expect(screen.getByText(/scan to open/i)).toBeTruthy();
	});

	it('does NOT render a QR for sections with only a quiz', () => {
		const { container } = render(PrintSectionLink, {
			generationId: 'gen-123',
			section: {
				...baseSection,
				quiz: {
					question: 'Which value is the limit?',
					options: [],
					feedback_correct: 'Correct',
					feedback_incorrect: 'Try again'
				}
			}
		});

		expect(container.textContent?.trim()).toBe('');
	});

	it('does NOT render a QR for sections with only a diagram', () => {
		const { container } = render(PrintSectionLink, {
			generationId: 'gen-123',
			section: {
				...baseSection,
				diagram: {
					svg_content: '<svg/>',
					alt_text: 'A diagram',
					caption: '',
					callouts: []
				}
			}
		});

		expect(container.textContent?.trim()).toBe('');
	});

	it('stays hidden for non-interactive sections', () => {
		const { container } = render(PrintSectionLink, {
			generationId: 'gen-123',
			section: baseSection
		});

		expect(container.textContent?.trim()).toBe('');
	});
});
