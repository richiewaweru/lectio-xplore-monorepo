<script lang="ts">
	interface Props {
		headers?: string[];
		rows?: string[][];
		caption?: string;
		onChange?: (patch: { headers?: string[]; rows?: string[][]; caption?: string }) => void;
	}

	let {
		headers = $bindable<string[]>(['Column A', 'Column B']),
		rows = $bindable<string[][]>([['', '']]),
		caption = $bindable(''),
		onChange = undefined
	}: Props = $props();

	function setHeader(index: number, value: string) {
		const next = headers.map((h, i) => (i === index ? value : h));
		headers = next;
		onChange?.({ headers: next });
	}

	function setCell(ri: number, ci: number, value: string) {
		const next = rows.map((row, i) =>
			i === ri ? row.map((cell, j) => (j === ci ? value : cell)) : [...row]
		);
		rows = next;
		onChange?.({ rows: next });
	}

	function addRow() {
		const next = [...rows, headers.map(() => '')];
		rows = next;
		onChange?.({ rows: next });
	}

	function removeRow(index: number) {
		if (rows.length <= 1) return;
		const next = rows.filter((_, i) => i !== index);
		rows = next;
		onChange?.({ rows: next });
	}

	function addColumn() {
		const nextHeaders = [...headers, `Column ${headers.length + 1}`];
		const nextRows = rows.map((row) => [...row, '']);
		headers = nextHeaders;
		rows = nextRows;
		onChange?.({ headers: nextHeaders, rows: nextRows });
	}
</script>

<div class="table-editor" data-testid="table-editor">
	<input
		type="text"
		class="caption"
		placeholder="Table caption"
		aria-label="Table caption"
		value={caption}
		oninput={(e) => {
			const next = (e.currentTarget as HTMLInputElement).value;
			caption = next;
			onChange?.({ caption: next });
		}}
	/>
	<div class="grid-wrap">
		<table>
			<thead>
				<tr>
					{#each headers as header, i (i)}
						<th>
							<input
								type="text"
								aria-label={`Header ${i + 1}`}
								value={header}
								oninput={(e) => setHeader(i, (e.currentTarget as HTMLInputElement).value)}
							/>
						</th>
					{/each}
					<th class="actions"></th>
				</tr>
			</thead>
			<tbody>
				{#each rows as row, ri (ri)}
					<tr>
						{#each row as cell, ci (ci)}
							<td>
								<input
									type="text"
									aria-label={`Cell ${ri + 1},${ci + 1}`}
									value={cell}
									oninput={(e) =>
										setCell(ri, ci, (e.currentTarget as HTMLInputElement).value)}
								/>
							</td>
						{/each}
						<td class="actions">
							<button
								type="button"
								aria-label={`Remove row ${ri + 1}`}
								disabled={rows.length <= 1}
								onclick={() => removeRow(ri)}
							>
								×
							</button>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	<div class="toolbar">
		<button type="button" data-testid="table-editor-add-row" onclick={addRow}>Add row</button>
		<button type="button" data-testid="table-editor-add-col" onclick={addColumn}>Add column</button>
	</div>
</div>

<style>
	.table-editor {
		display: grid;
		gap: 8px;
	}
	.caption,
	input {
		box-sizing: border-box;
		width: 100%;
		border: 1px solid var(--rule, #ccc);
		border-radius: 8px;
		background: var(--paper, #fff);
		color: var(--ink, #1a1a1a);
		font: inherit;
		padding: 6px 8px;
	}
	.grid-wrap {
		overflow-x: auto;
	}
	table {
		width: 100%;
		border-collapse: collapse;
	}
	th,
	td {
		border: 1px solid var(--rule, #ccc);
		padding: 4px;
		vertical-align: top;
	}
	.actions {
		width: 36px;
		text-align: center;
	}
	.actions button,
	.toolbar button {
		border: 1px solid var(--rule, #ccc);
		border-radius: 8px;
		background: var(--surface, #f7f7f5);
		cursor: pointer;
		font: inherit;
		padding: 4px 8px;
	}
	.toolbar {
		display: flex;
		gap: 8px;
	}
</style>
