import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = resolve(HERE, '..', '..');
const PACKAGE_JSON_PATH = resolve(FRONTEND_ROOT, 'package.json');
const PACKAGE_LOCK_PATH = resolve(FRONTEND_ROOT, 'package-lock.json');
const PNPM_LOCK_PATH = resolve(FRONTEND_ROOT, 'pnpm-lock.yaml');

describe('lectio lockfile sync', () => {
	it('keeps package.json, package-lock.json, and pnpm-lock.yaml on the same lectio version', () => {
		const packageJson = JSON.parse(readFileSync(PACKAGE_JSON_PATH, 'utf8')) as {
			dependencies?: Record<string, string>;
		};
		const packageLock = JSON.parse(readFileSync(PACKAGE_LOCK_PATH, 'utf8')) as {
			packages?: Record<string, { dependencies?: Record<string, string>; version?: string }>;
		};
		const pnpmLock = readFileSync(PNPM_LOCK_PATH, 'utf8');

		const packageVersion = packageJson.dependencies?.lectio;
		const normalizedPackageVersion = packageVersion?.replace(/^[~^]/, '');
		const lockRootVersion = packageLock.packages?.['']?.dependencies?.lectio;
		const lockInstalledVersion = packageLock.packages?.['node_modules/lectio']?.version;
		const pnpmMatch = pnpmLock.match(
			/^\s+lectio:\n\s+specifier:\s*([^\n]+)\n\s+version:\s*([^\n]+)\n/m
		);
		const pnpmSpecifier = pnpmMatch?.[1];
		const pnpmVersion = pnpmMatch?.[2];

		expect(packageVersion).toBeTruthy();
		expect(lockRootVersion).toBeTruthy();
		expect(lockInstalledVersion).toBeTruthy();
		expect(pnpmSpecifier).toBeTruthy();
		expect(pnpmVersion).toBeTruthy();
		expect(lockRootVersion).toBe(packageVersion);
		expect(lockInstalledVersion).toBe(normalizedPackageVersion);
		expect(pnpmSpecifier).toBe(packageVersion);
		expect(pnpmVersion?.startsWith(`${normalizedPackageVersion}(`)).toBe(true);
	});
});
