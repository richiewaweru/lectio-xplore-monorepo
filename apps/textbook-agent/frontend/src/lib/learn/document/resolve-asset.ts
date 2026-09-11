/**
 * Resolve a figure asset_id to a displayable URL.
 * asset_id may already be a URL/path, a media map key, or a local/GCS image key.
 */

export type AssetRef = {
	url?: string | null;
	src?: string | null;
};

export function resolveAssetUrl(
	assetId: string | null | undefined,
	assets?: Record<string, AssetRef> | null
): string | null {
	if (!assetId || !String(assetId).trim()) return null;
	const id = String(assetId).trim();

	const mapped = assets?.[id];
	const mappedUrl = mapped?.url || mapped?.src;
	if (typeof mappedUrl === 'string' && mappedUrl.trim()) {
		return mappedUrl.trim();
	}

	if (/^https?:\/\//i.test(id) || id.startsWith('data:') || id.startsWith('blob:')) {
		return id;
	}
	if (id.startsWith('/')) {
		return id;
	}

	// LocalImageStore / static mount: data/images → /images/...
	return `/images/${id.replace(/^\/+/, '')}`;
}
