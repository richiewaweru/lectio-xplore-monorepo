import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

import adapter from '@sveltejs/adapter-vercel';

function copyRecursiveSync(source, destination) {
	const stats = fs.lstatSync(source);
	if (stats.isDirectory()) {
		fs.mkdirSync(destination, { recursive: true });
		for (const entry of fs.readdirSync(source)) {
			copyRecursiveSync(path.join(source, entry), path.join(destination, entry));
		}
		return;
	}

	fs.mkdirSync(path.dirname(destination), { recursive: true });
	fs.copyFileSync(source, destination);
}

function resolveSymlinkSource(target, destination) {
	return path.resolve(path.dirname(destination), target);
}

function resolveExistingSource(target, destination) {
	const directSource = resolveSymlinkSource(target, destination);
	if (fs.existsSync(directSource)) {
		return directSource;
	}

	const nodeModulesMarker = `${path.sep}node_modules`;
	const nodeModulesIndex = String(destination).indexOf(nodeModulesMarker);
	if (nodeModulesIndex >= 0) {
		const bundleNodeModulesRoot = String(destination).slice(
			0,
			nodeModulesIndex + nodeModulesMarker.length
		);
		const relativeWithinNodeModules = path.relative(bundleNodeModulesRoot, directSource);
		const fromProjectBundle = path.join(
			process.cwd(),
			'node_modules',
			relativeWithinNodeModules
		);
		if (fs.existsSync(fromProjectBundle)) {
			return fromProjectBundle;
		}
	}

	const fromProjectNodeModules = path.resolve(process.cwd(), 'node_modules', target);
	if (fs.existsSync(fromProjectNodeModules)) {
		return fromProjectNodeModules;
	}

	return directSource;
}

export default function safeAdapter(options = {}) {
	const base = adapter(options);
	const adapt = base.adapt;

	return {
		...base,
		async adapt(builder) {
			if (process.platform !== 'win32') {
				await adapt(builder);
				return;
			}

			const originalSymlinkSync = fs.symlinkSync.bind(fs);

			fs.symlinkSync = (target, destination, type) => {
				try {
					return originalSymlinkSync(target, destination, type);
				} catch (error) {
					if (!(error instanceof Error) || !('code' in error) || error.code !== 'EPERM') {
						throw error;
					}

					const resolvedSource = resolveExistingSource(String(target), String(destination));
					if (!fs.existsSync(resolvedSource)) {
						throw error;
					}

					const sourceStats = fs.lstatSync(resolvedSource);
					fs.mkdirSync(path.dirname(String(destination)), { recursive: true });

					if (sourceStats.isDirectory()) {
						try {
							return originalSymlinkSync(target, destination, 'junction');
						} catch {
							copyRecursiveSync(resolvedSource, String(destination));
							return;
						}
					}

					fs.copyFileSync(resolvedSource, String(destination));
				}
			};

			try {
				await adapt(builder);
			} finally {
				fs.symlinkSync = originalSymlinkSync;
			}
		}
	};
}
