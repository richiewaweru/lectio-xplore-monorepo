<script lang="ts">
	import { planDraft } from '$lib/stores/studio';
	import { componentLabel, roleLabel, roleTone, visualPolicyLabel } from '$lib/studio/presentation';

	interface Props {
		errorMessage?: string | null;
		onRetry?: () => void;
		replanningFor?: string | null;
	}

	let { errorMessage = null, onRetry = () => {}, replanningFor = null }: Props = $props();

	const progressValue = $derived.by(() => {
		if ($planDraft.is_complete) {
			return 100;
		}
		if (errorMessage) {
			return Math.max(26, Math.min(84, 18 + $planDraft.sections.length * 14));
		}
		if (!$planDraft.template_decision) {
			return 18;
		}
		return Math.min(86, 34 + $planDraft.sections.length * 15);
	});

	const pendingLabel = $derived(
		$planDraft.sections.length
			? `Planning section ${$planDraft.sections.length + 1}...`
			: 'Selecting the opening section...'
	);
</script>

<section class="planning-shell" aria-live="polite">
	<header class="planning-header">
		<div>
			<p class="eyebrow">Planning</p>
			<h2>Building the lesson structure in view</h2>
			<p class="lede">
				The planner chooses a template first, then lays down the sections one by one so the wait
				reads as visible progress instead of a blank pause.
			</p>
		</div>
		<div class="status-pill">
			<span class="pulse-dot"></span>
			<span>{errorMessage ? 'Planning interrupted' : 'Live planning'}</span>
		</div>
	</header>

	<section class="template-panel">
		<div class="status-row">
			<div class="planning-copy">
				<span class="pulse-dot"></span>
				<span>{errorMessage ? 'Planning paused' : 'Building your lesson plan...'}</span>
			</div>
			<span class="status-caption">
				{$planDraft.sections.length} section{$planDraft.sections.length === 1 ? '' : 's'} outlined
			</span>
		</div>
		<div class="progress-bar-bg" aria-hidden="true">
			<div class="progress-bar-fill" style={`width:${progressValue}%`}></div>
		</div>

		{#if $planDraft.template_decision}
			<div class="template-badge">
				<div>
					<div class="template-name-row">
						<h3>{$planDraft.template_decision.chosen_name}</h3>
						<span class="fit-pill">Best fit</span>
					</div>
					<p class="template-rationale">
						{$planDraft.lesson_rationale || $planDraft.template_decision.rationale}
					</p>
				</div>
				<div class="template-score">{$planDraft.template_decision.fit_score.toFixed(2)}</div>
			</div>
		{:else}
			<div class="template-loading" aria-busy="true">
				<div class="skeleton-line short"></div>
				<div class="skeleton-line"></div>
			</div>
		{/if}

		{#if $planDraft.warning}
			<p class="notice notice-warn">{$planDraft.warning}</p>
		{/if}

		{#if errorMessage}
			<div class="error-panel" role="alert">
				<div>
					<h3>Something went wrong building your plan.</h3>
					<p>
						{errorMessage} Return to the brief, keep your draft, and try the planner again.
					</p>
				</div>
				<button class="retry-button" type="button" onclick={onRetry}>Try again</button>
			</div>
		{/if}
	</section>

	<section class="section-panel">
		<div class="section-panel-header">
			<div>
				<p class="label">Sections</p>
				<h3>{replanningFor ? `Replanning for ${replanningFor}…` : 'Arriving now'}</h3>
			</div>
			<p class="status-caption">Each section appears as soon as its structure is ready.</p>
		</div>

		<div class="section-list">
			{#if $planDraft.sections.length}
				{#each $planDraft.sections as section, index (section.id)}
					<article
						class:section-row-new={index === $planDraft.sections.length - 1 && !errorMessage}
						class="section-row"
					>
						<div class="section-order">{String(section.order).padStart(2, '0')}</div>
						<div class="section-copy">
							<div class="section-topline">
								<h4>{section.title}</h4>
								<span class={`role-pill role-${roleTone(section.role)}`}>{roleLabel(section.role)}</span>
							</div>
							<p>{section.objective || section.rationale}</p>
							<div class="chip-row">
								{#each section.selected_components as component}
									<span class="component-chip">{componentLabel(component)}</span>
								{/each}
								{#if visualPolicyLabel(section.visual_policy)}
									<span class="visual-chip">{visualPolicyLabel(section.visual_policy)}</span>
								{/if}
							</div>
						</div>
					</article>
				{/each}
			{:else}
				{#each Array.from({ length: 2 }) as _, index}
					<article class="section-row section-row-loading" aria-busy="true">
						<div class="section-order">{String(index + 1).padStart(2, '0')}</div>
						<div class="section-copy">
							<div class="skeleton-line short"></div>
							<div class="skeleton-line"></div>
						</div>
					</article>
				{/each}
			{/if}

			{#if !errorMessage}
				<article class="section-row section-row-pending" aria-busy="true">
					<div class="section-order section-order-pending">..</div>
					<div class="section-copy">
						<div class="section-topline">
							<h4>{pendingLabel}</h4>
							<span class="pending-pill">Pending</span>
						</div>
						<p>The next section placeholder stays visible so the remaining planning latency is readable.</p>
					</div>
				</article>
			{/if}
		</div>
	</section>
</section>

<style>
	.planning-shell {
		display: grid;
		gap: 1rem;
	}

	.planning-header,
	.status-row,
	.template-badge,
	.section-panel-header,
	.section-topline,
	.error-panel {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		align-items: start;
	}

	.eyebrow,
	.label {
		margin: 0;
		font-size: 0.76rem;
		font-weight: 700;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: #6b7c88;
	}

	h2,
	h3,
	h4,
	p {
		margin: 0;
	}

	.lede,
	.template-rationale,
	.section-copy p,
	.status-caption {
		color: #625a50;
		line-height: 1.6;
	}

	.status-pill,
	.planning-copy,
	.fit-pill,
	.pending-pill,
	.template-score {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		border-radius: 999px;
		padding: 0.38rem 0.72rem;
		font-size: 0.78rem;
		font-weight: 700;
	}

	.status-pill,
	.fit-pill {
		background: #e1f5ee;
		color: #085041;
	}

	.pending-pill,
	.template-score {
		background: #f1ece4;
		color: #4f5c65;
	}

	.pulse-dot {
		width: 0.55rem;
		height: 0.55rem;
		border-radius: 999px;
		background: #1d9e75;
		animation: pulse 1.2s ease-in-out infinite;
	}

	.template-panel,
	.section-panel {
		display: grid;
		gap: 0.9rem;
		border: 0.5px solid rgba(36, 52, 63, 0.12);
		border-radius: 1.35rem;
		background: #fffdf9;
		padding: 1.1rem;
	}

	.progress-bar-bg {
		height: 0.22rem;
		border-radius: 999px;
		background: #efe8dc;
		overflow: hidden;
	}

	.progress-bar-fill {
		height: 100%;
		border-radius: inherit;
		background: #1d9e75;
		transition: width 200ms ease;
	}

	.template-name-row {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem;
		align-items: center;
	}

	.template-loading,
	.section-row-loading {
		display: grid;
		gap: 0.6rem;
	}

	.notice {
		border-radius: 0.95rem;
		padding: 0.85rem 0.95rem;
	}

	.notice-warn {
		background: #fff8e4;
		color: #805d16;
	}

	.error-panel {
		border-radius: 1rem;
		background: #fff2ee;
		padding: 0.95rem;
		color: #7d3524;
	}

	.error-panel h3 {
		margin-bottom: 0.28rem;
		font-size: 1rem;
	}

	.retry-button {
		border: none;
		border-radius: 0.9rem;
		background: #1d9e75;
		padding: 0.72rem 1rem;
		color: #e1f5ee;
		font: inherit;
		font-weight: 700;
		cursor: pointer;
	}

	.section-list {
		display: grid;
		gap: 0.75rem;
	}

	.section-row {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.9rem;
		border-radius: 1rem;
		border: 0.5px solid rgba(36, 52, 63, 0.08);
		background: #f9f6f0;
		padding: 0.9rem;
	}

	.section-row-new {
		border-color: rgba(29, 158, 117, 0.35);
		background: #eef8f4;
		animation: section-arrive 0.28s ease;
	}

	.section-row-pending {
		opacity: 0.7;
	}

	.section-order {
		display: grid;
		place-items: center;
		width: 2.45rem;
		height: 2.45rem;
		border-radius: 999px;
		background: #eef8f4;
		color: #0b6a52;
		font-size: 0.82rem;
		font-weight: 700;
	}

	.section-order-pending {
		background: #f1ece4;
		color: #70695f;
	}

	.section-copy {
		display: grid;
		gap: 0.45rem;
	}

	.chip-row {
		display: flex;
		flex-wrap: wrap;
		gap: 0.45rem;
	}

	.component-chip,
	.visual-chip,
	.role-pill {
		display: inline-flex;
		align-items: center;
		border-radius: 999px;
		padding: 0.25rem 0.6rem;
		font-size: 0.74rem;
		font-weight: 700;
	}

	.component-chip {
		background: #ffffff;
		color: #4f5c65;
		border: 0.5px solid rgba(36, 52, 63, 0.1);
	}

	.visual-chip {
		background: #fff8e4;
		color: #805d16;
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

	.skeleton-line {
		height: 0.82rem;
		border-radius: 999px;
		background: linear-gradient(90deg, #ece4d6, #f8f4ec, #ece4d6);
		background-size: 200% 100%;
		animation: shimmer 1.25s linear infinite;
	}

	.skeleton-line.short {
		width: 56%;
	}

	@keyframes pulse {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.3;
		}
	}

	@keyframes shimmer {
		from {
			background-position: 200% 0;
		}
		to {
			background-position: -200% 0;
		}
	}

	@keyframes section-arrive {
		from {
			opacity: 0;
			transform: translateY(6px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.pulse-dot,
		.skeleton-line,
		.section-row-new {
			animation: none;
		}
	}

	@media (max-width: 720px) {
		.planning-header,
		.status-row,
		.template-badge,
		.section-panel-header,
		.section-topline,
		.error-panel {
			flex-direction: column;
		}

		.retry-button {
			width: 100%;
		}
	}
</style>
