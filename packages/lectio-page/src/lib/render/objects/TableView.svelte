<script lang="ts">
	import type { TableContent } from '$lib/contract/document';
	import { asRichText, plainText } from '$lib/normalize/inline';
	import InlineView from '../InlineView.svelte';

	let {
		content,
		spanning = false
	}: {
		content: TableContent;
		spanning?: boolean;
	} = $props();
</script>

<table class={['lectio-table', spanning && 'lectio-table--span']}>
	{#if content.caption}
		<caption class="lectio-caption">{content.caption}</caption>
	{/if}
	<thead>
		<tr>
			{#each content.columns as col}
				<th>{col.label}</th>
			{/each}
		</tr>
	</thead>
	<tbody>
		{#each content.rows as row}
			<tr>
				{#each content.columns as col}
					<td>
						{#if typeof row.cells[col.id] === 'string'}
							{plainText(row.cells[col.id])}
						{:else}
							<InlineView nodes={asRichText(row.cells[col.id])} />
						{/if}
					</td>
				{/each}
			</tr>
		{/each}
	</tbody>
</table>
