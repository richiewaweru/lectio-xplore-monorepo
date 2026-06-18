<script lang="ts">
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';

	import { getProfile } from '$lib/api/profile';
	import { commitPlan, listContracts, streamPlan, streamReplan } from '$lib/api/brief';
	import { ApiError } from '$lib/api/errors';
	import GenerationView from '$lib/components/studio/GenerationView.svelte';
	import IntentForm from '$lib/components/studio/IntentForm.svelte';
	import PlanReview from '$lib/components/studio/PlanReview.svelte';
	import PlanStream from '$lib/components/studio/PlanStream.svelte';
	import {
		appendPlannedSection,
		applyTeacherProfileDefaults,
		beginPlanning,
		briefDraft,
		completePlanning,
		contracts,
		editedSpec,
		failPlanning,
		generationState,
		returnToIdle,
		setContracts,
		setGenerationAccepted,
		setTemplateDecision,
		studioState
	} from '$lib/stores/studio';
	import { mergeAuthoredSections, type AuthoredSection } from '$lib/studio/template-swap';
	import type {
		PlanningErrorEvent,
		PlanningTemplateSelectedEvent,
		StudioTemplateContract
	} from '$lib/types';

	const stages = [
		{ key: 'idle', label: 'Intent capture' },
		{ key: 'planning', label: 'Plan streaming' },
		{ key: 'reviewing', label: 'Review and edit' },
		{ key: 'generating', label: 'Live generation' }
	] as const;

	let catalogError = $state<string | null>(null);
	let planningError = $state<string | null>(null);
	let commitError = $state<string | null>(null);
	let committing = $state(false);
	let swappingTemplateName = $state<string | null>(null);

	const stateSummary = $derived(
		$studioState === 'idle'
			? 'Intent capture'
			: $studioState === 'planning'
				? 'Live planning'
				: $studioState === 'reviewing'
					? 'Review gate'
					: 'Generating in place'
	);

	const currentStageIndex = $derived(stages.findIndex((stage) => stage.key === $studioState));

	function errorMessage(error: unknown, fallback: string): string {
		return error instanceof ApiError || error instanceof Error ? error.message : fallback;
	}

	async function loadContractCatalog() {
		try {
			setContracts(await listContracts());
			catalogError = null;
		} catch (error) {
			catalogError = errorMessage(error, 'Failed to load template contracts.');
		}
	}

	async function handlePlan() {
		planningError = null;
		commitError = null;
		beginPlanning();

		const request = structuredClone(get(briefDraft));
		const startedAt = performance.now();

		try {
			for await (const event of streamPlan(request)) {
				if (event.event === 'template_selected') {
					const payload = (event as PlanningTemplateSelectedEvent).data;
					setTemplateDecision(
						payload.template_decision,
						payload.lesson_rationale,
						payload.warning
					);
					continue;
				}

				if (event.event === 'section_planned') {
					appendPlannedSection(event.data.section);
					continue;
				}

				if (event.event === 'plan_complete') {
					completePlanning(event.data.spec, performance.now() - startedAt);
					if (!get(contracts).length) {
						await loadContractCatalog();
					}
					continue;
				}

				if (event.event === 'plan_error') {
					const payload = (event as PlanningErrorEvent).data;
					completePlanning(payload.spec, performance.now() - startedAt);
					failPlanning(payload.warning ?? 'Planning fell back to defaults. Review carefully.');
					if (!get(contracts).length) {
						await loadContractCatalog();
					}
					continue;
				}

				// Ignore unrecognized event types for forward compatibility
			}
		} catch (error) {
			planningError = errorMessage(
				error,
				'Planning failed before a reviewable draft was returned.'
			);
			failPlanning(planningError);
		}
	}

	async function handleTemplateSwap(contract: StudioTemplateContract) {
		const current = get(editedSpec);
		if (!current || current.template_id === contract.id) return;

		const authoredSections: AuthoredSection[] = current.sections.map((s) => ({
			order: s.order,
			title: s.title,
			focus_note: s.focus_note,
			transition_note: s.transition_note ?? null
		}));
		const originalSpec = current;

		swappingTemplateName = contract.name;
		planningError = null;
		beginPlanning();

		const startedAt = performance.now();

		try {
			for await (const event of streamReplan(current.source_brief, contract.id)) {
				if (event.event === 'template_selected') {
					const e = event as PlanningTemplateSelectedEvent;
					setTemplateDecision(e.data.template_decision, e.data.lesson_rationale, e.data.warning);
					continue;
				}
				if (event.event === 'section_planned') {
					appendPlannedSection(event.data.section);
					continue;
				}
				if (event.event === 'plan_complete') {
					const merged = mergeAuthoredSections(event.data.spec, authoredSections);
					completePlanning(merged, performance.now() - startedAt);
					continue;
				}
				if (event.event === 'plan_error') {
					const e = event as PlanningErrorEvent;
					const merged = mergeAuthoredSections(e.data.spec, authoredSections);
					completePlanning(merged, performance.now() - startedAt);
					planningError = e.data.warning ?? 'Replan fell back to defaults. Review carefully.';
					continue;
				}
			}
		} catch (error) {
			completePlanning(originalSpec, performance.now() - startedAt);
			planningError = errorMessage(error, 'Replan failed. Your original plan has been restored.');
		} finally {
			swappingTemplateName = null;
		}
	}

	async function handleCommit() {
		const spec = get(editedSpec);
		if (!spec) {
			return;
		}

		commitError = null;
		committing = true;

		try {
			const accepted = await commitPlan(spec);
			setGenerationAccepted(accepted);
			studioState.set('generating');
		} catch (error) {
			studioState.set('reviewing');
			commitError = errorMessage(error, 'Failed to start generation.');
		} finally {
			committing = false;
		}
	}

	function handleBackToBrief() {
		planningError = null;
		commitError = null;
		returnToIdle();
	}

	function handleRetryPlanning() {
		planningError = null;
		returnToIdle();
	}

	function handleResetFromGeneration() {
		planningError = null;
		commitError = null;
		returnToIdle();
	}

	onMount(() => {
		if (!get(contracts).length) {
			void loadContractCatalog();
		}
		void getProfile()
			.then((profile) => {
				applyTeacherProfileDefaults(profile);
			})
			.catch(() => {
				// Profile gating happens before Studio loads; ignore prefill failures here.
			});
	});
</script>

<section class="studio-shell" data-state={$studioState}>
	<header class="studio-header">
		<div>
			<p class="eyebrow">Studio</p>
			<h1>Teacher lesson studio</h1>
			<p class="lede">
				Capture intent, watch the plan assemble, review the exact structure, then stay inside the
				workspace while the lesson generates.
			</p>
		</div>

		<div class="studio-status">
			<span class="status-pill">{stateSummary}</span>
			<span class="catalog-pill">
				{$contracts.length || 0} live-safe template{$contracts.length === 1 ? '' : 's'}
			</span>
			<a href="/dashboard" class="dashboard-link">Back to dashboard</a>
		</div>
	</header>

	<ol class="stage-list" aria-label="Studio stages">
		{#each stages as stage, index}
			<li
				class:stage-current={index === currentStageIndex}
				class:stage-complete={index < currentStageIndex}
				class="stage-item"
			>
				<span class="stage-number">{index + 1}</span>
				<div>
					<strong>{stage.label}</strong>
					<p>{stage.key}</p>
				</div>
			</li>
		{/each}
	</ol>

	{#if catalogError && $studioState !== 'reviewing'}
		<p class="notice notice-error">{catalogError}</p>
	{/if}

	<div class="main-stage">
		{#if $studioState === 'idle'}
			<IntentForm onSubmit={handlePlan} />
		{:else if $studioState === 'planning'}
			<PlanStream errorMessage={planningError} onRetry={handleRetryPlanning} replanningFor={swappingTemplateName} />
		{:else if $studioState === 'reviewing'}
			<PlanReview
				busy={committing}
				onBack={handleBackToBrief}
				onCommit={handleCommit}
				onTemplateSwap={handleTemplateSwap}
				errorMessage={commitError}
				catalogError={catalogError}
			/>
		{:else if $generationState.accepted}
			<GenerationView accepted={$generationState.accepted} onReset={handleResetFromGeneration} />
		{/if}
	</div>
</section>

<style>
	.studio-shell {
		display: grid;
		gap: 1rem;
	}

	.studio-header,
	.studio-status {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		align-items: start;
	}

	.eyebrow {
		margin: 0 0 0.35rem 0;
		font-size: 0.76rem;
		font-weight: 700;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: #6b7c88;
	}

	h1,
	p {
		margin: 0;
	}

	h1 {
		font-size: clamp(2rem, 3vw, 2.7rem);
	}

	.lede {
		margin-top: 0.45rem;
		max-width: 62ch;
		color: #625a50;
		line-height: 1.65;
	}

	.studio-status {
		flex-wrap: wrap;
		align-items: center;
		justify-content: flex-end;
	}

	.status-pill,
	.catalog-pill,
	.dashboard-link {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border-radius: 999px;
		padding: 0.45rem 0.8rem;
		font-size: 0.8rem;
		font-weight: 700;
		text-decoration: none;
	}

	.status-pill {
		background: #e1f5ee;
		color: #085041;
	}

	.catalog-pill {
		background: #f1ece4;
		color: #4f5c65;
	}

	.dashboard-link {
		background: #f1ece4;
		color: #4f5c65;
	}

	.stage-list {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 0.75rem;
		padding: 0;
		margin: 0;
		list-style: none;
	}

	.stage-item {
		display: flex;
		gap: 0.8rem;
		align-items: center;
		border-radius: 1.1rem;
		border: 0.5px solid rgba(36, 52, 63, 0.12);
		background: #f8f4ec;
		padding: 0.85rem 0.95rem;
		color: #625a50;
	}

	.stage-item strong {
		display: block;
		color: #1d1b17;
	}

	.stage-item p {
		font-size: 0.8rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: #8a8176;
	}

	.stage-number {
		display: grid;
		place-items: center;
		width: 2rem;
		height: 2rem;
		border-radius: 999px;
		background: #fffdf9;
		color: #4f5c65;
		font-weight: 700;
	}

	.stage-current {
		border-color: rgba(29, 158, 117, 0.35);
		background: #eef8f4;
	}

	.stage-current .stage-number,
	.stage-complete .stage-number {
		background: #1d9e75;
		color: #e1f5ee;
	}

	.stage-complete {
		background: #fffdf9;
	}

	.main-stage {
		display: grid;
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

	@media (max-width: 900px) {
		.stage-list {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}

	@media (max-width: 720px) {
		.studio-header,
		.studio-status {
			flex-direction: column;
			align-items: stretch;
		}

		.stage-list {
			grid-template-columns: 1fr;
		}
	}
</style>
