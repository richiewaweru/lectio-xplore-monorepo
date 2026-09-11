<script lang="ts">
	import { apiFetch } from '$lib/api/client';
	import { downloadV3GenerationPdf } from '$lib/api/v3';
	import type { LectioDocument } from '@lectio/page/contract';

	let {
		generationId,
		token = null,
		document: initialDocument,
		documentRevision = 0,
		onDocumentChange
	}: {
		generationId: string;
		token?: string | null;
		document: LectioDocument;
		documentRevision?: number;
		onDocumentChange?: (document: LectioDocument) => void;
	} = $props();

	function cloneDocument(doc: LectioDocument): LectioDocument {
		return JSON.parse(JSON.stringify(doc)) as LectioDocument;
	}

	let mode = $state<'view' | 'edit'>('view');
	let draft = $state<LectioDocument>(cloneDocument(initialDocument));
	let revision = $state(documentRevision);
	let status = $state('');
	let saving = $state(false);
	let pdfBusy = $state(false);

	$effect(() => {
		draft = cloneDocument(initialDocument);
		revision = documentRevision;
	});

	function authHeaders(): Record<string, string> {
		const headers: Record<string, string> = { 'Content-Type': 'application/json' };
		if (token) headers.Authorization = `Bearer ${token}`;
		return headers;
	}

	function asPlain(value: unknown): string {
		if (typeof value === 'string') return value;
		if (Array.isArray(value)) return value.map(asPlain).join('');
		if (value && typeof value === 'object') {
			const rec = value as Record<string, unknown>;
			if (typeof rec.value === 'string') return rec.value;
			if (Array.isArray(rec.children)) return asPlain(rec.children);
		}
		return '';
	}

	function setProse(sectionIndex: number, blockIndex: number, text: string) {
		const paragraphs = text
			.split(/\n\s*\n/)
			.map((part) => part.trim())
			.filter(Boolean)
			.map((part) => ({ children: [{ type: 'text' as const, value: part }] }));
		const next = cloneDocument(draft);
		(next.sections[sectionIndex].blocks[blockIndex].content as { paragraphs: unknown[] }).paragraphs =
			paragraphs;
		draft = next;
	}

	function setListItems(sectionIndex: number, blockIndex: number, text: string) {
		const items = text
			.split('\n')
			.map((line) => line.trim())
			.filter(Boolean)
			.map((line) => ({ text: line }));
		const next = cloneDocument(draft);
		(next.sections[sectionIndex].blocks[blockIndex].content as { items: unknown[] }).items = items;
		draft = next;
	}

	function setAsideBody(sectionIndex: number, blockIndex: number, text: string) {
		const next = cloneDocument(draft);
		(next.sections[sectionIndex].blocks[blockIndex].content as { body: string }).body = text;
		draft = next;
	}

	function setFigureField(
		sectionIndex: number,
		blockIndex: number,
		field: 'caption' | 'alt_text' | 'src',
		value: string
	) {
		const next = cloneDocument(draft);
		const content = next.sections[sectionIndex].blocks[blockIndex].content as {
			caption?: string | null;
			alt_text?: string;
			asset?: { src?: string };
		};
		if (field === 'src') {
			content.asset = { ...(content.asset || {}), src: value };
		} else if (field === 'caption') {
			content.caption = value;
		} else {
			content.alt_text = value;
		}
		draft = next;
	}

	function setTableCell(
		sectionIndex: number,
		blockIndex: number,
		rowIndex: number,
		columnId: string,
		value: string
	) {
		const next = cloneDocument(draft);
		const content = next.sections[sectionIndex].blocks[blockIndex].content as {
			rows: Array<{ cells: Record<string, string> }>;
		};
		content.rows[rowIndex].cells[columnId] = value;
		draft = next;
	}

	function setQuestionPrompt(sectionIndex: number, blockIndex: number, itemIndex: number, value: string) {
		const next = cloneDocument(draft);
		const content = next.sections[sectionIndex].blocks[blockIndex].content as {
			items: Array<{ prompt: string }>;
		};
		content.items[itemIndex].prompt = value;
		draft = next;
	}

	function setChoiceOption(
		sectionIndex: number,
		blockIndex: number,
		optionIndex: number,
		value: string
	) {
		const next = cloneDocument(draft);
		const content = next.sections[sectionIndex].blocks[blockIndex].content as {
			options: Array<{ text: string }>;
		};
		content.options[optionIndex].text = value;
		draft = next;
	}

	function setHeadingText(sectionIndex: number, blockIndex: number, value: string) {
		const next = cloneDocument(draft);
		(next.sections[sectionIndex].blocks[blockIndex].content as { text: string }).text = value;
		draft = next;
	}

	async function save() {
		saving = true;
		status = '';
		try {
			const res = await apiFetch(
				`/api/v1/v3/generations/${encodeURIComponent(generationId)}/lectio-document`,
				{
					method: 'PUT',
					headers: authHeaders(),
					body: JSON.stringify({
						expected_document_revision: revision,
						document: draft
					})
				}
			);
			if (res.status === 409) {
				status = 'Save rejected: stale document revision (409). Reload and retry.';
				return;
			}
			if (!res.ok) {
				const body = await res.text();
				status = `Save failed (${res.status}): ${body.slice(0, 240)}`;
				return;
			}
			const payload = (await res.json()) as { document_revision: number; document: LectioDocument };
			revision = payload.document_revision;
			draft = payload.document;
			onDocumentChange?.(payload.document);
			status = `Saved revision ${revision}`;
		} catch (err) {
			status = err instanceof Error ? err.message : 'Save failed';
		} finally {
			saving = false;
		}
	}

	async function reload() {
		status = '';
		const res = await apiFetch(
			`/api/v1/v3/generations/${encodeURIComponent(generationId)}/lectio-document`,
			{ headers: authHeaders() }
		);
		if (!res.ok) {
			status = `Reload failed (${res.status})`;
			return;
		}
		const payload = (await res.json()) as { document_revision: number; document: LectioDocument };
		revision = payload.document_revision;
		draft = payload.document;
		onDocumentChange?.(payload.document);
		status = `Reloaded revision ${revision}`;
	}

	async function exportPdf() {
		pdfBusy = true;
		status = '';
		try {
			await downloadV3GenerationPdf(generationId, {
				school_name: 'Lectio closeout',
				teacher_name: 'Studio',
				include_toc: false,
				include_answers: true,
				edition: 'teacher'
			});
			status = 'PDF export started';
		} catch (err) {
			status = err instanceof Error ? err.message : 'PDF export failed';
		} finally {
			pdfBusy = false;
		}
	}
</script>

<div class="print-editor" data-testid="print-document-editor" data-mode={mode} data-revision={revision}>
	<div class="toolbar">
		<button type="button" class:active={mode === 'view'} onclick={() => (mode = 'view')}>View</button>
		<button
			type="button"
			class:active={mode === 'edit'}
			data-testid="print-edit-toggle"
			onclick={() => (mode = 'edit')}
		>
			Edit
		</button>
		<button type="button" data-testid="print-save" disabled={saving || mode !== 'edit'} onclick={save}>
			{saving ? 'Saving…' : 'Save'}
		</button>
		<button type="button" data-testid="print-reload" onclick={reload}>Reload</button>
		<button type="button" data-testid="print-pdf" disabled={pdfBusy} onclick={exportPdf}>
			{pdfBusy ? 'Exporting…' : 'Download PDF'}
		</button>
		<span class="rev">rev {revision}</span>
	</div>
	{#if status}
		<p class="status" data-testid="print-editor-status" role="status">{status}</p>
	{/if}

	{#if mode === 'edit'}
		<div class="fields" data-testid="print-edit-fields">
			{#each draft.sections as section, sectionIndex}
				<section class="section">
					<h3>{section.title || section.id}</h3>
					{#each section.blocks as block, blockIndex}
						{@const content = block.content as unknown as Record<string, unknown>}
						<div class="block" data-block-object={block.object}>
							<p class="kind">{block.object}</p>
							{#if block.object === 'heading'}
								<textarea
									aria-label="Heading text"
									value={asPlain(content.text)}
									oninput={(event) =>
										setHeadingText(sectionIndex, blockIndex, event.currentTarget.value)}
								></textarea>
							{:else if block.object === 'prose'}
								<textarea
									aria-label="Prose"
									value={(Array.isArray(content.paragraphs) ? content.paragraphs : [])
										.map((item) => asPlain(item))
										.join('\n\n')}
									oninput={(event) => setProse(sectionIndex, blockIndex, event.currentTarget.value)}
								></textarea>
							{:else if block.object === 'list'}
								<textarea
									aria-label="List items"
									value={(Array.isArray(content.items) ? content.items : [])
										.map((item) => asPlain((item as { text?: unknown }).text))
										.join('\n')}
									oninput={(event) =>
										setListItems(sectionIndex, blockIndex, event.currentTarget.value)}
								></textarea>
							{:else if block.object === 'aside'}
								<textarea
									aria-label="Callout body"
									value={asPlain(content.body)}
									oninput={(event) =>
										setAsideBody(sectionIndex, blockIndex, event.currentTarget.value)}
								></textarea>
							{:else if block.object === 'figure'}
								<label>
									Caption
									<input
										value={asPlain(content.caption)}
										oninput={(event) =>
											setFigureField(sectionIndex, blockIndex, 'caption', event.currentTarget.value)}
									/>
								</label>
								<label>
									Alt
									<input
										value={asPlain(content.alt_text)}
										oninput={(event) =>
											setFigureField(sectionIndex, blockIndex, 'alt_text', event.currentTarget.value)}
									/>
								</label>
								<label>
									Asset URL
									<input
										value={asPlain((content.asset as { src?: string } | undefined)?.src)}
										oninput={(event) =>
											setFigureField(sectionIndex, blockIndex, 'src', event.currentTarget.value)}
									/>
								</label>
							{:else if block.object === 'table' && Array.isArray(content.columns) && Array.isArray(content.rows)}
								<table>
									<thead>
										<tr>
											{#each content.columns as column}
												<th>{asPlain((column as { label?: string }).label)}</th>
											{/each}
										</tr>
									</thead>
									<tbody>
										{#each content.rows as row, rowIndex}
											<tr>
												{#each content.columns as column}
													{@const columnId = String((column as { id?: string }).id || '')}
													<td>
														<input
															value={asPlain(
																((row as { cells?: Record<string, unknown> }).cells || {})[
																	columnId
																]
															)}
															oninput={(event) =>
																setTableCell(
																	sectionIndex,
																	blockIndex,
																	rowIndex,
																	columnId,
																	event.currentTarget.value
																)}
														/>
													</td>
												{/each}
											</tr>
										{/each}
									</tbody>
								</table>
							{:else if block.object === 'questions' && Array.isArray(content.items)}
								{#each content.items as item, itemIndex}
									<textarea
										aria-label={`Question ${itemIndex + 1}`}
										value={asPlain((item as { prompt?: unknown }).prompt)}
										oninput={(event) =>
											setQuestionPrompt(
												sectionIndex,
												blockIndex,
												itemIndex,
												event.currentTarget.value
											)}
									></textarea>
								{/each}
							{:else if block.object === 'choices' && Array.isArray(content.options)}
								<p>{asPlain(content.stem)}</p>
								{#each content.options as option, optionIndex}
									<label>
										{(option as { letter?: string }).letter || optionIndex + 1}
										<input
											value={asPlain((option as { text?: unknown }).text)}
											oninput={(event) =>
												setChoiceOption(
													sectionIndex,
													blockIndex,
													optionIndex,
													event.currentTarget.value
												)}
										/>
									</label>
								{/each}
							{:else}
								<pre>{JSON.stringify(content, null, 2)}</pre>
							{/if}
						</div>
					{/each}
				</section>
			{/each}
		</div>
	{/if}
</div>

<style>
	.print-editor {
		display: grid;
		gap: 12px;
		margin-bottom: 1rem;
	}
	.toolbar {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		align-items: center;
	}
	.toolbar button.active {
		font-weight: 700;
	}
	.rev,
	.status {
		font-size: 0.8rem;
		color: #444;
	}
	.fields {
		display: grid;
		gap: 16px;
	}
	.block {
		display: grid;
		gap: 8px;
		padding: 10px;
		border: 1px solid #ddd;
		border-radius: 8px;
	}
	.kind {
		margin: 0;
		font-size: 11px;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: #666;
	}
	textarea,
	input {
		width: 100%;
		font: inherit;
	}
	textarea {
		min-height: 72px;
	}
</style>
