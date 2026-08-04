import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig, loadEnv } from 'vite';
import { resolveDevProxyTarget } from './src/lib/config/environment';

const lectioTemplateIds = [
	'compare-and-apply',
	'diagram-led-lesson',
	'distinction-grid',
	'figure-first',
	'focus-flow',
	'formal-track',
	'guided-concept-compact',
	'guided-concept-path',
	'guided-discovery',
	'interactive-lab',
	'process-trainer',
	'timeline-narrative'
] as const;

function normalizePath(id: string): string {
	return id.replace(/\\/g, '/');
}

function resolveLectioTemplateChunk(id: string): string | undefined {
	for (const templateId of lectioTemplateIds) {
		if (
			id.includes(`/node_modules/lectio/dist/templates/${templateId}/`) ||
			id.includes(`/node_modules/lectio/src/lib/templates/${templateId}/`)
		) {
			return `lectio-template-${templateId}`;
		}
	}

	return undefined;
}

function resolveManualChunk(id: string): string | undefined {
	const normalizedId = normalizePath(id);
	const lectioTemplateChunk = resolveLectioTemplateChunk(normalizedId);

	if (lectioTemplateChunk) {
		return lectioTemplateChunk;
	}

	if (
		normalizedId.includes('/node_modules/svelte/') ||
		normalizedId.includes('/node_modules/@sveltejs/')
	) {
		return 'framework-runtime';
	}

	if (normalizedId.includes('/node_modules/katex/')) {
		return 'katex-runtime';
	}

	if (
		normalizedId.includes('/node_modules/bits-ui/') ||
		normalizedId.includes('/node_modules/clsx/') ||
		normalizedId.includes('/node_modules/tailwind-merge/')
	) {
		return 'framework-runtime';
	}

	if (normalizedId.includes('/node_modules/lucide-svelte/')) {
		return 'icon-runtime';
	}

	if (
		normalizedId.includes('/node_modules/lectio/dist/') ||
		normalizedId.includes('/node_modules/lectio/src/lib/')
	) {
		return 'lectio-core';
	}

	return undefined;
}

export default defineConfig(({ mode }) => {
	const apiTarget = resolveDevProxyTarget(loadEnv(mode, '.', ''));
	const isVitest =
		(globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env
			?.VITEST === 'true';

	return {
		plugins: [tailwindcss(), sveltekit()],
		resolve: isVitest
			? {
					conditions: ['browser']
				}
			: undefined,
		server: {
			proxy: {
				'/api': apiTarget,
				'/health': apiTarget
			}
		},
		/*build: {
			rollupOptions: {
				output: {
					manualChunks: resolveManualChunk
				}
			}
		},*/
		test: {
			environment: 'jsdom',
			globals: true,
			/** Threads pool can stall indefinitely on some Windows setups with SvelteKit/Vite. */
			pool: 'forks',
			/** Avoid vitest-worker fetch timeouts when pre-bundling bits-ui (date-time utils) under pnpm. */
			deps: {
				optimizer: {
					web: {
						include: ['bits-ui']
					}
				}
			}
		}
	};
});
