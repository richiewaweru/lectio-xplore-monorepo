<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { buildApiUrl } from '$lib/api/client';
	import { Button, Card, InlineError } from '$lib/ui';
	import {
		getStoredLearner,
		learnerFetch,
		storeLearner,
		type StoredLearner
	} from '$lib/learn/student/api/learner-fetch';
	import { resumeWithCode } from '$lib/learn/student/api/resume';

	let { code = '' }: { code?: string } = $props();

	// Code is fixed when it arrives via the link; otherwise the student types it.
	const linkCode = $derived(code.trim());
	let typedCode = $state('');
	let step = $state<'code' | 'name' | 'done'>('code');
	let joined = $state<{ learnerId: string; displayName: string; code: string } | null>(null);
	let copied = $state(false);
	let resumeCode = $state('');
	let resumeBusy = $state(false);
	let resumeError = $state<string | null>(null);
	let continueBusy = $state(false);
	let continueError = $state<string | null>(null);
	let displayName = $state('');
	let error = $state<string | null>(null);
	let busy = $state(false);
	let returning = $state<StoredLearner | null>(null);

	const inviteCode = $derived(linkCode || typedCode.trim());

	$effect(() => {
		if (linkCode) step = 'name';
	});

	onMount(() => {
		returning = getStoredLearner();
	});

	function continueCode(e: SubmitEvent) {
		e.preventDefault();
		if (!typedCode.trim()) return;
		step = 'name';
		error = null;
	}

	async function continueAsReturning() {
		if (!returning) return;
		continueError = null;
		// Same device: attach this stored learner to the class (no new identity).
		if (linkCode) {
			continueBusy = true;
			try {
				const response = await learnerFetch('/api/v1/learn/classes/join-existing', {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ invite_code: linkCode })
				});
				if (!response.ok) {
					const body = await response.json().catch(() => ({}));
					throw new Error(
						typeof body.detail === 'string' ? body.detail : 'Could not join class. Try again.'
					);
				}
			} catch (err) {
				continueError = err instanceof Error ? err.message : 'Could not join class. Try again.';
				continueBusy = false;
				return;
			}
			continueBusy = false;
		}
		await goto(`/learn/home/${encodeURIComponent(returning.learnerId)}`);
	}

	async function useCode(e: SubmitEvent) {
		e.preventDefault();
		if (!resumeCode.trim()) return;
		resumeBusy = true;
		resumeError = null;
		try {
			const learnerId = await resumeWithCode(resumeCode);
			await goto(`/learn/home/${encodeURIComponent(learnerId)}`);
		} catch (err) {
			resumeError = err instanceof Error ? err.message : 'Something went wrong. Try again.';
		} finally {
			resumeBusy = false;
		}
	}

	async function copyCode() {
		if (!joined) return;
		try {
			await navigator.clipboard.writeText(joined.code);
			copied = true;
		} catch {
			copied = false;
		}
	}

	async function join(e: SubmitEvent) {
		e.preventDefault();
		if (!displayName.trim() || !inviteCode) return;
		busy = true;
		error = null;
		try {
			const response = await fetch(buildApiUrl('/api/v1/learn/classes/join'), {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ invite_code: inviteCode, display_name: displayName.trim() })
			});
			if (!response.ok) {
				const body = await response.json().catch(() => ({}));
				throw new Error(
					typeof body.detail === 'string' ? body.detail : 'Could not join class. Check the code and try again.'
				);
			}
			const body = await response.json();
			// Joining from the form creates a new learner. Same-device returners use
			// join-existing instead (see continueAsReturning).
			storeLearner({
				token: body.token,
				learnerId: body.learner_id,
				displayName: body.display_name,
				code: body.code
			});
			joined = { learnerId: body.learner_id, displayName: body.display_name, code: body.code ?? '' };
			step = 'done';
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
		{#if step === 'done' && joined}
			<h1>Welcome, {joined.displayName}</h1>
			{#if joined.code}
				<p class="lede">Your code</p>
				<div class="codebox">
					<strong class="code" data-testid="learner-code">{joined.code}</strong>
					<Button variant="secondary" type="button" onclick={copyCode}>{copied ? 'Copied' : 'Copy'}</Button>
				</div>
				<p class="lede">Save this. It gets your progress back on any device.</p>
				<p class="bookmark">
					Bookmark:
					<a href={`${location.origin}/resume/${encodeURIComponent(joined.code)}`}>
						{location.origin}/resume/{joined.code}
					</a>
				</p>
			{/if}
			<Button onclick={() => goto(`/learn/home/${encodeURIComponent(joined!.learnerId)}`)}>
				Start learning →
			</Button>
		{:else}
		{#if returning}
			<div class="returning">
				<p class="lede">
					Welcome back{returning.displayName ? `, ${returning.displayName}` : ''}.
				</p>
				<Button onclick={continueAsReturning} busy={continueBusy}>
					Continue{returning.displayName ? ` as ${returning.displayName}` : ''}
				</Button>
				{#if continueError}<InlineError message={continueError} />{/if}
				<Button variant="secondary" type="button" onclick={() => (returning = null)}>
					Not you? Join as someone else
				</Button>
			</div>
		{/if}
		{#if step === 'code'}
			<h1>Join your class</h1>
			<p class="lede">Enter the class code from your teacher.</p>
			{#if error}<InlineError message={error} />{/if}
			<form onsubmit={continueCode}>
				<label>
					<span>Class code</span>
					<input bind:value={typedCode} required placeholder="ABC123" autocomplete="off" />
				</label>
				<Button type="submit" disabled={!typedCode.trim()}>Continue</Button>
			</form>
			<p class="or">or</p>
			<form onsubmit={useCode}>
				<label>
					<span>Have a code?</span>
					<input bind:value={resumeCode} placeholder="HAPPY-TIGER-4821" autocomplete="off" />
				</label>
				{#if resumeError}<InlineError message={resumeError} />{/if}
				<Button type="submit" variant="secondary" busy={resumeBusy} disabled={!resumeCode.trim()}>
					Continue
				</Button>
			</form>
		{:else}
			<h1>Join your class</h1>
			<p class="lede">Class code <strong class="code">{inviteCode}</strong>. What should we call you?</p>
			{#if error}<InlineError message={error} />{/if}
			<form onsubmit={join}>
				<label>
					<span>Your name</span>
					<input bind:value={displayName} required placeholder="Aisha" autocomplete="name" />
				</label>
				<div class="actions">
					{#if !linkCode}
						<Button variant="secondary" type="button" onclick={() => (step = 'code')}>Back</Button>
					{/if}
					<Button type="submit" busy={busy} disabled={!displayName.trim()}>
						{busy ? 'Joining…' : 'Join class'}
					</Button>
				</div>
			</form>
		{/if}
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
	.code {
		font-family: var(--font-mono, monospace);
		color: var(--ink);
	}
	.returning {
		display: grid;
		gap: 0.5rem;
		margin-bottom: 1.25rem;
		padding-bottom: 1.25rem;
		border-bottom: 1px solid var(--rule);
	}
	.returning .lede {
		margin: 0;
	}
	.codebox {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		margin-bottom: 1rem;
		padding: 0.75rem 1rem;
		border: 1px solid var(--rule);
		border-radius: var(--radius-md);
		font-size: 1.25rem;
	}
	.bookmark {
		margin: 0 0 1.25rem;
		font-size: 0.8125rem;
		overflow-wrap: anywhere;
	}
	.or {
		margin: 0.25rem 0 0;
		font-size: 0.8125rem;
		color: var(--ink-3);
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
