import { describe, expect, it } from 'vitest';

import { ApiError, ensureOk } from './errors';

describe('ensureOk', () => {
	it('uses a friendly concurrency message for 429 responses', async () => {
		const response = new Response('', {
			status: 429,
			statusText: 'Too Many Requests'
		});

		const error = await ensureOk(response, 'Generation failed.').catch((value) => value);

		expect(error).toBeInstanceOf(ApiError);
		expect((error as ApiError).detail).toContain('maximum number of active generations');
	});

	it('formats object-shaped FastAPI detail with debug JSON', async () => {
		const response = new Response(
			JSON.stringify({
				detail: {
					message: 'PDFRenderError: Timed out rendering print view',
					debug: { page_url: 'https://app.example/studio/print/x' }
				}
			}),
			{
				status: 500,
				statusText: 'Internal Server Error',
				headers: { 'content-type': 'application/json' }
			}
		);

		const error = await ensureOk(response, 'Failed to export PDF.').catch((value) => value);

		expect(error).toBeInstanceOf(ApiError);
		const detail = (error as ApiError).detail;
		expect(detail).toContain('PDFRenderError:');
		expect(detail).toContain('Debug:');
		expect(detail).toContain('"page_url"');
		expect(detail).toContain('https://app.example/studio/print/x');
	});
});
