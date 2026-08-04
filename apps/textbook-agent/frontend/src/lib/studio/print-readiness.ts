import { tick } from 'svelte';

export type PrintImageWaitResult = {
	image_count: number;
	loaded_count: number;
	failed_count: number;
	timed_out: boolean;
	failed_sources: string[];
};

/**
 * Set loading="eager" on all images so the browser fetches them promptly for PDF capture.
 */
export function forceEagerImages(): void {
	for (const img of document.querySelectorAll('img')) {
		img.loading = 'eager';
	}
}

/**
 * Wait for in-document images to finish loading or decoding (bounded by timeout).
 */
export async function waitForPrintImages(options?: {
	timeoutMs?: number;
}): Promise<PrintImageWaitResult> {
	const timeoutMs = options?.timeoutMs ?? 10_000;
	await tick();

	const images = Array.from(document.images);
	const failedSources: string[] = [];
	let loadedCount = 0;
	let failedCount = 0;

	const waitOne = async (img: HTMLImageElement) => {
		if (img.complete && img.naturalWidth > 0) {
			loadedCount += 1;
			return;
		}
		try {
			if (typeof img.decode === 'function') {
				await img.decode();
				if (img.naturalWidth > 0) {
					loadedCount += 1;
					return;
				}
			}
		} catch {
			// fall through to event wait
		}
		await new Promise<void>((resolve) => {
			const done = (ok: boolean) => {
				if (ok && img.naturalWidth > 0) {
					loadedCount += 1;
				} else {
					failedCount += 1;
					const src = img.currentSrc || img.src;
					if (src) failedSources.push(src);
				}
				resolve();
			};
			img.addEventListener('load', () => done(true), { once: true });
			img.addEventListener('error', () => done(false), { once: true });
		});
	};

	const timeout = new Promise<'timeout'>((resolve) => {
		window.setTimeout(() => resolve('timeout'), timeoutMs);
	});

	const result = await Promise.race([
		Promise.all(images.map(waitOne)).then(() => 'done' as const),
		timeout
	]);

	return {
		image_count: images.length,
		loaded_count: loadedCount,
		failed_count: failedCount,
		timed_out: result === 'timeout',
		failed_sources: failedSources
	};
}
