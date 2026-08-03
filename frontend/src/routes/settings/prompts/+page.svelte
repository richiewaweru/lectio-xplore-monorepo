<script lang="ts">
	import { onMount } from 'svelte';
	import {
		getPrompt,
		listPrompts,
		resetPrompt,
		savePrompt,
		type PromptDetail,
		type PromptListItem
	} from '$lib/api/prompts';

	let items = $state<PromptListItem[]>([]);
	let selectedId = $state<string | null>(null);
	let detail = $state<PromptDetail | null>(null);
	let editing = $state(false);
	let draft = $state('');
	let busy = $state(false);
	let errorMessage = $state<string | null>(null);

	onMount(async () => {
		try {
			items = await listPrompts();
			if (items.length > 0) {
				await openPrompt(items[0].id);
			}
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : 'Failed to load prompts.';
		}
	});

	async function openPrompt(id: string) {
		errorMessage = null;
		editing = false;
		selectedId = id;
		detail = await getPrompt(id);
		draft = detail.text;
	}

	async function onSave() {
		if (!selectedId || !detail?.editable) return;
		busy = true;
		errorMessage = null;
		try {
			detail = await savePrompt(selectedId, draft);
			items = await listPrompts();
			editing = false;
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : 'Save failed.';
		} finally {
			busy = false;
		}
	}

	async function onReset() {
		if (!selectedId || !detail?.editable) return;
		busy = true;
		errorMessage = null;
		try {
			detail = await resetPrompt(selectedId);
			draft = detail.text;
			items = await listPrompts();
			editing = false;
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : 'Reset failed.';
		} finally {
			busy = false;
		}
	}

	function renderMarkdown(text: string): string {
		// Lightweight formatting for headings, lists, and emphasis — not a full markdown engine.
		const escaped = text
			.replace(/&/g, '&amp;')
			.replace(/</g, '&lt;')
			.replace(/>/g, '&gt;');
		return escaped
			.replace(/^### (.+)$/gm, '<h3>$1</h3>')
			.replace(/^## (.+)$/gm, '<h2>$1</h2>')
			.replace(/^# (.+)$/gm, '<h1>$1</h1>')
			.replace(/^\- (.+)$/gm, '<li>$1</li>')
			.replace(/(<li>.*<\/li>\n?)+/g, (block) => `<ul>${block}</ul>`)
			.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
			.replace(/\*(.+?)\*/g, '<em>$1</em>')
			.replace(/\n\n/g, '</p><p>')
			.replace(/^(?!<[hul])/gm, (line, offset, full) => {
				if (offset === 0) return `<p>${line}`;
				return line;
			});
	}
</script>

<svelte:head><title>How lessons get written · Lectio</title></svelte:head>

<div class="prompts-page">
	<a class="back-link" href="/settings">← Settings</a>
	<header>
		<p class="eyebrow">Settings</p>
		<h1>How lessons get written</h1>
		<p class="lede">
			These are the instructions the system follows when it plans and writes your lessons. You can
			read all of them; most can be edited for your classroom.
		</p>
	</header>

	{#if errorMessage}
		<p class="error" role="alert">{errorMessage}</p>
	{/if}

	<div class="layout">
		<aside>
			<ol>
				{#each items as item}
					<li>
						<button
							type="button"
							class:active={item.id === selectedId}
							onclick={() => openPrompt(item.id)}
						>
							<span>{item.stage_label}</span>
							{#if item.modified}<span class="badge">modified</span>{/if}
							{#if !item.editable}<span class="lock" title="Locked">locked</span>{/if}
						</button>
					</li>
				{/each}
			</ol>
		</aside>

		<section>
			{#if detail}
				<div class="section-head">
					<div>
						<h2>{detail.stage_label}</h2>
						{#if detail.modified}<span class="badge">modified</span>{/if}
					</div>
					{#if detail.editable}
						<div class="actions">
							{#if editing}
								<button type="button" class="secondary" disabled={busy} onclick={onSave}>
									{busy ? 'Saving…' : 'Save'}
								</button>
								<button type="button" class="text-button" disabled={busy} onclick={() => (editing = false, draft = detail?.text ?? '')}>
									Cancel
								</button>
								<button type="button" class="text-button" disabled={busy} onclick={onReset}>
									Reset to default
								</button>
							{:else}
								<button type="button" class="secondary" onclick={() => (editing = true)}>Edit</button>
								{#if detail.modified}
									<button type="button" class="text-button" disabled={busy} onclick={onReset}>
										Reset to default
									</button>
								{/if}
							{/if}
						</div>
					{:else}
						<p class="lock-note">
							{#if detail.id === 'quiz-items'}
								This one keeps the quiz honest, so it can't be changed.
							{:else}
								This one protects lesson structure, so it can't be changed.
							{/if}
						</p>
					{/if}
				</div>

				{#if editing}
					<textarea bind:value={draft} rows="24" aria-label="Prompt editor"></textarea>
				{:else}
					<div class="markdown">{@html renderMarkdown(detail.text)}</div>
				{/if}
			{:else}
				<p role="status">Loading…</p>
			{/if}
		</section>
	</div>
</div>

<style>
	.prompts-page {
		display: grid;
		gap: 1.5rem;
		max-width: 1100px;
		margin: 0 auto;
		padding: 2rem 1.25rem 4rem;
	}
	.back-link {
		color: inherit;
		text-decoration: none;
		opacity: 0.7;
	}
	.eyebrow {
		text-transform: uppercase;
		letter-spacing: 0.08em;
		font-size: 0.75rem;
		opacity: 0.65;
		margin: 0;
	}
	h1 {
		margin: 0.25rem 0;
		font-size: 2rem;
	}
	.lede {
		max-width: 42rem;
		opacity: 0.8;
	}
	.layout {
		display: grid;
		grid-template-columns: minmax(220px, 280px) 1fr;
		gap: 1.5rem;
		align-items: start;
	}
	aside ol {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		gap: 0.35rem;
	}
	aside button {
		width: 100%;
		text-align: left;
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		align-items: center;
		padding: 0.65rem 0.75rem;
		border: 1px solid color-mix(in srgb, currentColor 18%, transparent);
		background: transparent;
		border-radius: 0.4rem;
		cursor: pointer;
		color: inherit;
	}
	aside button.active {
		border-color: color-mix(in srgb, currentColor 45%, transparent);
		background: color-mix(in srgb, currentColor 6%, transparent);
	}
	.badge,
	.lock {
		font-size: 0.7rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		padding: 0.1rem 0.35rem;
		border-radius: 999px;
		border: 1px solid color-mix(in srgb, currentColor 25%, transparent);
	}
	.section-head {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		align-items: flex-start;
		margin-bottom: 1rem;
	}
	.actions {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.secondary,
	.text-button {
		cursor: pointer;
		border-radius: 0.35rem;
		padding: 0.4rem 0.75rem;
		border: 1px solid color-mix(in srgb, currentColor 25%, transparent);
		background: transparent;
		color: inherit;
	}
	.text-button {
		border: none;
		text-decoration: underline;
		padding-inline: 0.25rem;
	}
	.lock-note {
		opacity: 0.75;
		font-size: 0.95rem;
		max-width: 18rem;
	}
	.markdown {
		line-height: 1.55;
		white-space: normal;
	}
	.markdown :global(h1),
	.markdown :global(h2),
	.markdown :global(h3) {
		margin: 1.1rem 0 0.4rem;
	}
	.markdown :global(ul) {
		padding-left: 1.2rem;
	}
	.markdown :global(p) {
		margin: 0.6rem 0;
	}
	textarea {
		width: 100%;
		min-height: 28rem;
		font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
		font-size: 0.9rem;
		line-height: 1.45;
		padding: 0.75rem;
		border-radius: 0.4rem;
		border: 1px solid color-mix(in srgb, currentColor 25%, transparent);
		background: color-mix(in srgb, currentColor 3%, transparent);
		color: inherit;
	}
	.error {
		color: #a33;
	}
	@media (max-width: 800px) {
		.layout {
			grid-template-columns: 1fr;
		}
	}
</style>
