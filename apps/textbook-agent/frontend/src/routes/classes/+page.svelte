<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { apiFetch } from '$lib/api/client';
	import { ensureOk } from '$lib/api/errors';
	import { PageHeader, Card, Button, EmptyState, InlineError, Dialog, Badge } from '$lib/ui';

	let classes = $state<Array<{ id: string; name: string; invite_code: string }>>([]);
	let name = $state('');
	let error = $state<string | null>(null);
	let createOpen = $state(false);
	let busy = $state(false);

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
		if (!name.trim()) return;
		busy = true;
		error = null;
		try {
			const response = await apiFetch('/api/v1/learn/classes', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ name: name.trim() })
			});
			await ensureOk(response);
			name = '';
			createOpen = false;
			await refresh();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not create class';
		} finally {
			busy = false;
		}
	}
</script>

<PageHeader title="Classes" description="Roster containers for assigning Learn lessons and seeing progress.">
	{#snippet actions()}
		<Button onclick={() => (createOpen = true)}>+ New class</Button>
	{/snippet}
</PageHeader>

{#if error}
	<InlineError message={error} />
{/if}

{#if classes.length === 0}
	<EmptyState
		title="No classes yet"
		description="Create a class, share the invite code with students at /join, then assign published lessons."
	>
		{#snippet actions()}
			<Button onclick={() => (createOpen = true)}>Create class</Button>
		{/snippet}
	</EmptyState>
{:else}
	<div class="grid">
		{#each classes as row}
			<Card href={`/classes/${row.id}`} padding="md">
				<div class="row">
					<h2>{row.name}</h2>
					<Badge tone="neutral">Invite {row.invite_code}</Badge>
				</div>
				<p>Open overview, students, assignments, and insights.</p>
			</Card>
		{/each}
	</div>
{/if}

<Dialog bind:open={createOpen} title="Create class" description="Students join with the invite code.">
	<label class="field">
		<span>Class name</span>
		<input bind:value={name} placeholder="Year 8 Science" />
	</label>
	{#snippet footer()}
		<Button variant="secondary" onclick={() => (createOpen = false)}>Cancel</Button>
		<Button busy={busy} disabled={!name.trim()} onclick={() => void createClass()}>Create</Button>
	{/snippet}
</Dialog>

<style>
	.grid {
		display: grid;
		gap: var(--space-4);
		grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
	}
	.row {
		display: flex;
		justify-content: space-between;
		gap: 0.75rem;
		align-items: flex-start;
	}
	h2 {
		margin: 0;
		font-size: 1.05rem;
	}
	p {
		margin: 0.4rem 0 0;
		color: var(--ink-2);
		font-size: 0.875rem;
	}
	.field {
		display: grid;
		gap: 0.4rem;
		font-size: 0.8125rem;
		font-weight: 600;
		color: var(--ink-2);
	}
	input {
		font: inherit;
		font-weight: 400;
		padding: 0.55rem 0.7rem;
		border: 1px solid var(--rule);
		border-radius: var(--radius-md);
	}
</style>
