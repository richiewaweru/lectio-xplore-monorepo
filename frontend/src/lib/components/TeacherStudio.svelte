<script lang="ts">
	import { templateRegistryMap } from 'lectio';

	import { planBrief } from '$lib/api/client';
	import type { BriefRequest, GenerationRequest, GenerationSpec, SectionPlan } from '$lib/types';

	const LIVE_PRESET_ID = 'blue-classroom';

	interface Props {
		onsubmit: (request: GenerationRequest) => Promise<void> | void;
		disabled?: boolean;
	}

	let { onsubmit, disabled = false }: Props = $props();

	let studioState = $state('idle' as 'idle' | 'loading_brief' | 'reviewing' | 'submitting_generation');
	let intent: string = $state('');
	let audience: string = $state('');
	let extraContext: string = $state('');
	let briefError = $state(null as string | null);
	let submitError = $state(null as string | null);
	let reviewedSpec = $state(null as GenerationSpec | null);

	const templateName = $derived(
		reviewedSpec
			? templateRegistryMap[reviewedSpec.template_id]?.contract.name ?? reviewedSpec.template_id
			: null
	);

	const isBusy = $derived(
		disabled || studioState === 'loading_brief' || studioState === 'submitting_generation'
	);
	const summaryTitle = $derived(reviewedSpec?.source_brief.intent ?? intent.trim() ?? '');
	const summaryAudience = $derived(reviewedSpec?.source_brief.audience ?? audience.trim() ?? '');
	const sectionCount = $derived(reviewedSpec?.sections.length ?? 0);
	const sectionCards = $derived(reviewedSpec?.sections ?? []);

	function buildBriefRequest(): BriefRequest {
		return {
			intent: intent.trim(),
			audience: audience.trim(),
			mode: 'balanced',
			extra_context: extraContext.trim()
		};
	}

	function buildGenerationContext(spec: GenerationSpec): string {
		const outline = spec.sections
			.map((section) => `Section ${section.position}: ${section.title} - ${section.focus}`)
			.join('\n');
		const parts = [
			spec.source_brief.intent,
			`Audience: ${spec.source_brief.audience}`,
			spec.source_brief.extra_context ? `Notes:\n${spec.source_brief.extra_context}` : null,
			`Lesson outline:\n${outline}`
		].filter(Boolean);

		return parts.join('\n\n');
	}

	function buildGenerationRequest(spec: GenerationSpec): GenerationRequest {
		return {
			subject: spec.source_brief.intent,
			context: buildGenerationContext(spec),
			mode: spec.mode,
			template_id: spec.template_id,
			preset_id: LIVE_PRESET_ID,
			section_count: spec.section_count,
			generation_spec: spec
		};
	}

	async function handlePlan(event: SubmitEvent) {
		event.preventDefault();

		if (isBusy) {
			return;
		}

		briefError = null;
		submitError = null;
		studioState = 'loading_brief';

		try {
			reviewedSpec = await planBrief(buildBriefRequest());
			studioState = 'reviewing';
		} catch (error) {
			reviewedSpec = null;
			studioState = 'idle';
			briefError = error instanceof Error ? error.message : 'Failed to plan the lesson.';
		}
	}

	function updateSectionTitle(sectionId: string, title: string) {
		if (!reviewedSpec) {
			return;
		}

		reviewedSpec = {
			...reviewedSpec,
			sections: reviewedSpec.sections.map((section: SectionPlan) =>
				section.section_id === sectionId ? { ...section, title } : section
			)
		};
	}

	function nudge() {
		if (!reviewedSpec) {
			return;
		}

		intent = reviewedSpec.source_brief.intent;
		audience = reviewedSpec.source_brief.audience;
		extraContext = reviewedSpec.source_brief.extra_context;
		reviewedSpec = null;
		briefError = null;
		submitError = null;
		studioState = 'idle';
	}

	async function handleGenerate() {
		if (!reviewedSpec || isBusy) {
			return;
		}

		submitError = null;
		studioState = 'submitting_generation';

		try {
			await onsubmit(buildGenerationRequest(reviewedSpec));
		} catch (error) {
			submitError = error instanceof Error ? error.message : 'Generation failed.';
		} finally {
			studioState = reviewedSpec ? 'reviewing' : 'idle';
		}
	}
</script>

<section class="studio-shell" data-state={studioState}>
	<div class="studio-header">
		<div>
			<p class="eyebrow">Teacher Studio</p>
			<h2>Plan the lesson before generation</h2>
			<p class="lede">
				Start with plain language, review the brief the backend returns, then hand the reviewed plan
				to the live Blue Classroom runtime.
			</p>
		</div>
		<div class="chip-stack">
			<span class="chip">Blue Classroom preset</span>
		</div>
	</div>

	{#if briefError}
		<div class="notice notice-error" role="alert">{briefError}</div>
	{/if}

	{#if submitError}
		<div class="notice notice-error" role="alert">{submitError}</div>
	{/if}

	{#if studioState === 'idle'}
		<form class="studio-form" onsubmit={handlePlan}>
			<label class="field field-wide">
				<span>What do you want to teach or learn?</span>
				<textarea
					bind:value={intent}
					rows="4"
					required
					placeholder="Teach photosynthesis to Year 10 students"
					disabled={isBusy}
				></textarea>
			</label>

			<label class="field">
				<span>Who is this for?</span>
				<input
					bind:value={audience}
					type="text"
					required
					placeholder="Year 10, mixed ability / age 14 / adults with no maths background"
					disabled={isBusy}
				/>
			</label>

			<details class="notes-panel" open>
				<summary>Add notes or context</summary>
				<div class="notes-body">
					<p class="helper">
						Paste syllabus extracts, prior lesson notes, or any constraints you want the planner to
						respect.
					</p>
					<label class="field field-wide">
						<span class="visually-hidden">Optional notes</span>
						<textarea
							bind:value={extraContext}
							rows="5"
							maxlength="1000"
							placeholder="Paste supporting notes, a syllabus extract, or a quick reminder about the lesson."
							disabled={isBusy}
						></textarea>
					</label>
					<div class="counter">{extraContext.length}/1000</div>
				</div>
			</details>

			<button class="primary-button" type="submit" disabled={isBusy || !intent.trim() || !audience.trim()}>
				Plan this lesson
			</button>
		</form>
	{:else if studioState === 'loading_brief'}
		<div class="loading-shell" aria-busy="true" aria-label="Planning lesson">
			<div class="skeleton-card skeleton-card-wide"></div>
			<div class="skeleton-grid">
				<div class="skeleton-card"></div>
				<div class="skeleton-card"></div>
				<div class="skeleton-card"></div>
			</div>
		</div>
	{:else}
		<div class="review-stack">
			<section class="review-card review-card-header">
				<div class="review-topline">
					<div>
						<p class="eyebrow">Reviewed plan</p>
						<h3>{templateName}</h3>
					</div>
					<div class="chip">{sectionCount} sections</div>
				</div>
				<p class="lede">{reviewedSpec?.rationale}</p>
				<div class="brief-meta">
					<span>Intent: {summaryTitle}</span>
					<span>Audience: {summaryAudience}</span>
				</div>
			</section>

			{#if reviewedSpec?.warning}
				<aside class="notice notice-warn" role="status">{reviewedSpec.warning}</aside>
			{/if}

			<section class="review-card">
				<div class="review-topline">
					<div>
						<p class="eyebrow">Section outline</p>
						<h3>Edit titles only</h3>
					</div>
					<button type="button" class="ghost-button" onclick={nudge}>Nudge</button>
				</div>

				<div class="section-grid">
					{#each sectionCards as section}
						<div class="section-card">
							<div class="section-head">
								<span class="section-pill">Section {section.position}</span>
								<span class="section-id">{section.section_id}</span>
							</div>
							<label class="field">
								<span class="visually-hidden">Section {section.position} title</span>
								<input
									value={section.title}
									oninput={(event) =>
										updateSectionTitle(section.section_id, (event.currentTarget as HTMLInputElement).value)
									}
									disabled={studioState === 'submitting_generation' || disabled}
								/>
							</label>
							<p class="focus-copy">{section.focus}</p>
						</div>
					{/each}
				</div>
			</section>

			<div class="actions">
				<button class="ghost-button" type="button" onclick={nudge} disabled={isBusy}>
					Refine brief
				</button>
				<button
					class="primary-button"
					type="button"
					onclick={handleGenerate}
					disabled={isBusy || !reviewedSpec}
				>
					{#if studioState === 'submitting_generation'}
						Generating...
					{:else}
						Generate
					{/if}
				</button>
			</div>
		</div>
	{/if}
</section>

<style>
	.studio-shell {
		display: grid;
		gap: 1rem;
		border: 1px solid rgba(36, 52, 63, 0.12);
		border-radius: 28px;
		background:
			linear-gradient(180deg, rgba(255, 251, 244, 0.92), rgba(247, 240, 228, 0.82)),
			rgba(255, 255, 255, 0.9);
		box-shadow: 0 18px 50px rgba(72, 52, 23, 0.08);
		padding: 1.35rem;
	}

	.studio-header,
	.review-topline,
	.section-head,
	.actions {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		align-items: center;
	}

	.studio-header {
		align-items: start;
	}

	.eyebrow {
		margin: 0 0 0.3rem 0;
		font-size: 0.78rem;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: #6b7c88;
	}

	h2,
	h3,
	p {
		margin: 0;
	}

	.lede,
	.helper,
	.focus-copy {
		color: #655c52;
	}

	.chip-stack,
	.brief-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		justify-content: flex-end;
	}

	.chip,
	.section-pill,
	.section-id {
		border-radius: 999px;
		padding: 0.3rem 0.65rem;
		font-size: 0.76rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	.chip,
	.section-pill {
		background: rgba(36, 52, 63, 0.08);
		color: #24343f;
	}

	.section-id {
		background: rgba(108, 94, 74, 0.08);
		color: #6c5e4a;
	}

	.notice {
		padding: 0.9rem 1rem;
		border-radius: 18px;
		border: 1px solid rgba(36, 52, 63, 0.1);
	}

	.notice-error {
		background: rgba(255, 242, 238, 0.9);
		border-color: rgba(148, 66, 46, 0.18);
		color: #7d3524;
	}

	.notice-warn {
		background: rgba(255, 248, 232, 0.92);
		border-color: rgba(156, 107, 14, 0.16);
		color: #805d16;
	}

	.studio-form,
	.review-stack {
		display: grid;
		gap: 1rem;
	}

	.field {
		display: grid;
		gap: 0.4rem;
		color: #2b3037;
	}

	.field span {
		font-size: 0.92rem;
		font-weight: 600;
	}

	.field-wide {
		grid-column: 1 / -1;
	}

	input,
	textarea {
		border: 1px solid rgba(36, 52, 63, 0.14);
		border-radius: 16px;
		padding: 0.82rem 0.95rem;
		background: rgba(255, 255, 255, 0.88);
		color: #202020;
		font: inherit;
	}

	textarea {
		resize: vertical;
		min-height: 7rem;
	}

	input:disabled,
	textarea:disabled,
	button:disabled {
		opacity: 0.65;
		cursor: not-allowed;
	}

	.notes-panel {
		border: 1px solid rgba(36, 52, 63, 0.12);
		border-radius: 20px;
		background: rgba(255, 255, 255, 0.42);
		padding: 0.9rem;
	}

	.notes-panel summary {
		cursor: pointer;
		font-weight: 600;
		color: #24343f;
	}

	.notes-body {
		display: grid;
		gap: 0.75rem;
		padding-top: 0.85rem;
	}

	.counter {
		justify-self: end;
		font-size: 0.8rem;
		color: #726658;
	}

	.primary-button,
	.ghost-button {
		border-radius: 999px;
		padding: 0.78rem 1.1rem;
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}

	.primary-button {
		border: none;
		background: linear-gradient(135deg, #15395f, #1f5f8a);
		color: #fff;
	}

	.ghost-button {
		border: 1px solid rgba(36, 67, 106, 0.14);
		background: rgba(36, 67, 106, 0.05);
		color: #24436a;
	}

	.review-card {
		border: 1px solid rgba(36, 52, 63, 0.12);
		border-radius: 24px;
		background: rgba(255, 255, 255, 0.72);
		padding: 1rem;
	}

	.review-card-header {
		background: linear-gradient(180deg, rgba(250, 249, 244, 0.92), rgba(243, 236, 225, 0.9));
	}

	.section-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 0.9rem;
		margin-top: 0.95rem;
	}

	.section-card {
		display: grid;
		gap: 0.7rem;
		padding: 0.95rem;
		border-radius: 18px;
		border: 1px solid rgba(36, 52, 63, 0.1);
		background: rgba(255, 255, 255, 0.82);
	}

	.section-head {
		align-items: start;
	}

	.focus-copy {
		font-size: 0.92rem;
	}

	.actions {
		justify-content: flex-end;
	}

	.loading-shell {
		display: grid;
		gap: 1rem;
		animation: fade-in 180ms ease-out;
	}

	.skeleton-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 0.9rem;
	}

	.skeleton-card {
		height: 9.5rem;
		border-radius: 18px;
		background: linear-gradient(
			90deg,
			rgba(230, 223, 212, 0.48) 0%,
			rgba(248, 242, 231, 0.88) 50%,
			rgba(230, 223, 212, 0.48) 100%
		);
		background-size: 200% 100%;
		animation: shimmer 1.4s linear infinite;
	}

	.skeleton-card-wide {
		height: 6.5rem;
	}

	.visually-hidden {
		position: absolute;
		width: 1px;
		height: 1px;
		padding: 0;
		margin: -1px;
		overflow: hidden;
		clip: rect(0, 0, 0, 0);
		white-space: nowrap;
		border: 0;
	}

	@keyframes shimmer {
		0% {
			background-position: 200% 0;
		}
		100% {
			background-position: -200% 0;
		}
	}

	@keyframes fade-in {
		from {
			opacity: 0;
			transform: translateY(4px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	@media (max-width: 720px) {
		.studio-header,
		.review-topline,
		.section-head,
		.actions {
			flex-direction: column;
			align-items: stretch;
		}

		.chip-stack,
		.brief-meta {
			justify-content: flex-start;
		}
	}
</style>
