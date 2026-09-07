import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import VideoEmbed from './VideoEmbed.svelte';

vi.mock('qrcode', () => ({
	default: {
		toDataURL: () => Promise.resolve('data:image/png;base64,QRSTUB')
	}
}));

describe('VideoEmbed', () => {
	it('renders iframe with embed URL and start time', async () => {
		const { container } = render(VideoEmbed, {
			props: {
				content: {
					media_id: 'm1',
					print_fallback: 'thumbnail',
					start_time: 30,
					caption: 'Short caption'
				},
				media: {
					m1: {
						id: 'm1',
						type: 'video',
						url: 'https://www.youtube.com/embed/dQw4w9WgXcQ'
					}
				}
			}
		});

		const iframe = container.querySelector('iframe');
		expect(iframe).toBeTruthy();
		const src = iframe?.getAttribute('src') ?? '';
		expect(src).toContain('youtube.com/embed/dQw4w9WgXcQ');
		expect(src).toContain('start=30');
		expect(screen.getAllByText('Short caption').length).toBeGreaterThanOrEqual(1);
	});

	it('shows fallback when media is missing', () => {
		render(VideoEmbed, {
			props: {
				content: {
					media_id: 'missing',
					print_fallback: 'hide'
				},
				media: {}
			}
		});

		expect(screen.getByText(/Video is not available/i)).toBeInTheDocument();
	});
});
