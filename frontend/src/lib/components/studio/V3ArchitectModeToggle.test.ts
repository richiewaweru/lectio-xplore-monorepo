// @vitest-environment jsdom

import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

const { authStore } = vi.hoisted(() => {
	let current: {
		id: string;
		email: string;
		name: string | null;
		picture_url: string | null;
		has_profile: boolean;
		created_at: string;
		updated_at: string;
	} | null = null;
	const subscribers = new Set<(value: typeof current) => void>();

	return {
		authStore: {
			subscribe(callback: (value: typeof current) => void) {
				subscribers.add(callback);
				callback(current);
				return () => subscribers.delete(callback);
			},
			set(value: typeof current) {
				current = value;
				for (const callback of subscribers) {
					callback(current);
				}
			}
		}
	};
});

vi.mock('$lib/stores/auth', () => ({
	authUser: authStore
}));

import V3ArchitectModeToggle from './V3ArchitectModeToggle.svelte';

describe('V3ArchitectModeToggle', () => {
	afterEach(() => {
		authStore.set(null);
		vi.restoreAllMocks();
	});

	it('does not render for non-admin email', () => {
		authStore.set({
			id: 'user-1',
			email: 'teacher@school.edu',
			name: 'Teacher',
			picture_url: null,
			has_profile: true,
			created_at: '2026-05-17T00:00:00Z',
			updated_at: '2026-05-17T00:00:00Z'
		});

		render(V3ArchitectModeToggle, {
			props: {
				selected: 'standard',
				onModeChange: vi.fn()
			}
		});

		expect(screen.queryByRole('group', { name: /architect mode/i })).toBeNull();
		expect(screen.queryByText(/chunked/i)).toBeNull();
	});

	it('does not render when authUser is null', () => {
		authStore.set(null);

		render(V3ArchitectModeToggle, {
			props: {
				selected: 'standard',
				onModeChange: vi.fn()
			}
		});

		expect(screen.queryByRole('group', { name: /architect mode/i })).toBeNull();
	});

	it('renders for admin email with group role present', () => {
		authStore.set({
			id: 'admin-1',
			email: 'richie@lectio.app',
			name: 'Admin',
			picture_url: null,
			has_profile: true,
			created_at: '2026-05-17T00:00:00Z',
			updated_at: '2026-05-17T00:00:00Z'
		});

		render(V3ArchitectModeToggle, {
			props: {
				selected: 'standard',
				onModeChange: vi.fn()
			}
		});

		expect(screen.getByRole('group', { name: /architect mode/i })).toBeTruthy();
	});

	it('Standard button has aria-pressed=true when selected=standard', () => {
		authStore.set({
			id: 'admin-1',
			email: 'richie@lectio.app',
			name: 'Admin',
			picture_url: null,
			has_profile: true,
			created_at: '2026-05-17T00:00:00Z',
			updated_at: '2026-05-17T00:00:00Z'
		});

		render(V3ArchitectModeToggle, {
			props: {
				selected: 'standard',
				onModeChange: vi.fn()
			}
		});

		expect(screen.getByRole('button', { name: /standard/i }).getAttribute('aria-pressed')).toBe(
			'true'
		);
		expect(screen.getByRole('button', { name: /chunked/i }).getAttribute('aria-pressed')).toBe(
			'false'
		);
	});

	it('Chunked button has aria-pressed=true when selected=chunked', () => {
		authStore.set({
			id: 'admin-1',
			email: 'richie@lectio.app',
			name: 'Admin',
			picture_url: null,
			has_profile: true,
			created_at: '2026-05-17T00:00:00Z',
			updated_at: '2026-05-17T00:00:00Z'
		});

		render(V3ArchitectModeToggle, {
			props: {
				selected: 'chunked',
				onModeChange: vi.fn()
			}
		});

		expect(screen.getByRole('button', { name: /chunked/i }).getAttribute('aria-pressed')).toBe(
			'true'
		);
		expect(screen.getByRole('button', { name: /standard/i }).getAttribute('aria-pressed')).toBe(
			'false'
		);
	});

	it("clicking Chunked calls onModeChange('chunked') once", async () => {
		authStore.set({
			id: 'admin-1',
			email: 'richie@lectio.app',
			name: 'Admin',
			picture_url: null,
			has_profile: true,
			created_at: '2026-05-17T00:00:00Z',
			updated_at: '2026-05-17T00:00:00Z'
		});
		const onModeChange = vi.fn();

		render(V3ArchitectModeToggle, {
			props: {
				selected: 'standard',
				onModeChange
			}
		});

		await fireEvent.click(screen.getByRole('button', { name: /chunked/i }));

		expect(onModeChange).toHaveBeenCalledOnce();
		expect(onModeChange).toHaveBeenCalledWith('chunked');
	});

	it('clicking already-selected Standard does NOT call onModeChange', async () => {
		authStore.set({
			id: 'admin-1',
			email: 'richie@lectio.app',
			name: 'Admin',
			picture_url: null,
			has_profile: true,
			created_at: '2026-05-17T00:00:00Z',
			updated_at: '2026-05-17T00:00:00Z'
		});
		const onModeChange = vi.fn();

		render(V3ArchitectModeToggle, {
			props: {
				selected: 'standard',
				onModeChange
			}
		});

		await fireEvent.click(screen.getByRole('button', { name: /standard/i }));

		expect(onModeChange).not.toHaveBeenCalled();
	});
});
