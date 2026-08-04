// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';

import LectioDocumentView from './LectioDocumentView.svelte';
import PrintModeDocumentView from './__fixtures__/PrintModeDocumentView.svelte';

const imagePipelineDocument = {
	generation_id: 'gen_package_smoke',
	subject: 'Newtonian motion',
	context: 'A package-smoke lesson proving hook, diagram-series, and diagram-compare images render end-to-end.',
	template_id: 'open-canvas',
	preset_id: 'blue-classroom',
	status: 'completed',
	section_manifest: [],
	sections: [
		{
			section_id: 'sec_package_smoke',
			template_id: 'open-canvas',
			header: {
				title: 'Diagram-led walkthrough',
				subject: 'Physics',
				grade_band: 'secondary'
			},
			hook: {
				headline: 'The same push does not move every object equally',
				body: 'A realism image should anchor the lesson before the formal explanation starts.',
				anchor: 'mass changes how strongly a force changes motion',
				image: {
					url: '/images/hook-realism.png',
					alt: 'Generated realism hook'
				}
			},
			explanation: {
				body: 'Mass resists acceleration, so the same net force produces different changes in motion.',
				emphasis: ['Mass resists acceleration']
			},
			diagram_series: {
				title: 'Force changes motion',
				diagrams: [
					{
						step_label: 'Image step',
						caption: 'A generated step image for the diagram series.',
						image_url: '/images/series-step-1.png'
					},
					{
						step_label: 'SVG step',
						caption: 'Inline SVG still works after an image-backed step.',
						svg_content:
							'<svg viewBox="0 0 120 80" xmlns="http://www.w3.org/2000/svg"><text x="12" y="44">Force applied</text></svg>'
					}
				]
			},
			diagram_compare: {
				before_label: 'Before push',
				after_label: 'After push',
				before_image_url: '/images/compare-before.png',
				after_image_url: '/images/compare-after.png',
				before_details: ['Net force is not yet acting.'],
				after_details: ['The net force now changes the motion.'],
				caption: 'The same scene before and after the applied force changes the motion.',
				alt_text: 'Before and after comparison showing the same object before and after a push.'
			},
			practice: {
				problems: [
					{
						difficulty: 'warm',
						question: 'What happens to acceleration when the same force pushes a heavier object?',
						hints: [{ level: 1, text: 'Use F = ma.' }]
					},
					{
						difficulty: 'medium',
						question: 'What net force acts when acceleration is zero?',
						hints: [{ level: 1, text: 'Think about balanced forces.' }]
					}
				]
			},
			what_next: {
				body: 'Next we compare how changing the net force changes acceleration over time.',
				next: 'Net force over time'
			}
		}
	],
	failed_sections: [],
	qc_reports: [],
	quality_passed: true,
	error: null,
	created_at: '2026-04-07T00:00:00Z',
	updated_at: '2026-04-07T00:00:00Z',
	completed_at: '2026-04-07T00:01:00Z'
} as any;

const simulationPipelineDocument = {
	generation_id: 'gen_package_simulation',
	subject: 'Probability',
	context: 'A package-smoke lesson proving simulation payloads render through Lectio unchanged.',
	template_id: 'open-canvas',
	preset_id: 'blue-classroom',
	status: 'completed',
	section_manifest: [],
	sections: [
		{
			section_id: 'sec_package_simulation',
			template_id: 'open-canvas',
			header: {
				title: 'Explore random outcomes',
				subject: 'Mathematics',
				grade_band: 'secondary'
			},
			hook: {
				headline: 'Random does not mean patternless',
				body: 'Repeated trials still produce stable distributions.',
				anchor: 'probability'
			},
			explanation: {
				body: 'Use the simulation to compare short runs with long runs.',
				emphasis: ['short runs', 'long runs']
			},
			simulation: {
				spec: {
					type: 'probability_tree',
					goal: 'Compare short and long runs',
					anchor_content: {
						headline: 'Coin flip trials'
					},
					context: {
						learner_level: 'secondary',
						template_id: 'open-canvas',
						color_mode: 'light',
						accent_color: '#17417a',
						surface_color: '#f7fbff',
						font_mono: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace'
					},
					dimensions: {
						width: '100%',
						height: 360,
						resizable: true
					},
					print_translation: 'static_diagram'
				},
				html_content:
					'<!DOCTYPE html><html><body><main><h1>Coin Flip Sandbox</h1><p>Heads: 8, Tails: 12</p></main></body></html>',
				fallback_diagram: {
					caption: 'Static print fallback for the simulation.',
					alt_text: 'A summary diagram of heads and tails outcomes.',
					svg_content:
						'<svg viewBox="0 0 200 120" xmlns="http://www.w3.org/2000/svg"><text x="12" y="48">Heads: 8</text><text x="12" y="84">Tails: 12</text></svg>'
				},
				explanation: 'Use the controls to compare how the distribution settles over time.'
			},
			practice: {
				problems: [
					{
						difficulty: 'warm',
						question: 'What changes as the number of trials grows?',
						hints: [{ level: 1, text: 'Look at the balance between heads and tails.' }]
					}
				]
			},
			what_next: {
				body: 'Next we connect repeated trials to expected value.',
				next: 'Expected value'
			}
		}
	],
	failed_sections: [],
	qc_reports: [],
	quality_passed: true,
	error: null,
	created_at: '2026-04-07T00:00:00Z',
	updated_at: '2026-04-07T00:00:00Z',
	completed_at: '2026-04-07T00:01:00Z'
} as any;

const printCoveragePipelineDocument = {
	generation_id: 'gen_package_print',
	subject: 'Integrated print fallback coverage',
	context:
		'A package-smoke lesson proving practice, short-answer, simulation, timeline, worked-example, and fill-in-blank render in print mode.',
	template_id: 'open-canvas',
	preset_id: 'blue-classroom',
	status: 'completed',
	section_manifest: [],
	sections: [
		{
			section_id: 'sec_package_print',
			template_id: 'open-canvas',
			header: {
				title: 'Print fallback coverage',
				subject: 'Integrated Science',
				grade_band: 'secondary'
			},
			hook: {
				headline: 'Print and screen should stay aligned',
				body: 'The fallback render should preserve instructional intent.',
				anchor: 'print parity'
			},
			explanation: {
				body: 'Each interactive or structured block should degrade gracefully for print output.',
				emphasis: ['graceful print fallback']
			},
			practice: {
				problems: [
					{
						difficulty: 'warm',
						question: 'Practice check: estimate the probability of two heads in two flips.',
						hints: [{ level: 1, text: 'List the outcomes HH, HT, TH, TT.' }]
					}
				]
			},
			worked_example: {
				title: 'Worked example: two-coin outcomes',
				setup: 'Count outcomes where both coins land heads.',
				steps: [{ label: '1', content: 'There is one favourable outcome out of four total outcomes.' }],
				conclusion: 'The probability is 1/4.',
				answer: '1/4'
			},
			short_answer: {
				question: 'Short answer prompt: explain why long-run frequency stabilizes.',
				marks: 3,
				lines: 4
			},
			fill_in_blank: {
				instruction: 'Fill in the missing term.',
				segments: [
					{ text: 'As trials increase, frequency approaches ', is_blank: false },
					{ text: 'probability', is_blank: true, answer: 'probability' },
					{ text: '.', is_blank: false }
				],
				word_bank: ['probability']
			},
			timeline: {
				title: 'Timeline of probability thinking',
				intro: 'Milestones that shaped modern probability.',
				events: [
					{
						id: 't-1',
						year: '1654',
						title: 'Pascal and Fermat correspondence',
						summary: 'Early formal treatment of chance.'
					},
					{
						id: 't-2',
						year: '1812',
						title: 'Laplace synthesis',
						summary: 'Probability consolidated into a broad framework.'
					}
				],
				closing_takeaway: 'Probability evolved from games to a general decision tool.'
			},
			simulation: {
				spec: {
					type: 'probability_tree',
					goal: 'Compare short and long runs',
					anchor_content: {
						headline: 'Coin flip trials'
					},
					context: {
						learner_level: 'secondary',
						template_id: 'open-canvas',
						color_mode: 'light',
						accent_color: '#17417a',
						surface_color: '#f7fbff',
						font_mono: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace'
					},
					dimensions: {
						width: '100%',
						height: 360,
						resizable: true
					},
					print_translation: 'static_diagram'
				},
				html_content:
					'<!DOCTYPE html><html><body><main><h1>Interactive Probability Sandbox</h1><p>Heads: 9, Tails: 11</p></main></body></html>',
				fallback_diagram: {
					caption: 'Static print fallback for all six component checks.',
					alt_text: 'A static print fallback for simulation output.',
					svg_content:
						'<svg viewBox="0 0 200 120" xmlns="http://www.w3.org/2000/svg"><text x="12" y="48">Heads: 9</text><text x="12" y="84">Tails: 11</text></svg>'
				},
				explanation: 'Use the simulation controls to compare sample size effects.'
			},
			what_next: {
				body: 'Next we connect probability to expected value.',
				next: 'Expected value and risk'
			}
		}
	],
	failed_sections: [],
	qc_reports: [],
	quality_passed: true,
	error: null,
	created_at: '2026-04-07T00:00:00Z',
	updated_at: '2026-04-07T00:00:00Z',
	completed_at: '2026-04-07T00:01:00Z'
} as any;

describe('LectioDocumentView package smoke', () => {
	afterEach(() => {
		cleanup();
	});

	it('renders package hook, diagram-series, and diagram-compare images through the real Lectio package', async () => {
		const { container } = render(LectioDocumentView, {
			props: {
				document: imagePipelineDocument
			}
		});

		expect(screen.getByRole('img', { name: 'Generated realism hook' })).toBeTruthy();
		expect(
			screen.getByRole('img', { name: 'A generated step image for the diagram series.' })
		).toBeTruthy();
		expect(
			container.querySelector('img[src="/images/compare-before.png"]')
		).toBeTruthy();
		expect(
			container.querySelector('img[src="/images/compare-after.png"]')
		).toBeTruthy();
		expect(screen.getByText('Diagram-led walkthrough')).toBeTruthy();
		expect(screen.getByText('Force changes motion')).toBeTruthy();

		await fireEvent.click(screen.getByRole('button', { name: /Next/i }));

		expect(screen.getByText('Step 2 of 2')).toBeTruthy();
		expect(screen.getByText('Force applied')).toBeTruthy();

		await fireEvent.input(screen.getByLabelText('Reveal the after state'), {
			target: { value: '100' }
		});

		expect(screen.getByText('The net force now changes the motion.')).toBeTruthy();
	});

	it('renders package simulation payloads with live html and preserved fallback metadata', () => {
		const { container } = render(LectioDocumentView, {
			props: {
				document: simulationPipelineDocument
			}
		});

		const iframe = container.querySelector('iframe[srcdoc*="Coin Flip Sandbox"]');
		expect(iframe).toBeTruthy();
		expect(screen.getByText(/Use the controls to compare how the distribution settles over time\./i)).toBeTruthy();
		expect(screen.getByText('Explore random outcomes')).toBeTruthy();
	});

	it('renders print-mode fallbacks for practice, short-answer, simulation, timeline, worked-example, and fill-in-blank', () => {
		const { container } = render(PrintModeDocumentView, {
			props: {
				document: printCoveragePipelineDocument
			}
		});

		expect(container.querySelector('[data-print-mode="true"]')).toBeTruthy();
		expect(screen.getByText('Practice check: estimate the probability of two heads in two flips.')).toBeTruthy();
		expect(screen.getByText('Short answer prompt: explain why long-run frequency stabilizes.')).toBeTruthy();
		expect(screen.getAllByText('Worked example: two-coin outcomes')).toHaveLength(2);
		expect(screen.getByText('Timeline of probability thinking')).toBeTruthy();
		expect(screen.getByText('Pascal and Fermat correspondence')).toBeTruthy();
		expect(screen.getByText('Static print fallback for all six component checks.')).toBeTruthy();
		expect(screen.getAllByText('probability').length).toBeGreaterThan(0);
	});
});
