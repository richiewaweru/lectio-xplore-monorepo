import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

const isVitest = process.env.VITEST === 'true';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	resolve: isVitest
		? {
				conditions: ['browser']
			}
		: undefined,
	test: {
		environment: 'jsdom',
		globals: true,
		setupFiles: ['src/test/setup.ts'],
		exclude: ['.claude/**', 'node_modules/**', 'dist/**', '.svelte-kit/**']
	}
});
