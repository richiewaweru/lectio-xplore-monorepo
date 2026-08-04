import DOMPurify from 'dompurify';

export const MAX_RASTER_IMAGE_BYTES = 10 * 1024 * 1024;
export const MAX_SVG_BYTES = 2 * 1024 * 1024;

export const ALLOWED_RASTER_IMAGE_TYPES = [
	'image/png',
	'image/jpeg',
	'image/webp',
	'image/gif'
] as const;
export const ALLOWED_SVG_TYPES = ['image/svg+xml'] as const;

export type VideoParseResult = { provider: 'youtube' | 'vimeo'; embedUrl: string };

/**
 * Normalise YouTube / Vimeo URLs to a stable iframe embed URL.
 */
export function parseVideoUrl(raw: string): VideoParseResult | null {
	const trimmed = raw.trim();
	if (!trimmed) return null;

	let urlString = trimmed;
	if (!/^https?:\/\//i.test(urlString)) {
		urlString = `https://${urlString}`;
	}

	try {
		const u = new URL(urlString);
		const host = u.hostname.replace(/^www\./, '').toLowerCase();

		if (host === 'youtu.be') {
			const id = u.pathname.replace(/^\//, '').split('/')[0];
			if (id && /^[\w-]{6,}$/.test(id)) {
				return { provider: 'youtube', embedUrl: `https://www.youtube.com/embed/${id}` };
			}
			return null;
		}

		if (host === 'youtube.com' || host === 'm.youtube.com' || host === 'music.youtube.com') {
			if (u.pathname.startsWith('/embed/')) {
				return { provider: 'youtube', embedUrl: u.toString() };
			}
			const v = u.searchParams.get('v');
			if (v && /^[\w-]{6,}$/.test(v)) {
				return { provider: 'youtube', embedUrl: `https://www.youtube.com/embed/${v}` };
			}
			return null;
		}

		if (host === 'vimeo.com' || host.endsWith('.vimeo.com')) {
			const parts = u.pathname.split('/').filter(Boolean);
			const id = parts[0];
			if (id && /^\d+$/.test(id)) {
				return { provider: 'vimeo', embedUrl: `https://player.vimeo.com/video/${id}` };
			}
			return null;
		}

		return null;
	} catch {
		return null;
	}
}

export function validateRasterImageFile(
	file: File
): { ok: true } | { ok: false; reason: string } {
	if (!ALLOWED_RASTER_IMAGE_TYPES.includes(file.type as (typeof ALLOWED_RASTER_IMAGE_TYPES)[number])) {
		return { ok: false, reason: 'Use PNG, JPEG, WebP, or GIF.' };
	}
	if (file.size > MAX_RASTER_IMAGE_BYTES) {
		return { ok: false, reason: 'Image must be 10 MB or smaller.' };
	}
	return { ok: true };
}

export function isSvgFile(file: File): boolean {
	return (
		ALLOWED_SVG_TYPES.includes(file.type as (typeof ALLOWED_SVG_TYPES)[number]) ||
		file.name.toLowerCase().endsWith('.svg')
	);
}

export function validateSvgFile(
	file: File
): { ok: true } | { ok: false; reason: string } {
	if (!isSvgFile(file)) {
		return { ok: false, reason: 'File must be an SVG.' };
	}
	if (file.size > MAX_SVG_BYTES) {
		return { ok: false, reason: 'SVG must be 2 MB or smaller.' };
	}
	return { ok: true };
}

export function validateDiagramFile(
	file: File
): { ok: true; kind: 'raster' | 'svg' } | { ok: false; reason: string } {
	if (isSvgFile(file)) {
		const svgResult = validateSvgFile(file);
		if (!svgResult.ok) return svgResult;
		return { ok: true, kind: 'svg' };
	}
	const rasterResult = validateRasterImageFile(file);
	if (!rasterResult.ok) return rasterResult;
	return { ok: true, kind: 'raster' };
}

export function fileToDataUri(file: File): Promise<string> {
	return new Promise((resolve, reject) => {
		const reader = new FileReader();
		reader.onload = () => resolve(reader.result as string);
		reader.onerror = () => reject(reader.error ?? new Error('read failed'));
		reader.readAsDataURL(file);
	});
}

/**
 * Strip executable content from SVG markup before storing.
 */
export function sanitizeSvg(dirty: string): string {
	return DOMPurify.sanitize(dirty, {
		USE_PROFILES: { svg: true, svgFilters: true },
		ADD_TAGS: ['use'],
		ADD_ATTR: ['viewBox', 'preserveAspectRatio', 'xmlns', 'xmlns:xlink', 'fill', 'stroke']
	});
}
