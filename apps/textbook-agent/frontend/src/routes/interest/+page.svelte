<script lang="ts">
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api/client';
	import { ensureOk } from '$lib/api/errors';
	import { PageHeader, EmptyState, InlineError } from '$lib/ui';

	type Row = {
		id: string;
		display_name: string | null;
		email: string | null;
		phone: string | null;
		message: string;
		source: string;
		created_at: string;
	};

	let rows = $state<Row[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	onMount(async () => {
		try {
			const response = await apiFetch('/api/v1/learn/interest?limit=200');
			await ensureOk(response);
			rows = await response.json();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not load messages.';
		} finally {
			loading = false;
		}
	});

	function when(iso: string): string {
		const d = new Date(iso.endsWith('Z') ? iso : `${iso}Z`);
		return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
	}
</script>

<PageHeader title="Interest" description="Notes left by demo visitors, newest first." />

{#if error}
	<InlineError message={error} />
{:else if loading}
	<p class="muted">Loading…</p>
{:else if rows.length === 0}
	<EmptyState title="Nothing yet" description="Messages from the interest form will show up here." />
{:else}
	<div class="scroll">
		<table>
			<thead>
				<tr>
					<th>Date</th>
					<th>Name</th>
					<th>Email</th>
					<th>Phone</th>
					<th>Message</th>
					<th>Source</th>
				</tr>
			</thead>
			<tbody>
				{#each rows as row (row.id)}
					<tr>
						<td>{when(row.created_at)}</td>
						<td>{row.display_name ?? ''}</td>
						<td>{row.email ?? ''}</td>
						<td>{row.phone ?? ''}</td>
						<td class="message">{row.message}</td>
						<td>{row.source}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/if}

<style>
	.muted {
		color: var(--ink-2);
	}
	.scroll {
		overflow-x: auto;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.875rem;
	}
	th,
	td {
		text-align: left;
		vertical-align: top;
		padding: 0.5rem 0.75rem;
		border-bottom: 1px solid var(--rule);
		overflow-wrap: anywhere;
	}
	th {
		color: var(--ink-3);
		font-weight: 500;
	}
	.message {
		min-width: 240px;
		white-space: pre-wrap;
	}
</style>
