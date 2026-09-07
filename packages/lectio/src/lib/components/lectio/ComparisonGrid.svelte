<script lang="ts">
	import type { ComparisonGridContent } from '$lib/schema/types';
	import { Badge } from '$lib/components/ui/badge';
	import { Card } from '$lib/components/ui/card';
	import { usePrintMode } from '$lib/utils/printContext';

	let { content }: { content: ComparisonGridContent } = $props();

	const gridTemplate = $derived(
		`grid-template-columns: minmax(9rem, 1.1fr) repeat(${content.columns.length}, minmax(10rem, 1fr));`
	);

	const getPrintMode = usePrintMode();
	const printMode = $derived(getPrintMode());

	function normalizeValues(values: Array<string | { text?: string }>): string[] {
		return values.map((value) => (typeof value === 'string' ? value : value?.text ?? ''));
	}
</script>

<div class="comparison-grid-root">
	{#if printMode}
		<div class="comparison-grid-print rh-gap-component-tight">
			<p class="eyebrow">Comparison</p>
			<h3 class="text-lg font-semibold font-serif">{content.title}</h3>
			{#if content.intro}
				<p class="text-sm leading-6 text-muted-foreground">{content.intro}</p>
			{/if}
			<table class="comparison-grid-print-table w-full border-collapse text-sm" data-print-container="table">
				<thead>
					<tr>
						<th class="comparison-grid-print-th" scope="col">Criterion</th>
						{#each content.columns as column}
							<th class="comparison-grid-print-th" scope="col">{column.title}</th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each content.rows as row}
						<tr>
							<th class="comparison-grid-print-th-row" scope="row">
								{row.criterion}
								{#if row.takeaway}
									<span class="comparison-grid-print-takeaway">{row.takeaway}</span>
								{/if}
							</th>
							{#each normalizeValues(row.values) as value}
								<td class="comparison-grid-print-td">{value}</td>
							{/each}
						</tr>
					{/each}
				</tbody>
			</table>
			{#if content.apply_prompt}
				<p class="text-sm leading-6">
					<strong>Apply it:</strong>
					{content.apply_prompt}
				</p>
			{/if}
		</div>
	{:else}
		<Card class="border-cyan-200 bg-cyan-50/45 rh-pad-card">
			<div class="space-y-5">
				<div class="space-y-2">
					<p class="eyebrow text-cyan-700">Comparison</p>
					<h3 class="text-2xl font-semibold font-serif text-primary">{content.title}</h3>
					{#if content.intro}
						<p class="text-sm leading-6 text-muted-foreground">{content.intro}</p>
					{/if}
				</div>

				<div class="grid rh-gap-cluster lg:grid-cols-2 xl:grid-cols-4">
					{#each content.columns as column}
						<div
							class={`rh-radius-card border bg-white/82 p-4 ${
								column.highlight
									? 'border-cyan-300 shadow-[0_12px_30px_rgba(8,145,178,0.12)]'
									: 'border-cyan-100'
							}`}
						>
							<div class="flex items-center gap-2">
								<p class="text-sm font-semibold uppercase tracking-[0.18em] text-cyan-700">
									{column.title}
								</p>
								{#if column.badge}
									<Badge variant="outline" class="border-cyan-200 text-cyan-700">
										{column.badge}
									</Badge>
								{/if}
							</div>
							<p class="mt-3 text-base leading-7 text-foreground/84">{column.summary}</p>
							{#if column.detail}
								<p class="mt-2 text-sm leading-6 text-muted-foreground">{column.detail}</p>
							{/if}
						</div>
					{/each}
				</div>

				<div class="comparison-grid-table-wrapper overflow-x-auto rh-radius-card border border-cyan-100 bg-white/88">
					<div class="comparison-grid-table min-w-[48rem]">
						<div class="grid items-stretch border-b border-cyan-100 bg-cyan-50/80" style={gridTemplate}>
							<div class="px-4 py-3 text-xs font-semibold uppercase tracking-[0.18em] text-cyan-700">
								Criterion
							</div>
							{#each content.columns as column}
								<div class="px-4 py-3 text-xs font-semibold uppercase tracking-[0.18em] text-cyan-700">
									{column.title}
								</div>
							{/each}
						</div>

						{#each content.rows as row}
							<div class="grid border-t border-cyan-100 first:border-t-0" style={gridTemplate}>
								<div class="px-4 py-4 text-sm font-semibold text-primary">
									{row.criterion}
									{#if row.takeaway}
										<p class="mt-1 text-xs font-normal uppercase tracking-[0.16em] text-muted-foreground">
											{row.takeaway}
										</p>
									{/if}
								</div>
								{#each normalizeValues(row.values) as value}
									<div class="px-4 py-4 text-sm leading-6 text-foreground/82">{value}</div>
								{/each}
							</div>
						{/each}
					</div>
				</div>

				{#if content.apply_prompt}
					<div class="rounded-[1.15rem] bg-cyan-100/70 p-4 text-sm leading-6 text-cyan-950">
						<span class="mr-2 font-semibold uppercase tracking-[0.18em] text-cyan-700">
							Apply it
						</span>
						{content.apply_prompt}
					</div>
				{/if}
			</div>
		</Card>
	{/if}
</div>

<style>
	.comparison-grid-print-takeaway {
		display: block;
		margin-top: 0.25rem;
		font-size: 0.7rem;
		font-weight: 400;
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}

	@media print {
		.comparison-grid-root {
			page-break-inside: auto;
		}

		.comparison-grid-print-table {
			border: 1px solid #d1d5db;
		}

		.comparison-grid-print-th,
		.comparison-grid-print-th-row,
		.comparison-grid-print-td {
			border: 1px solid #d1d5db;
			padding: 0.4rem 0.5rem;
			vertical-align: top;
			text-align: left;
		}

		.comparison-grid-print-th {
			background: #f3f4f6;
			font-size: 0.7rem;
			text-transform: uppercase;
			letter-spacing: 0.06em;
		}

		.comparison-grid-table-wrapper {
			overflow: visible !important;
		}

		.comparison-grid-table {
			min-width: 0 !important;
			width: 100%;
		}
	}
</style>
