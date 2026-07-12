import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import V3PlanActions from './V3PlanActions.svelte';

describe('V3PlanActions', () => {
	it('calls approve and recovery handlers', async () => {
		const onApprove = vi.fn();
		const onRegenerate = vi.fn();
		const onRecovery = vi.fn();

		render(V3PlanActions, {
			props: {
				onApprove,
				onRegenerate,
				onRecovery
			}
		});

		await fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
		expect(onApprove).toHaveBeenCalledTimes(1);


		await fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
		expect(onApprove).toHaveBeenCalledTimes(2);
	});

	it('renders the teacher-safe recovery action', async () => {
		const onRecovery = vi.fn();
		render(V3PlanActions, {
			props: {
				onApprove: vi.fn(),
				onRegenerate: vi.fn(),
				onRecovery,
				recoveryAction: 'retry_failed_sections'
			}
		});

		expect(screen.getByText("Some sections didn't complete. You can retry them.")).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: 'Retry failed sections' }));
		expect(onRecovery).toHaveBeenCalledTimes(1);
	});
});
