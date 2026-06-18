<script lang="ts">
	import { contracts, editedSpec, planDraft, planningMs, updateSection } from '$lib/stores/studio';
	import {
		componentLabel,
		isHeavyComponent,
		roleLabel,
		roleTone,
		visualPolicyDetail,
		visualPolicyLabel
	} from '$lib/studio/presentation';
	import type { StudioTemplateContract } from '$lib/types';

	interface Props {
		busy?: boolean;
		onBack: () => void;
		onCommit: () => void;
		onTemplateSwap: (contract: StudioTemplateContract) => void;
		errorMessage?: string | null;
		catalogError?: string | null;
	}

	type ReviewTemplateCard = {
		contract: StudioTemplateContract;
		fitScore: number | null;
		selected: boolean;
		reason: string;
		label: string;
	};

	let {
		busy = false,
		onBack,
		onCommit,
		onTemplateSwap,
		errorMessage = null,
		catalogError = null
	}: Props = $props();

	let expandedSections = $state<Record<string, boolean>>({});

	const templateCards = $derived.by(() => {
		if (!$editedSpec) {
			return [] as ReviewTemplateCard[];
		}

		const contractsById = new Map($contracts.map((contract) => [contract.id, contract]));
		const cards: ReviewTemplateCard[] = [];
		const selectedId = $editedSpec.template_id;
		const seen = new Set<string>();

		function pushCard(
			templateId: string,
			fitScore: number | null,
			reason: string,
			label: string
		): void {
			if (seen.has(templateId)) {
				return;
			}
			const contract = contractsById.get(templateId);
			if (!contract) {
				return;
			}
			seen.add(templateId);
			cards.push({
				contract,
				fitScore,
				selected: templateId === selectedId,
				reason,
				label
			});
		}

		pushCard(
			selectedId,
			$editedSpec.template_decision.chosen_id === selectedId
				? $editedSpec.template_decision.fit_score
				: null,
			$editedSpec.template_decision.rationale,
			selectedId === $planDraft.template_decision?.chosen_id ? 'Best fit' : 'Current selection'
		);

		$editedSpec.template_decision.alternatives.forEach((alternative, index) => {
			pushCard(
				alternative.template_id,
				alternative.fit_score,
				alternative.why_not_chosen,
				`Alternative ${index + 1}`
			);
		});

		return cards;
	});

	const templateChanged = $derived(
		Boolean($planDraft.template_decision) &&
			$editedSpec?.template_id !== $planDraft.template_decision?.chosen_id
	);

	function handleTitleInput(sectionId: string, title: string) {
		updateSection(sectionId, (section) => ({
			...section,
			title
		}));
	}

	function handleFocusInput(sectionId: string, focusNote: string) {
		updateSection(sectionId, (section) => ({
			...section,
			focus_note: focusNote.trim() ? focusNote : null
		}));
	}

	function handleTransitionInput(sectionId: string, transitionNote: string) {
		updateSection(sectionId, (section) => ({
			...section,
			transition_note: transitionNote.trim() ? transitionNote : null
		}));
	}

	function toggleSection(sectionId: string) {
		expandedSections = {
			...expandedSections,
			[sectionId]: !expandedSections[sectionId]
		};
	}

	function handleTemplateSelect(contract: StudioTemplateContract) {
		if (busy || !$editedSpec || contract.id === $editedSpec.template_id) {
			return;
		}
		onTemplateSwap(contract);
	}

	function formatElapsed(ms: number): string {
		if (!ms) {
			return 'Just now';
		}
		return `${(ms / 1000).toFixed(1)}s`;
	}
</script>

{#if $editedSpec}
	<section class="review-shell">
		<header class="review-header">
			<div>
				<p class="eyebrow">Review</p>
				<h2>Approve the plan before generation</h2>
				<p class="lede">
					This is the only hard gate in the studio. Check the structure, refine the wording, and
					commit the exact plan you want the generator to follow.
				</p>
			</div>
			<div class="review-meta">
				<span class="meta-pill">{$editedSpec.sections.length} sections</span>
				<span class="meta-pill">Planned in {formatElapsed($planningMs)}</span>
			</div>
		</header>

		{#if errorMessage}
			<p class="notice notice-error" role="alert">{errorMessage}</p>
		{/if}

		{#if $planDraft.error}
			<p class="notice notice-warn">{$planDraft.error}</p>
		{/if}

		{#if $editedSpec.warning}
			<p class="notice notice-warn">{$editedSpec.warning}</p>
		{/if}

		<section class="summary-panel">
			<div class="summary-topline">
				<div>
					<p class="label">Template decision</p>
					<h3>{$editedSpec.template_decision.chosen_name}</h3>
				</div>
				<span class="score-pill">Fit {$editedSpec.template_decision.fit_score.toFixed(2)}</span>
			</div>
			<div class="rationale-box">
				<p>{$editedSpec.lesson_rationale}</p>
			</div>
			<p class="small-copy">{$editedSpec.template_decision.rationale}</p>
			{#if templateChanged}
				<p class="template-updated">Template updated during review. Section defaults were re-derived locally.</p>
			{/if}
		</section>

		<section class="template-panel">
			<div class="panel-header">
				<div>
					<p class="label">Ranked alternatives</p>
					<h3>Try another safe Lectio shape</h3>
				</div>
				<p class="small-copy">Swapping stays client-side until you commit.</p>
			</div>

			{#if catalogError}
				<p class="notice notice-error">{catalogError}</p>
			{:else if templateCards.length}
				<div class="template-grid">
					{#each templateCards as card}
						<button
							type="button"
							class:selected-template={card.selected}
							class="template-card"
							onclick={() => handleTemplateSelect(card.contract)}
							disabled={busy}
						>
							<div class="template-card-topline">
								<div>
									<p class="template-label">{card.label}</p>
									<strong>{card.contract.name}</strong>
								</div>
								{#if card.fitScore !== null}
									<span class="fit-chip">{card.fitScore.toFixed(2)}</span>
								{/if}
							</div>
							<p>{card.contract.tagline}</p>
							<small>{card.reason}</small>
						</button>
					{/each}
				</div>
			{:else}
				<p class="small-copy">Template alternatives will appear here once the contract catalog is available.</p>
			{/if}
		</section>

		<section class="section-panel">
			<div class="panel-header">
				<div>
					<p class="label">Sections</p>
					<h3>Edit titles, focus, and transitions</h3>
				</div>
				<p class="small-copy">Roles and components stay read-only in phase 1.</p>
			</div>

			<div class="section-list">
				{#each $editedSpec.sections as section}
					<article class="section-card">
						<div class="section-header">
							<div class="section-title-wrap">
								<span class="order-pill">{String(section.order).padStart(2, '0')}</span>
								<input
									class="section-title-input"
									type="text"
									value={section.title}
									aria-label={`Section ${section.order} title`}
									oninput={(event) =>
										handleTitleInput(section.id, (event.currentTarget as HTMLInputElement).value)}
									disabled={busy}
								/>
							</div>
							<div class="section-tags">
								<span class={`role-pill role-${roleTone(section.role)}`}>{roleLabel(section.role)}</span>
								{#if visualPolicyDetail(section.visual_policy)}
									{@const vd = visualPolicyDetail(section.visual_policy)}
									<span class="visual-pill">{vd?.chip}</span>
								{/if}
								<button class="toggle-pill" type="button" onclick={() => toggleSection(section.id)}>
									{expandedSections[section.id] ? 'Hide details' : 'Details'}
								</button>
							</div>
						</div>

						{#if section.objective}
							<p class="section-objective">{section.objective}</p>
						{/if}

						<div class="component-row">
							{#each section.selected_components as component}
								<span class:heavy-chip={isHeavyComponent(component)} class="component-chip">
									{componentLabel(component)}
								</span>
							{/each}
						</div>

						{#if expandedSections[section.id]}
							<div class="section-detail">
								{#if section.objective || section.rationale}
									<p class="section-copy">{section.objective || section.rationale}</p>
								{/if}
								{#if visualPolicyDetail(section.visual_policy)?.goal}
									<p class="visual-goal">{visualPolicyDetail(section.visual_policy)?.goal}</p>
								{/if}
								<label class="field">
									<span>Focus note</span>
									<textarea
										rows="3"
										value={section.focus_note ?? ''}
										placeholder="Optional: guide what the AI emphasises — e.g. 'Use a river ecosystem example'"
										aria-label={`Section ${section.order} focus note`}
										oninput={(event) =>
											handleFocusInput(section.id, (event.currentTarget as HTMLTextAreaElement).value)}
										disabled={busy}
									></textarea>
								</label>
								<label class="field">
									<span>Transition note</span>
									<textarea
										rows="3"
										value={section.transition_note ?? ''}
										placeholder="How the previous section leads into this one"
										aria-label={`Section ${section.order} transition note`}
										oninput={(event) =>
											handleTransitionInput(section.id, (event.currentTarget as HTMLTextAreaElement).value)}
										disabled={busy || section.order === 1}
									></textarea>
								</label>
							</div>
						{/if}
					</article>
				{/each}
			</div>
		</section>

		<div class="actions">
			<div class="action-copy">Nothing generates until you explicitly approve this plan.</div>
			<div class="action-buttons">
				<button class="secondary-button" type="button" onclick={onBack} disabled={busy}>
					&lt;- Edit intent
				</button>
				<button class="primary-button" type="button" onclick={onCommit} disabled={busy}>
					{busy ? 'Starting generation...' : 'Generate lesson ->'}
				</button>
			</div>
		</div>
	</section>
{/if}

<style>
	.review-shell {
		display: grid;
		gap: 1rem;
	}

	.review-header,
	.review-meta,
	.summary-topline,
	.panel-header,
	.section-header,
	.section-title-wrap,
	.section-tags,
	.action-buttons,
	.actions {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		align-items: start;
	}

	.review-meta,
	.component-row,
	.template-grid {
		display: grid;
	}

	.review-meta {
		grid-auto-flow: row;
		gap: 0.5rem;
	}

	.eyebrow,
	.label,
	.template-label,
	.field span {
		margin: 0;
		font-size: 0.76rem;
		font-weight: 700;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: #6b7c88;
	}

	h2,
	h3,
	p {
		margin: 0;
	}

	.lede,
	.small-copy,
	.section-copy,
	.action-copy {
		color: #625a50;
		line-height: 1.6;
	}

	.meta-pill,
	.score-pill,
	.fit-chip,
	.order-pill,
	.role-pill,
	.visual-pill,
	.toggle-pill,
	.component-chip {
		display: inline-flex;
		align-items: center;
		border-radius: 999px;
		padding: 0.3rem 0.68rem;
		font-size: 0.76rem;
		font-weight: 700;
	}

	.meta-pill,
	.score-pill,
	.fit-chip,
	.toggle-pill {
		background: #f1ece4;
		color: #4f5c65;
	}

	.summary-panel,
	.template-panel,
	.section-panel,
	.actions {
		display: grid;
		gap: 0.9rem;
		border: 0.5px solid rgba(36, 52, 63, 0.12);
		border-radius: 1.35rem;
		background: #fffdf9;
		padding: 1.1rem;
	}

	.rationale-box {
		border-radius: 1rem;
		background: #e1f5ee;
		padding: 0.9rem 1rem;
		color: #085041;
	}

	.template-updated {
		color: #0b6a52;
		font-size: 0.88rem;
		font-weight: 600;
	}

	.notice {
		margin: 0;
		border-radius: 0.95rem;
		padding: 0.85rem 0.95rem;
	}

	.notice-error {
		background: #fff2ee;
		color: #7d3524;
	}

	.notice-warn {
		background: #fff8e4;
		color: #805d16;
	}

	.template-grid {
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 0.8rem;
	}

	.template-card,
	.section-card {
		display: grid;
		gap: 0.7rem;
		border-radius: 1rem;
		border: 0.5px solid rgba(36, 52, 63, 0.1);
		background: #f8f4ec;
		padding: 0.95rem;
		text-align: left;
	}

	.template-card {
		cursor: pointer;
	}

	.template-card-topline {
		display: flex;
		justify-content: space-between;
		gap: 0.6rem;
		align-items: start;
	}

	.template-card p,
	.template-card small {
		color: #625a50;
		line-height: 1.55;
	}

	.selected-template {
		border-color: rgba(29, 158, 117, 0.42);
		background: #eef8f4;
	}

	.section-list {
		display: grid;
		gap: 0.8rem;
	}

	.section-header {
		align-items: center;
	}

	.section-title-wrap {
		flex: 1;
		align-items: center;
	}

	.order-pill {
		background: #f1ece4;
		color: #4f5c65;
	}

	.section-title-input,
	textarea {
		width: 100%;
		border: 0.5px solid rgba(36, 52, 63, 0.14);
		border-radius: 0.9rem;
		padding: 0.72rem 0.82rem;
		background: #fffdf9;
		color: #1d1b17;
		font: inherit;
	}

	textarea {
		resize: vertical;
	}

	.section-title-input:focus,
	textarea:focus {
		outline: 2px solid rgba(29, 158, 117, 0.18);
		outline-offset: 1px;
		border-color: rgba(29, 158, 117, 0.42);
	}

	.section-tags,
	.component-row {
		flex-wrap: wrap;
	}

	.component-row {
		display: flex;
		gap: 0.45rem;
	}

	.component-chip {
		background: #ffffff;
		color: #4f5c65;
		border: 0.5px solid rgba(36, 52, 63, 0.1);
	}

	.heavy-chip {
		background: #fff2d8;
		color: #6a3a04;
		border-color: rgba(186, 117, 23, 0.28);
	}

	.role-pill {
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}

	.role-intro {
		background: #e6f1fb;
		color: #185fa5;
	}

	.role-explain {
		background: #eeedfe;
		color: #3c3489;
	}

	.role-practice {
		background: #faeeda;
		color: #633806;
	}

	.role-summary {
		background: #eaf3de;
		color: #3b6d11;
	}

	.role-neutral {
		background: #f1ece4;
		color: #4f5c65;
	}

	.visual-pill {
		background: #fff8e4;
		color: #805d16;
	}

	.section-objective {
		font-size: 0.82rem;
		color: #625a50;
		line-height: 1.45;
		margin: 0.25rem 0.1rem 0;
	}

	.visual-goal {
		font-size: 0.8rem;
		color: #625a50;
		font-style: italic;
		margin-top: 0.3rem;
	}

	.toggle-pill {
		border: none;
		cursor: pointer;
	}

	.section-detail {
		display: grid;
		gap: 0.8rem;
		padding-top: 0.1rem;
	}

	.field {
		display: grid;
		gap: 0.42rem;
	}

	.actions {
		position: sticky;
		bottom: 0;
		grid-template-columns: minmax(0, 1fr) auto;
		align-items: center;
		background:
			linear-gradient(180deg, rgba(255, 253, 249, 0.92), rgba(255, 253, 249, 0.98)),
			#fffdf9;
	}

	.primary-button,
	.secondary-button {
		border: none;
		border-radius: 0.95rem;
		padding: 0.72rem 1.1rem;
		font: inherit;
		font-weight: 700;
		cursor: pointer;
	}

	.primary-button {
		background: #1d9e75;
		color: #e1f5ee;
	}

	.secondary-button {
		background: #f1ece4;
		color: #4f5c65;
	}

	.primary-button:disabled,
	.secondary-button:disabled,
	.template-card:disabled,
	.section-title-input:disabled,
	textarea:disabled {
		cursor: not-allowed;
		opacity: 0.68;
	}

	@media (max-width: 820px) {
		.review-header,
		.summary-topline,
		.panel-header,
		.section-header,
		.section-title-wrap,
		.section-tags,
		.actions {
			flex-direction: column;
			align-items: stretch;
		}

		.actions {
			grid-template-columns: 1fr;
		}

		.action-buttons {
			flex-direction: column;
		}

		.action-buttons button {
			width: 100%;
		}
	}
</style>
