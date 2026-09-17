<script lang="ts">
	import { goto } from '$app/navigation';
	import { buildApiUrl } from '$lib/api/client';
	import { Button, Card, InlineError } from '$lib/ui';

	let step = $state<'code' | 'name'>('code');
	let inviteCode = $state('');
	let displayName = $state('');
	let className = $state('');
	let error = $state<string | null>(null);
	let busy = $state(false);

	async function continueCode(e: SubmitEvent) {
		e.preventDefault();
		if (!inviteCode.trim()) return;
		step = 'name';
		error = null;
	}

	async function join(e: SubmitEvent) {
		e.preventDefault();
		if (!displayName.trim() || !inviteCode.trim()) return;
		busy = true;
		error = null;
		try {
			const response = await fetch(buildApiUrl('/api/v1/learn/classes/join'), {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					invite_code: inviteCode.trim(),
					display_name: displayName.trim()
				})
			});
			if (!response.ok) {
				const body = await response.json().catch(() => ({}));
				throw new Error(body.detail || 'Could not join class');
			}
			const body = await response.json();
			localStorage.setItem('x-learner-session', body.token);
			className = body.class_name;
			await goto(`/learn/home/${encodeURIComponent(body.learner_id)}`);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not join class';
		} finally {
			busy = false;
		}
	}
</script>

<div class="join">
	<p class="brand">Lect<span>i</span>o</p>
	<Card padding="lg">
		{#if step === 'code'}
			<h1>Join your class</h1>
			<p class="lede">Enter the class code from your teacher.</p>
			{#if error}<InlineError message={error} />{/if}
			<form onsubmit={continueCode}>
				<label>
					<span>Class code</span>
					<input bind:value={inviteCode} required placeholder="ABC123" autocomplete="off" />
				</label>
				<Button type="submit" disabled={!inviteCode.trim()}>Continue</Button>
			</form>
		{:else}
			<h1>Welcome{className ? ` to ${className}` : ''}</h1>
			<p class="lede">What should we call you?</p>
			{#if error}<InlineError message={error} />{/if}
			<form onsubmit={join}>
				<label>
					<span>Your name</span>
					<input bind:value={displayName} required placeholder="Aisha" autocomplete="name" />
				</label>
				<div class="actions">
					<Button variant="secondary" type="button" onclick={() => (step = 'code')}>Back</Button>
					<Button type="submit" busy={busy} disabled={!displayName.trim()}>
						{busy ? 'Joining…' : 'Join class'}
					</Button>
				</div>
			</form>
		{/if}
	</Card>
</div>

<style>
	.join {
		min-height: 100vh;
		display: grid;
		place-items: center;
		padding: 1.5rem;
		background: var(--paper);
	}
	.brand {
		position: absolute;
		top: 1.25rem;
		left: 1.5rem;
		margin: 0;
		font-family: var(--font-serif);
		font-size: 1.35rem;
		font-weight: 600;
	}
	.brand span {
		color: var(--accent);
	}
	h1 {
		margin: 0 0 0.5rem;
		font-family: var(--font-serif);
		font-size: 1.5rem;
	}
	.lede {
		margin: 0 0 1.25rem;
		color: var(--ink-2);
	}
	form {
		display: grid;
		gap: 1rem;
	}
	label {
		display: grid;
		gap: 0.4rem;
		font-size: 0.8125rem;
		font-weight: 600;
		color: var(--ink-2);
	}
	input {
		font: inherit;
		font-weight: 400;
		font-size: 1rem;
		padding: 0.7rem 0.85rem;
		border: 1px solid var(--rule);
		border-radius: var(--radius-md);
	}
	.actions {
		display: flex;
		gap: 0.5rem;
		justify-content: flex-end;
	}
</style>
