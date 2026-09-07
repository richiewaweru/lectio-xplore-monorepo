/**
 * Capability manifest.
 *
 * Every exported artefact is listed with its version and content hash, so a
 * consumer can tell which catalogue revision it holds and whether the generated
 * views were produced from it. The hash is over the exact bytes written, which
 * is what makes regeneration checkable rather than asserted.
 */

import { createHash } from 'node:crypto';

export interface ManifestEntry {
	file: string;
	view: string;
	view_version: string;
	sha256: string;
	bytes: number;
}

export interface CapabilityManifest {
	manifest_version: string;
	catalogue_version: string;
	package_version: string;
	generated_at: string;
	capability_counts: Record<string, number>;
	artifacts: ManifestEntry[];
}

export const MANIFEST_VERSION = '1.0.0';

export function hashJson(serialized: string): string {
	return createHash('sha256').update(serialized, 'utf8').digest('hex');
}

export function manifestEntry(
	file: string,
	view: string,
	view_version: string,
	serialized: string
): ManifestEntry {
	return {
		file,
		view,
		view_version,
		sha256: hashJson(serialized),
		bytes: Buffer.byteLength(serialized, 'utf8')
	};
}
