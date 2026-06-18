<script lang="ts">
	import { get } from 'svelte/store';

	import { briefDraft, emptyDraft } from '$lib/stores/studio';
	import type {
		Brevity,
		ClassStyle,
		ExampleStyle,
		ExplanationStyle,
		GenerationMode,
		LearningOutcome,
		LessonFormat,
		ReadingLevel,
		Tone,
		TopicType,
		UserBriefDraft
	} from '$lib/types';

	interface Props {
		disabled?: boolean;
		onSubmit: () => void;
	}

	type SignalKey = keyof UserBriefDraft['signals'];
	type PreferenceKey = keyof UserBriefDraft['preferences'];
	type ConstraintKey = keyof UserBriefDraft['constraints'];

	const defaultDraft = emptyDraft();

	let { disabled = false, onSubmit }: Props = $props();
	let showPriorKnowledge = $state(
		Boolean($briefDraft.prior_knowledge.trim() || $briefDraft.extra_context.trim())
	);
	let showPreferences = $state(hasCustomPreferences($briefDraft));
	let validationMessage = $state<string | null>(null);
	let signalWarning = $state<string | null>(null);

	const topicTypes: Array<{ label: string; value: TopicType }> = [
		{ label: 'Concept / idea', value: 'concept' },
		{ label: 'Step-by-step process', value: 'process' },
		{ label: 'Facts to remember', value: 'facts' },
		{ label: 'Mixed', value: 'mixed' }
	];

	const learningOutcomes: Array<{ label: string; value: LearningOutcome }> = [
		{ label: 'Understand why it works', value: 'understand-why' },
		{ label: 'Be able to do it themselves', value: 'be-able-to-do' },
		{ label: 'Remember key terms', value: 'remember-terms' },
		{ label: 'Apply to a new situation', value: 'apply-to-new' }
	];

	const classStyles: Array<{ label: string; value: ClassStyle }> = [
		{ label: 'Needs explanation first', value: 'needs-explanation-first' },
		{ label: 'Tries before being told', value: 'tries-before-told' },
		{ label: 'Gets restless without activity', value: 'restless-without-activity' },
		{ label: 'Responds to visuals', value: 'engages-with-visuals' },
		{ label: 'Likes worked examples', value: 'responds-to-worked-examples' }
	];

	const formats: Array<{ label: string; value: LessonFormat }> = [
		{ label: 'Printed booklet', value: 'printed-booklet' },
		{ label: 'Screen-based', value: 'screen-based' },
		{ label: 'Both', value: 'both' }
	];

	const tones: Array<{ label: string; value: Tone }> = [
		{ label: 'Supportive', value: 'supportive' },
		{ label: 'Neutral', value: 'neutral' },
		{ label: 'Rigorous', value: 'rigorous' }
	];

	const readingLevels: Array<{ label: string; value: ReadingLevel }> = [
		{ label: 'Simple', value: 'simple' },
		{ label: 'Standard', value: 'standard' },
		{ label: 'Advanced', value: 'advanced' }
	];

	const explanationStyles: Array<{ label: string; value: ExplanationStyle }> = [
		{ label: 'Concrete examples first', value: 'concrete-first' },
		{ label: 'Concept first', value: 'concept-first' },
		{ label: 'Balanced', value: 'balanced' }
	];

	const exampleStyles: Array<{ label: string; value: ExampleStyle }> = [
		{ label: 'Everyday examples', value: 'everyday' },
		{ label: 'Academic examples', value: 'academic' },
		{ label: 'Exam-style examples', value: 'exam' }
	];

	const brevityOptions: Array<{ label: string; value: Brevity }> = [
		{ label: 'Concise', value: 'tight' },
		{ label: 'Balanced', value: 'balanced' },
		{ label: 'Expanded', value: 'expanded' }
	];

	const generationModes: Array<{
		label: string;
		value: GenerationMode;
		hint: string;
	}> = [
		{
			label: 'Draft - Fast preview for planning',
			value: 'draft',
			hint: 'Static printable lessons, fastest generation, best for quick iteration.'
		},
		{
			label: 'Balanced - Recommended default',
			value: 'balanced',
			hint: 'Interactive-capable output with the standard speed and quality balance.'
		},
		{
			label: 'Strict - Maximum quality for critical content',
			value: 'strict',
			hint: 'Highest-quality generation path with the largest retry budget.'
		}
	];

	function hasAnySignals(draft: UserBriefDraft): boolean {
		return Boolean(
			draft.signals.topic_type ||
				draft.signals.learning_outcome ||
				draft.signals.format ||
				draft.signals.class_style.length
		);
	}

	function hasCustomPreferences(draft: UserBriefDraft): boolean {
		return (
			draft.preferences.tone !== defaultDraft.preferences.tone ||
			draft.preferences.reading_level !== defaultDraft.preferences.reading_level ||
			draft.preferences.explanation_style !== defaultDraft.preferences.explanation_style ||
			draft.preferences.example_style !== defaultDraft.preferences.example_style ||
			draft.preferences.brevity !== defaultDraft.preferences.brevity
		);
	}

	$effect(() => {
		if ($briefDraft.prior_knowledge.trim() || $briefDraft.extra_context.trim()) {
			showPriorKnowledge = true;
		}
		if (hasCustomPreferences($briefDraft)) {
			showPreferences = true;
		}
	});

	function updateBrief(patch: Partial<UserBriefDraft>) {
		briefDraft.update((draft) => ({
			...draft,
			...patch
		}));
		validationMessage = null;
	}

	function updateSignals<K extends SignalKey>(key: K, value: UserBriefDraft['signals'][K]) {
		briefDraft.update((draft) => {
			const nextDraft = {
				...draft,
				signals: {
					...draft.signals,
					[key]: value
				}
			};
			signalWarning = hasAnySignals(nextDraft) ? null : signalWarning;
			return nextDraft;
		});
	}

	function updatePreferences<K extends PreferenceKey>(
		key: K,
		value: UserBriefDraft['preferences'][K]
	) {
		briefDraft.update((draft) => ({
			...draft,
			preferences: {
				...draft.preferences,
				[key]: value
			}
		}));
	}

	function updateConstraints<K extends ConstraintKey>(
		key: K,
		value: UserBriefDraft['constraints'][K]
	) {
		briefDraft.update((draft) => ({
			...draft,
			constraints: {
				...draft.constraints,
				[key]: value
			}
		}));
	}

	function toggleClassStyle(value: ClassStyle) {
		const current = get(briefDraft).signals.class_style;
		if (current.includes(value)) {
			updateSignals(
				'class_style',
				current.filter((item) => item !== value)
			);
			return;
		}
		if (current.length >= 3) {
			return;
		}
		updateSignals('class_style', [...current, value]);
	}

	function clearDraft() {
		briefDraft.set(emptyDraft());
		showPriorKnowledge = false;
		showPreferences = false;
		validationMessage = null;
		signalWarning = null;
	}

	function classStyleLocked(value: ClassStyle): boolean {
		const current = $briefDraft.signals.class_style;
		return current.length >= 3 && !current.includes(value);
	}

	function handleSubmit(event: SubmitEvent) {
		event.preventDefault();

		const draft = get(briefDraft);
		if (!draft.intent.trim() || !draft.audience.trim()) {
			validationMessage = 'Intent and audience are both required before planning can start.';
			return;
		}

		validationMessage = null;
		signalWarning = hasAnySignals(draft)
			? null
			: 'No learning signals were selected, so planning will fall back to defaults. You can still continue.';
		onSubmit();
	}
</script>

<form class="studio-form" onsubmit={handleSubmit}>
	<section class="form-card">
		<header class="heading">
			<div>
				<p class="eyebrow">Intent capture</p>
				<h2>Shape the lesson before generation</h2>
				<p class="lede">
					Give the planner the topic, the class context, and a few learning signals. We keep the
					draft intact if you come back to refine it.
				</p>
			</div>
			<div class="draft-note">Draft restored automatically when you return from review.</div>
		</header>

		{#if validationMessage}
			<p class="notice notice-error" role="alert">{validationMessage}</p>
		{/if}

		{#if signalWarning}
			<p class="notice notice-warn" role="status">{signalWarning}</p>
		{/if}

		<div class="field-grid">
			<label class="field field-wide">
				<span>What do you want to teach?</span>
				<input
					type="text"
					value={$briefDraft.intent}
					placeholder="What do you want to teach?"
					oninput={(event) =>
						updateBrief({ intent: (event.currentTarget as HTMLInputElement).value })}
					disabled={disabled}
				/>
			</label>

			<label class="field field-wide">
				<span>Who is this for?</span>
				<input
					type="text"
					value={$briefDraft.audience}
					placeholder="Who is this for? Grade, ability, any notes."
					oninput={(event) =>
						updateBrief({ audience: (event.currentTarget as HTMLInputElement).value })}
					disabled={disabled}
				/>
			</label>

			<label class="field">
				<span>Generation mode</span>
				<select
					value={$briefDraft.mode}
					onchange={(event) =>
						updateBrief({
							mode: (event.currentTarget as HTMLSelectElement).value as GenerationMode
						})}
					disabled={disabled}
				>
					{#each generationModes as option}
						<option value={option.value}>{option.label}</option>
					{/each}
				</select>
				<span class="hint">{generationModes.find((option) => option.value === $briefDraft.mode)?.hint}</span>
			</label>
		</div>

		<button class="toggle-link" type="button" onclick={() => (showPriorKnowledge = !showPriorKnowledge)}>
			{showPriorKnowledge ? '-' : '+'} Prior knowledge and extra context
		</button>

		{#if showPriorKnowledge}
			<div class="field-grid">
				<label class="field">
					<span>Prior knowledge</span>
					<textarea
						rows="3"
						value={$briefDraft.prior_knowledge}
						placeholder="What do students already know? (optional)"
						oninput={(event) =>
							updateBrief({
								prior_knowledge: (event.currentTarget as HTMLTextAreaElement).value
							})}
						disabled={disabled}
					></textarea>
				</label>

				<label class="field">
					<span>Extra context</span>
					<textarea
						rows="3"
						value={$briefDraft.extra_context}
						placeholder="Any extra context or lesson constraints? (optional)"
						oninput={(event) =>
							updateBrief({
								extra_context: (event.currentTarget as HTMLTextAreaElement).value
							})}
						disabled={disabled}
					></textarea>
				</label>
			</div>
		{/if}

		<div class="signal-stack">
			<div class="signal-block">
				<p class="signal-title">Topic type</p>
				<div class="chip-row">
					{#each topicTypes as option}
						<button
							type="button"
							class:chip-selected={$briefDraft.signals.topic_type === option.value}
							class="chip"
							onclick={() => updateSignals('topic_type', option.value)}
						>
							{option.label}
						</button>
					{/each}
				</div>
			</div>

			<div class="signal-block">
				<p class="signal-title">What should students leave with?</p>
				<div class="chip-row">
					{#each learningOutcomes as option}
						<button
							type="button"
							class:chip-selected={$briefDraft.signals.learning_outcome === option.value}
							class="chip"
							onclick={() => updateSignals('learning_outcome', option.value)}
						>
							{option.label}
						</button>
					{/each}
				</div>
			</div>

			<div class="signal-block">
				<div class="signal-header">
					<p class="signal-title">How does this class learn?</p>
					<p class="helper">Select up to 3</p>
				</div>
				<div class="chip-row">
					{#each classStyles as option}
						<button
							type="button"
							class:chip-selected={$briefDraft.signals.class_style.includes(option.value)}
							class:chip-disabled={classStyleLocked(option.value)}
							class="chip"
							onclick={() => toggleClassStyle(option.value)}
							disabled={classStyleLocked(option.value)}
						>
							{option.label}
						</button>
					{/each}
				</div>
			</div>

			<div class="signal-block">
				<p class="signal-title">Format</p>
				<div class="chip-row">
					{#each formats as option}
						<button
							type="button"
							class:chip-selected={$briefDraft.signals.format === option.value}
							class="chip"
							onclick={() => updateSignals('format', option.value)}
						>
							{option.label}
						</button>
					{/each}
				</div>
			</div>
		</div>

		<button class="toggle-link" type="button" onclick={() => (showPreferences = !showPreferences)}>
			{showPreferences ? '-' : '+'} Tone and style preferences (optional)
		</button>

		{#if showPreferences}
			<div class="preference-grid">
				<label class="field">
					<span>Tone</span>
					<select
						value={$briefDraft.preferences.tone}
						onchange={(event) =>
							updatePreferences('tone', (event.currentTarget as HTMLSelectElement).value as Tone)}
					>
						{#each tones as option}
							<option value={option.value}>{option.label}</option>
						{/each}
					</select>
				</label>

				<label class="field">
					<span>Reading level</span>
					<select
						value={$briefDraft.preferences.reading_level}
						onchange={(event) =>
							updatePreferences(
								'reading_level',
								(event.currentTarget as HTMLSelectElement).value as ReadingLevel
							)}
					>
						{#each readingLevels as option}
							<option value={option.value}>{option.label}</option>
						{/each}
					</select>
				</label>

				<label class="field">
					<span>Explanation style</span>
					<select
						value={$briefDraft.preferences.explanation_style}
						onchange={(event) =>
							updatePreferences(
								'explanation_style',
								(event.currentTarget as HTMLSelectElement).value as ExplanationStyle
							)}
					>
						{#each explanationStyles as option}
							<option value={option.value}>{option.label}</option>
						{/each}
					</select>
				</label>

				<label class="field">
					<span>Example style</span>
					<select
						value={$briefDraft.preferences.example_style}
						onchange={(event) =>
							updatePreferences(
								'example_style',
								(event.currentTarget as HTMLSelectElement).value as ExampleStyle
							)}
					>
						{#each exampleStyles as option}
							<option value={option.value}>{option.label}</option>
						{/each}
					</select>
				</label>

				<label class="field">
					<span>Brevity</span>
					<select
						value={$briefDraft.preferences.brevity}
						onchange={(event) =>
							updatePreferences(
								'brevity',
								(event.currentTarget as HTMLSelectElement).value as Brevity
							)}
					>
						{#each brevityOptions as option}
							<option value={option.value}>{option.label}</option>
						{/each}
					</select>
				</label>
			</div>
		{/if}

		<div class="constraint-row">
			<label class="toggle">
				<input
					type="checkbox"
					checked={$briefDraft.constraints.more_practice}
					onchange={(event) =>
						updateConstraints('more_practice', (event.currentTarget as HTMLInputElement).checked)}
				/>
				<span>Emphasise practice</span>
			</label>

			<label class="toggle">
				<input
					type="checkbox"
					checked={$briefDraft.constraints.keep_short}
					onchange={(event) =>
						updateConstraints('keep_short', (event.currentTarget as HTMLInputElement).checked)}
				/>
				<span>Keep it short</span>
			</label>

			<label class="toggle">
				<input
					type="checkbox"
					checked={$briefDraft.constraints.use_visuals}
					onchange={(event) =>
						updateConstraints('use_visuals', (event.currentTarget as HTMLInputElement).checked)}
				/>
				<span>Include visuals wherever possible</span>
			</label>

			<label class="toggle">
				<input
					type="checkbox"
					checked={$briefDraft.constraints.print_first}
					onchange={(event) =>
						updateConstraints('print_first', (event.currentTarget as HTMLInputElement).checked)}
				/>
				<span>Optimise for print layout</span>
			</label>
		</div>

		<div class="actions">
			<button class="secondary-button" type="button" onclick={clearDraft} disabled={disabled}>
				Clear draft
			</button>
			<button class="primary-button" type="submit" disabled={disabled}>
				Build lesson plan ->
			</button>
		</div>
	</section>
</form>

<style>
	.studio-form {
		display: grid;
	}

	.form-card {
		display: grid;
		gap: 1rem;
		border: 0.5px solid rgba(36, 52, 63, 0.12);
		border-radius: 1.35rem;
		background: #fffdf9;
		padding: 1.3rem;
	}

	.heading {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		align-items: start;
	}

	.heading h2,
	.heading p {
		margin: 0;
	}

	.eyebrow,
	.signal-title,
	.field span {
		font-size: 0.78rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	.eyebrow {
		margin: 0 0 0.35rem 0;
		color: #6b7c88;
	}

	.lede {
		margin-top: 0.45rem;
		max-width: 62ch;
		color: #5f584f;
		line-height: 1.6;
	}

	.draft-note {
		max-width: 18rem;
		border-radius: 0.95rem;
		background: #f6f2ea;
		padding: 0.8rem 0.9rem;
		color: #6e665c;
		font-size: 0.85rem;
		line-height: 1.5;
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

	.field-grid,
	.preference-grid {
		display: grid;
		gap: 0.9rem;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
	}

	.field {
		display: grid;
		gap: 0.42rem;
	}

	.field-wide {
		grid-column: 1 / -1;
	}

	.field span,
	.signal-title {
		color: #24343f;
	}

	.hint {
		font-size: 0.82rem;
		color: #6e665c;
		line-height: 1.5;
	}

	input,
	textarea,
	select {
		border: 0.5px solid rgba(36, 52, 63, 0.14);
		border-radius: 0.9rem;
		padding: 0.75rem 0.85rem;
		font: inherit;
		background: #f8f4ec;
		color: #1d1b17;
	}

	textarea {
		resize: vertical;
	}

	input:focus,
	textarea:focus,
	select:focus {
		outline: 2px solid rgba(29, 158, 117, 0.18);
		outline-offset: 1px;
		border-color: rgba(29, 158, 117, 0.42);
	}

	.toggle-link {
		justify-self: start;
		border: none;
		background: transparent;
		padding: 0;
		color: #0b6a52;
		font: inherit;
		font-weight: 700;
		cursor: pointer;
	}

	.signal-stack {
		display: grid;
		gap: 0.8rem;
	}

	.signal-block {
		display: grid;
		gap: 0.55rem;
		border-radius: 1rem;
		background: #f4efe6;
		padding: 0.95rem;
	}

	.signal-header {
		display: flex;
		justify-content: space-between;
		gap: 0.8rem;
		align-items: baseline;
	}

	.chip-row {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}

	.chip {
		border: 0.5px solid rgba(36, 52, 63, 0.16);
		border-radius: 999px;
		background: #fffdf9;
		padding: 0.38rem 0.82rem;
		font: inherit;
		font-size: 0.84rem;
		color: #4f5c65;
		cursor: pointer;
		transition:
			border-color 140ms ease,
			background-color 140ms ease,
			color 140ms ease;
	}

	.chip:hover:not(:disabled) {
		border-color: rgba(29, 158, 117, 0.3);
	}

	.chip-selected {
		border-color: #1d9e75;
		background: #e1f5ee;
		color: #085041;
	}

	.chip-disabled,
	.chip:disabled {
		cursor: not-allowed;
		opacity: 0.48;
	}

	.helper {
		margin: 0;
		font-size: 0.8rem;
		color: #72695f;
	}

	.constraint-row {
		display: flex;
		flex-wrap: wrap;
		gap: 0.9rem 1.25rem;
		padding-top: 0.1rem;
	}

	.toggle {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		color: #24343f;
	}

	.toggle input {
		margin: 0;
		accent-color: #1d9e75;
	}

	.actions {
		display: flex;
		justify-content: space-between;
		gap: 0.8rem;
		align-items: center;
		padding-top: 0.15rem;
	}

	.primary-button,
	.secondary-button {
		border: none;
		border-radius: 0.95rem;
		padding: 0.72rem 1.15rem;
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
	input:disabled,
	textarea:disabled,
	select:disabled {
		cursor: not-allowed;
		opacity: 0.68;
	}

	@media (max-width: 720px) {
		.heading,
		.signal-header,
		.actions {
			flex-direction: column;
			align-items: stretch;
		}

		.draft-note {
			max-width: none;
		}

		.actions button {
			width: 100%;
		}
	}
</style>
