<script lang="ts">
	import type { TableNode } from '../types';

	interface Props {
		node: TableNode;
	}

	let { node }: Props = $props();

	const headers = $derived(node.headers ?? []);
	const rows = $derived(node.rows ?? []);
</script>

<figure class="learn-table-wrap" data-testid="table-node" data-node-id={node.id}>
	<table class="learn-table">
		{#if headers.length > 0}
			<thead>
				<tr>
					{#each headers as header, i (i)}
						<th>{header}</th>
					{/each}
				</tr>
			</thead>
		{/if}
		<tbody>
			{#each rows as row, ri (ri)}
				<tr>
					{#each row as cell, ci (ci)}
						<td>{cell}</td>
					{/each}
				</tr>
			{/each}
		</tbody>
	</table>
	{#if node.caption}
		<figcaption>{node.caption}</figcaption>
	{/if}
</figure>

<style>
	.learn-table-wrap {
		margin: 0;
		overflow-x: auto;
	}
	.learn-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 14px;
		color: var(--ink, #1a1a1a);
	}
	.learn-table th,
	.learn-table td {
		border: 1px solid var(--rule, #ccc);
		padding: 8px 10px;
		text-align: left;
		vertical-align: top;
	}
	.learn-table th {
		background: var(--surface, #f7f7f5);
		font-weight: 600;
	}
	figcaption {
		margin-top: 8px;
		font-size: 13px;
		color: var(--ink-2, #444);
	}
</style>
