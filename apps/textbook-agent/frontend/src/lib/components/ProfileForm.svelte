<script lang="ts">
	import {
		basePresets,
		templateRegistry,
		type TemplateDefinition
	} from 'lectio';
	import TemplatePreviewOverlay from '$lib/components/TemplatePreviewOverlay.svelte';

	type LegacyGenerationRequest = {
		subject: string;
		context: string;
		template_id: string;
		preset_id: string;
		section_count?: number;
	};

	const LIVE_PRESET_ID = 'blue-classroom';
	const livePresets = basePresets.filter((preset) => preset.id === LIVE_PRESET_ID);
	const liveTemplateRegistry = templateRegistry.filter((template) =>
		template.presets.some((preset) => preset.id === LIVE_PRESET_ID)
	);

	let subject = $state('');
	let context = $state('');
	let sectionCount = $state(4);
	let selectedTemplateId = $state(liveTemplateRegistry[0]?.contract.id ?? '');
	let selectedPresetId = $state(livePresets[0]?.id ?? '');
	let previewTemplateId = $state<string | null>(null);

	interface Props {
		onsubmit: (request: LegacyGenerationRequest) => void;
		disabled?: boolean;
	}

	let { onsubmit, disabled = false }: Props = $props();

	const selectedTemplate = $derived(
		liveTemplateRegistry.find((template) => template.contract.id === selectedTemplateId) ?? null
	);
	const previewTemplate = $derived(
		liveTemplateRegistry.find((template) => template.contract.id === previewTemplateId) ?? null
	);
	const previewTemplateName = $derived(previewTemplate?.contract.name ?? null);
	const availablePresets = $derived(
		(selectedTemplate?.presets ?? livePresets).filter((preset) => preset.id === LIVE_PRESET_ID)
	);

	$effect(() => {
		if (!selectedTemplateId && liveTemplateRegistry[0]) {
			selectedTemplateId = liveTemplateRegistry[0].contract.id;
		}

		if (!availablePresets.some((preset) => preset.id === selectedPresetId)) {
			selectedPresetId = availablePresets[0]?.id ?? livePresets[0]?.id ?? '';
		}
	});

	function submit() {
		if (!selectedTemplateId || !selectedPresetId) {
			return;
		}
		onsubmit({
			subject,
			context,
			template_id: selectedTemplateId,
			preset_id: selectedPresetId,
			section_count: sectionCount
		});
	}

	function learnerFitCopy(template: TemplateDefinition): string {
		return template.contract.learnerFit.join(', ').replace(/-/g, ' ');
	}

	function openTemplatePreview(template: TemplateDefinition) {
		selectedTemplateId = template.contract.id;
		previewTemplateId = template.contract.id;
	}

	function closeTemplatePreview() {
		previewTemplateId = null;
	}

	function usePreviewTemplate() {
		closeTemplatePreview();
	}
</script>

<form
	onsubmit={(event: Event) => {
		event.preventDefault();
		submit();
	}}
	class="generation-form"
>
	<section class="briefing">
			<div>
				<p class="eyebrow">Generation Brief</p>
				<h3>Describe the lesson you want</h3>
				<p class="copy">
					The shell keeps profile data outside the generation flow. Here you are choosing the lesson
					brief, and a fully wired Lectio template plus live preset.
				</p>
			</div>
		</section>

	<div class="field-grid">
		<label>
			Subject
			<input
				type="text"
				bind:value={subject}
				placeholder="e.g. calculus, ecosystems, thermodynamics"
				required
			/>
		</label>

		<label class="wide">
			Context
			<textarea
				bind:value={context}
				rows="4"
				placeholder="What should this generation teach, reinforce, or focus on?"
				required
			></textarea>
		</label>

		<label>
			Sections
			<input type="number" min="1" max="12" bind:value={sectionCount} />
			<span class="hint">Four is the default. Use fewer for tighter passes, more for broader coverage.</span>
		</label>
	</div>

	<section class="selection-shell">
		<div class="selection-header">
			<div>
				<p class="eyebrow">Template</p>
				<h3>Choose the teaching structure</h3>
				<p class="selection-note">
					Templates shown here are already wired to the live Blue Classroom runtime.
				</p>
			</div>
			<div class="selection-chip">{selectedTemplateId}</div>
		</div>

		<div class="template-grid">
			{#each liveTemplateRegistry as template}
				<button
					type="button"
					class:selected={template.contract.id === selectedTemplateId}
					class="template-card"
					aria-haspopup="dialog"
					aria-label={`Preview ${template.contract.name}`}
					onclick={() => {
						openTemplatePreview(template);
					}}
				>
					<div class="card-topline">
						<p class="template-id">{template.contract.id}</p>
						<span class="family">{template.contract.family.replace(/-/g, ' ')}</span>
					</div>
					<h4>{template.contract.name}</h4>
					<p class="template-description">{template.contract.tagline}</p>
					<p class="template-meta">
						<span>{template.contract.intent.replace(/-/g, ' ')}</span>
						<span>Interaction: {template.contract.interactionLevel}</span>
					</p>
					<p class="template-fit">Learner fit: {learnerFitCopy(template)}</p>
					<p class="template-preview-cta">Click to preview</p>
				</button>
			{/each}
		</div>
	</section>

	<section class="selection-shell">
		<div class="selection-header">
			<div>
				<p class="eyebrow">Preset</p>
				<h3>Choose the live visual preset</h3>
				<p class="selection-note">
					Only fully implemented preset themes are exposed in-product right now.
				</p>
			</div>
			<div class="selection-chip">{selectedPresetId}</div>
		</div>

		<div class="preset-grid">
			{#each availablePresets as preset}
				<button
					type="button"
					class:selected={preset.id === selectedPresetId}
					class="preset-card"
					onclick={() => {
						selectedPresetId = preset.id;
					}}
				>
					<p class="preset-id">{preset.id}</p>
					<h4>{preset.name}</h4>
					<p>{preset.description}</p>
					<p class="preset-meta">{preset.palette}</p>
				</button>
			{/each}
		</div>
	</section>

	<button type="submit" disabled={disabled || !selectedTemplateId || !selectedPresetId}>
		Start Generation
	</button>
</form>

<TemplatePreviewOverlay
	open={previewTemplateId !== null}
	templateId={previewTemplateId}
	templateName={previewTemplateName}
	presetId={selectedPresetId || null}
	onclose={closeTemplatePreview}
	onuse={usePreviewTemplate}
/>

<style>
	.generation-form {
		display: grid;
		gap: 1.25rem;
	}

	.briefing,
	.selection-shell {
		border: 1px solid rgba(36, 52, 63, 0.12);
		border-radius: 24px;
		background: rgba(255, 251, 244, 0.82);
		box-shadow: 0 14px 50px rgba(78, 58, 29, 0.08);
		padding: 1.2rem 1.3rem;
	}

	.eyebrow {
		margin: 0 0 0.3rem 0;
		font-size: 0.76rem;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: #6b7c88;
	}

	h3 {
		margin: 0;
		font-size: 1.2rem;
	}

	.copy {
		margin: 0.45rem 0 0 0;
		max-width: 62ch;
		color: #6b6257;
	}

	.selection-note {
		margin: 0.35rem 0 0 0;
		max-width: 56ch;
		color: #6b6257;
		font-size: 0.9rem;
	}

	.field-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 1rem;
	}

	.wide {
		grid-column: 1 / -1;
	}

	label {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		font-size: 0.92rem;
		color: #2b3037;
	}

	input,
	textarea {
		padding: 0.78rem 0.9rem;
		border-radius: 14px;
		border: 1px solid rgba(36, 52, 63, 0.14);
		background: rgba(255, 255, 255, 0.82);
		color: #202020;
		font: inherit;
	}

	.hint {
		font-size: 0.8rem;
		color: #726658;
	}

	.selection-header {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		align-items: start;
		margin-bottom: 1rem;
	}

	.selection-chip {
		padding: 0.45rem 0.7rem;
		border-radius: 999px;
		background: rgba(31, 43, 52, 0.08);
		color: #24343f;
		font-size: 0.82rem;
	}

	.template-grid,
	.preset-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 0.9rem;
	}

	.template-card,
	.preset-card {
		display: grid;
		gap: 0.55rem;
		padding: 1rem;
		text-align: left;
		border-radius: 18px;
		border: 1px solid rgba(36, 52, 63, 0.12);
		background: linear-gradient(180deg, rgba(255, 255, 255, 0.95), rgba(245, 237, 223, 0.85));
		cursor: pointer;
		color: inherit;
		transition:
			transform 0.15s ease,
			border-color 0.15s ease,
			box-shadow 0.15s ease;
	}

	.template-card:hover,
	.preset-card:hover {
		transform: translateY(-1px);
		border-color: rgba(36, 52, 63, 0.25);
		box-shadow: 0 16px 36px rgba(57, 42, 16, 0.1);
	}

	.template-card.selected,
	.preset-card.selected {
		border-color: #24436a;
		box-shadow: inset 0 0 0 1px rgba(36, 67, 106, 0.18);
		background: linear-gradient(180deg, rgba(241, 248, 255, 0.95), rgba(227, 236, 244, 0.92));
	}

	.card-topline,
	.template-meta {
		display: flex;
		justify-content: space-between;
		gap: 0.75rem;
		flex-wrap: wrap;
	}

	.template-id,
	.preset-id,
	.family {
		margin: 0;
		font-size: 0.78rem;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: #6d6a64;
	}

	h4 {
		margin: 0;
		font-size: 1rem;
	}

	.template-description,
	.template-fit,
	.preset-meta {
		margin: 0;
		color: #5d554a;
		font-size: 0.9rem;
	}

	.template-preview-cta {
		margin: 0;
		font-size: 0.82rem;
		font-weight: 600;
		color: #24436a;
	}

	button[type='submit'] {
		padding: 0.9rem 1.1rem;
		border-radius: 999px;
		border: none;
		background: linear-gradient(135deg, #1f3d52, #325d78);
		color: #fff;
		font: inherit;
		font-weight: 600;
		cursor: pointer;
		justify-self: start;
	}

	@media (max-width: 720px) {
		.field-grid {
			grid-template-columns: 1fr;
		}

		.selection-header {
			flex-direction: column;
		}
	}
</style>
