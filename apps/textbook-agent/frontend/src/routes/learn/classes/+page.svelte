<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { apiFetch } from '$lib/api/client';
	import { ensureOk } from '$lib/api/errors';

	let classes = $state<Array<{ id: string; name: string; invite_code: string }>>([]);
	let name = $state('');
	let error = $state<string | null>(null);

	async function refresh() {
		const response = await apiFetch('/api/v1/learn/classes');
		await ensureOk(response);
		classes = await response.json();
	}

	onMount(async () => {
		if (!browser) return;
		try {
			await refresh();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load classes';
		}
	});

	async function createClass() {
		error = null;
		const response = await apiFetch('/api/v1/learn/classes', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ name })
		});
		await ensureOk(response);
		name = '';
		await refresh();
	}
</script>

<main class="classes-page">
	<p class="eyebrow">Classes</p>
	<h1>Your classes</h1>
	{#if error}
		<p class="error">{error}</p>
	{/if}
	<form
		onsubmit={(e) => {
			e.preventDefault();
			void createClass();
		}}
	>
		<label>
			Class name
			<input bind:value={name} required placeholder="Period 1" />
		</label>
		<button type="submit" class="primary">Create class</button>
	</form>
	<ul>
		{#each classes as row}
			<li>
				<a href={`/learn/classes/${row.id}`}>
					<strong>{row.name}</strong>
					<span>Invite {row.invite_code}</span>
				</a>
			</li>
		{:else}
			<li class="empty">No classes yet.</li>
		{/each}
	</ul>
</main>

<style>
	.classes-page {
		max-width: 720px;
		margin: 0 auto;
		padding: 28px 18px 48px;
		background: var(--paper);
		color: var(--ink);
		min-height: 100vh;
	}
	.eyebrow {
		margin: 0 0 6px;
		color: var(--ink-3);
		font: 500 11px 'IBM Plex Mono', monospace;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}
	h1 {
		margin: 0 0 18px;
		font: 500 34px/1.1 Fraunces, Georgia, serif;
	}
	form {
		display: grid;
		gap: 10px;
		margin-bottom: 18px;
	}
	label {
		display: grid;
		gap: 6px;
		font-size: 12px;
		font-weight: 600;
		color: var(--ink-2);
	}
	input {
		border: 1px solid var(--rule);
		border-radius: 8px;
		background: var(--surface);
		padding: 10px 12px;
		color: var(--ink);
	}
	.primary {
		justify-self: start;
		border: 1px solid var(--accent);
		border-radius: 8px;
		background: var(--accent);
		color: white;
		padding: 9px 12px;
		font-weight: 600;
	}
	ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 8px;
	}
	a {
		display: grid;
		gap: 4px;
		border: 1px solid var(--rule);
		border-radius: 12px;
		background: var(--surface);
		padding: 12px 14px;
		text-decoration: none;
		color: inherit;
	}
	span,
	.empty,
	.error {
		color: var(--ink-3);
		font-size: 13px;
	}
	.error {
		color: var(--amber, #b45309);
	}
</style>
