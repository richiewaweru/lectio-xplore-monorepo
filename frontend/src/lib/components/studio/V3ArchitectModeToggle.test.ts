import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import { logout, setAuth } from '$lib/stores/auth';
import V3ArchitectModeToggle from './V3ArchitectModeToggle.svelte';

describe('V3ArchitectModeToggle', () => {
	it('stays hidden for non-admin users', () => {
		logout();
		render(V3ArchitectModeToggle, {
			props: {
				value: 'standard',
				onChange: vi.fn()
			}
		});

		expect(screen.queryByRole('button', { name: 'Standard' })).toBeNull();
		expect(screen.queryByRole('button', { name: 'Chunked' })).toBeNull();
	});

	it('renders standard and chunked options and supports switching', async () => {
		setAuth({
			access_token: 'token',
			token_type: 'bearer',
			user: {
				id: 'admin-1',
				email: 'admin@lectio.app',
				name: 'Admin',
				picture_url: null,
				has_profile: true,
				created_at: '2026-05-17T00:00:00Z',
				updated_at: '2026-05-17T00:00:00Z'
			}
		});
		const onChange = vi.fn();
		render(V3ArchitectModeToggle, {
			props: {
				value: 'chunked',
				onChange
			}
		});

		const standard = screen.getByRole('button', { name: 'Standard' });
		const chunked = screen.getByRole('button', { name: 'Chunked' });

		expect(standard).toBeTruthy();
		expect(chunked).toBeTruthy();
		expect(chunked.getAttribute('aria-pressed')).toBe('true');
		expect(standard.getAttribute('aria-pressed')).toBe('false');

		await fireEvent.click(standard);
		expect(onChange).toHaveBeenCalledWith('standard');
		logout();
	});
});
