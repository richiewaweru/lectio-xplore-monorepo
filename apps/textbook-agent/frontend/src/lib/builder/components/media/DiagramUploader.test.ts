// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { uploadLessonMedia } = vi.hoisted(() => ({
	uploadLessonMedia: vi.fn()
}));

vi.mock('$lib/builder/api/media-upload', () => ({
	uploadLessonMedia
}));

import DiagramUploader from './DiagramUploader.svelte';

describe('DiagramUploader', () => {
	beforeEach(() => {
		uploadLessonMedia.mockReset();
	});

	afterEach(() => {
		cleanup();
	});

	it('uploads raster files and emits onImageReady payload', async () => {
		uploadLessonMedia.mockResolvedValue({
			id: 'media-1',
			type: 'image',
			url: 'https://example.com/image.png',
			mime_type: 'image/png',
			filename: 'uploaded.png'
		});
		const onImageReady = vi.fn();
		const onSvgReady = vi.fn();

		render(DiagramUploader, {
			lessonId: 'lesson-1',
			onImageReady,
			onSvgReady
		});

		const input = screen.getByLabelText('Upload image or SVG') as HTMLInputElement;
		const file = new File(['raster'], 'diagram.png', { type: 'image/png' });
		await fireEvent.change(input, { target: { files: [file] } });

		await waitFor(() => expect(uploadLessonMedia).toHaveBeenCalledWith('lesson-1', file));
		expect(onImageReady).toHaveBeenCalledWith({
			url: 'https://example.com/image.png',
			filename: 'uploaded.png',
			mimeType: 'image/png'
		});
		expect(onSvgReady).not.toHaveBeenCalled();
	});

	it('reads and sanitizes svg files locally and emits onSvgReady', async () => {
		const onImageReady = vi.fn();
		const onSvgReady = vi.fn();

		render(DiagramUploader, {
			lessonId: 'lesson-1',
			onImageReady,
			onSvgReady
		});

		const input = screen.getByLabelText('Upload image or SVG') as HTMLInputElement;
		const file = new File(
			['<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script><rect width="1" height="1"/></svg>'],
			'diagram.svg',
			{ type: 'image/svg+xml' }
		);
		await fireEvent.change(input, { target: { files: [file] } });

		await waitFor(() => expect(onSvgReady).toHaveBeenCalledTimes(1));
		const svg = onSvgReady.mock.calls[0]?.[0] as string;
		expect(svg).toContain('<svg');
		expect(svg).not.toContain('<script');
		expect(uploadLessonMedia).not.toHaveBeenCalled();
		expect(onImageReady).not.toHaveBeenCalled();
	});
});
