import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import ImageBlock from './ImageBlock.svelte';

const tinyPng =
	'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';

describe('ImageBlock', () => {
	it('renders image with alt text and caption', () => {
		const { container } = render(ImageBlock, {
			props: {
				content: {
					media_id: 'img1',
					alt_text: 'Diagram of a cell',
					caption: 'Figure 1',
					width: 'half',
					alignment: 'center'
				},
				media: {
					img1: {
						id: 'img1',
						type: 'image',
						url: tinyPng,
						mime_type: 'image/png'
					}
				}
			}
		});

		const img = container.querySelector('img');
		expect(img?.getAttribute('src')).toBe(tinyPng);
		expect(img?.getAttribute('alt')).toBe('Diagram of a cell');
		expect(screen.getByText('Figure 1')).toBeInTheDocument();
		const wrap = img?.closest('div');
		expect(wrap?.className).toMatch(/max-w-\[50%\]/);
	});

	it('shows fallback when media is missing', () => {
		render(ImageBlock, {
			props: {
				content: {
					media_id: 'x',
					alt_text: 'Alt'
				},
				media: {}
			}
		});

		expect(screen.getByText(/Image not available/i)).toBeInTheDocument();
	});
});
