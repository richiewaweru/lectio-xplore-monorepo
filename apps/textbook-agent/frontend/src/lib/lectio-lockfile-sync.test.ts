import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = resolve(HERE, '..', '..');
const REPO_ROOT = resolve(FRONTEND_ROOT, '..', '..', '..');
const PACKAGE_JSON_PATH = resolve(FRONTEND_ROOT, 'package.json');
const PACKAGE_LOCK_PATH = resolve(FRONTEND_ROOT, 'package-lock.json');
const FRONTEND_PNPM_LOCK_PATH = resolve(FRONTEND_ROOT, 'pnpm-lock.yaml');
const ROOT_PNPM_LOCK_PATH = resolve(REPO_ROOT, 'pnpm-lock.yaml');

const LEARN_PACKAGE = '@lectio/learn';

describe('@lectio/learn lockfile sync', () => {
	it('keeps package.json and lockfiles on the same @lectio/learn workspace specifier', () => {
		const packageJson = JSON.parse(readFileSync(PACKAGE_JSON_PATH, 'utf8')) as {
			dependencies?: Record<string, string>;
		};
		const packageLock = JSON.parse(readFileSync(PACKAGE_LOCK_PATH, 'utf8')) as {
			packages?: Record<string, { dependencies?: Record<string, string>; version?: string; link?: boolean }>;
		};
		const frontendPnpmLock = readFileSync(FRONTEND_PNPM_LOCK_PATH, 'utf8');
		const rootPnpmLock = readFileSync(ROOT_PNPM_LOCK_PATH, 'utf8');

		const packageVersion = packageJson.dependencies?.[LEARN_PACKAGE];
		const lockRootVersion = packageLock.packages?.['']?.dependencies?.[LEARN_PACKAGE];
		const lockInstalled = packageLock.packages?.[`node_modules/${LEARN_PACKAGE}`];

		const rootPnpmNormalized = rootPnpmLock.replace(/\r\n/g, '\n');
		const frontendPnpmNormalized = frontendPnpmLock.replace(/\r\n/g, '\n');
		const frontendPnpmMatch = frontendPnpmNormalized.match(
			/'@lectio\/learn':\n\s+specifier:\s*([^\n]+)\n\s+version:\s*([^\n]+)/
		);
		const importerHeader = /\n  (?:\.|[A-Za-z0-9@._/-]+):\n/g;
		const headers: number[] = [];
		for (const match of rootPnpmNormalized.matchAll(importerHeader)) {
			headers.push(match.index ?? -1);
		}
		const frontendImporterStart = headers.find(
			(index) => rootPnpmNormalized.slice(index, index + 80).includes('apps/textbook-agent/frontend:')
		);
		const frontendImporterIndex = headers.indexOf(frontendImporterStart ?? -1);
		const nextImporterStart =
			frontendImporterIndex >= 0 ? headers[frontendImporterIndex + 1] : undefined;
		const frontendImporter =
			frontendImporterStart != null && frontendImporterStart >= 0
				? rootPnpmNormalized.slice(frontendImporterStart, nextImporterStart)
				: '';
		const rootImporterMatch = frontendImporter.match(
			/'@lectio\/learn':\n\s+specifier:\s*([^\n]+)\n\s+version:\s*([^\n]+)/
		);

		expect(packageVersion).toBe('workspace:*');
		expect(lockRootVersion).toBe('workspace:*');
		expect(lockInstalled?.link ?? lockInstalled?.version).toBeTruthy();
		expect(frontendPnpmMatch?.[1]).toBe('workspace:*');
		expect(frontendPnpmMatch?.[2]).toMatch(/^link:/);
		expect(rootImporterMatch?.[1]).toBe('workspace:*');
		expect(rootImporterMatch?.[2]).toMatch(/^link:/);
		expect(packageJson.dependencies?.lectio).toBeUndefined();
		expect(packageLock.packages?.['']?.dependencies?.lectio).toBeUndefined();
	});
});
