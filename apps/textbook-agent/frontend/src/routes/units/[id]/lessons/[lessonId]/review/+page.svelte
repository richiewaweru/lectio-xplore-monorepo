<script lang="ts">
	import { getContext, onDestroy, onMount } from 'svelte';
	import {
		getReviewDraft,
		regenerateSharedDocument,
		saveReviewDraftRevision,
		submitReviewDraft
	} from '$lib/api/shared-documents';
	import { isApiError } from '$lib/api/errors';
	import type { PathLesson, PreparedLessonStatus, Unit, UnitPath } from '$lib/types/units';
	import { Badge, Button, EmptyState, InlineError } from '$lib/ui';
	import { lessonWorkspaceHref } from '$lib/curriculum/lessons/lesson-context';
	import { createSerializedPoll } from '$lib/curriculum/lessons/serialized-poll';
	import {
		buildReviewDraftEdits,
		editableFieldsForDocument,
		fieldKey,
		issueLabel,
		issueNodeIds,
		type ContinuityIssue,
		type EditableField,
		type SharedLessonDocument,
		type SharedNode,
		type SharedSection
	} from '$lib/curriculum/lessons/review-draft';
	import type { ReviewDraftIdentity } from '$lib/api/shared-documents';

	type Ctx = {
		unitId: string;
		lessonId: string;
		unit: Unit | null;
		path: UnitPath | null;
		lesson: PathLesson | null;
		preparation: PreparedLessonStatus | null;
		statusFresh: boolean;
		statusError: string | null;
		refreshPreparation: () => Promise<void>;
	};

	const ctx = getContext<Ctx>('lessonWorkspace');

	let runId = $state<string | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let notice = $state<string | null>(null);
	let document = $state<SharedLessonDocument | null>(null);
	let issues = $state<ContinuityIssue[]>([]);
	let draft = $state<ReviewDraftIdentity | null>(null);
	let baselineFields = $state<EditableField[]>([]);
	let values = $state<Record<string, string>>({});
	let saving = $state(false);
	let submitting = $state(false);
	let regenerating = $state(false);
	let phase = $state<'editing' | 'rechecking' | 'ready' | 'needs_review_again' | 'failed'>('editing');

	const flaggedNodeIds = $derived(issueNodeIds(issues));
	const issuesBySection = $derived.by(() => {
		const grouped = new Map<string, ContinuityIssue[]>();
		for (const issue of issues) {
			const list = grouped.get(issue.affected_section_id) ?? [];
			list.push(issue);
			grouped.set(issue.affected_section_id, list);
		}
		return grouped;
	});
	const pendingEdits = $derived(
		buildReviewDraftEdits(baselineFields, new Map(Object.entries(values)))
	);
	const hasUnsavedChanges = $derived(pendingEdits.length > 0);

	function resolveRunId(): string | null {
		const workspace = ctx.preparation?.workspace;
		return workspace?.learn?.shared_document_run_id ?? workspace?.print?.shared_document_run_id ?? null;
	}

	function applyDraft(next: { document: SharedLessonDocument; issues: ContinuityIssue[]; draft: ReviewDraftIdentity }): void {
		document = next.document;
		issues = next.issues;
		draft = next.draft;
		baselineFields = editableFieldsForDocument(next.document);
		values = Object.fromEntries(baselineFields.map((field) => [field.key, field.value]));
	}

	async function loadDraft(): Promise<void> {
		if (!runId) return;
		const response = await getReviewDraft(runId);
		applyDraft(response);
	}

	async function resolveAndLoad(): Promise<void> {
		loading = true;
		error = null;
		try {
			await ctx.refreshPreparation();
			runId = resolveRunId();
			if (!runId) {
				error = 'No review draft is available for this lesson.';
				return;
			}
			await loadDraft();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not load the review draft.';
		} finally {
			loading = false;
		}
	}

	async function saveDraft(): Promise<void> {
		if (!runId || !draft || !hasUnsavedChanges) return;
		saving = true;
		notice = null;
		error = null;
		try {
			const response = await saveReviewDraftRevision(runId, {
				expected_revision: draft.revision,
				expected_hash: draft.hash,
				edits: pendingEdits
			});
			applyDraft(response);
			notice = 'Draft saved.';
		} catch (err) {
			if (isApiError(err) && err.status === 409) {
				try {
					await loadDraft();
					error = 'Someone or something else changed this draft. It has been reloaded with the latest content — please redo your edits.';
				} catch (reloadErr) {
					error = reloadErr instanceof Error ? reloadErr.message : 'Could not reload the review draft.';
				}
			} else {
				error = err instanceof Error ? err.message : 'Could not save the review draft.';
			}
		} finally {
			saving = false;
		}
	}

	const recheckPoll = createSerializedPoll(async () => {
		try {
			await ctx.refreshPreparation();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not refresh lesson status.';
			return false;
		}
		const workspace = ctx.preparation?.workspace;
		const state = workspace?.learn?.shared_document_state ?? workspace?.print?.shared_document_state;
		if (state === 'ready') {
			phase = 'ready';
			return false;
		}
		if (state === 'needs_review') {
			phase = 'needs_review_again';
			// A regenerated document is a new run; follow it.
			runId = resolveRunId() ?? runId;
			void loadDraft().catch((err) => {
				error = err instanceof Error ? err.message : 'Could not reload the review draft.';
			});
			return false;
		}
		if (state === 'failed') {
			phase = 'failed';
			return false;
		}
		return true;
	}, 2000);

	async function submitDraft(): Promise<void> {
		if (!runId || !draft || hasUnsavedChanges) return;
		submitting = true;
		error = null;
		notice = null;
		try {
			await submitReviewDraft(runId, { expected_revision: draft.revision, expected_hash: draft.hash });
			phase = 'rechecking';
			recheckPoll.start();
		} catch (err) {
			if (isApiError(err) && err.status === 409) {
				await loadDraft();
				error = 'This draft changed since you loaded it. Please review the latest content before submitting.';
			} else {
				error = err instanceof Error ? err.message : 'Could not submit the review draft.';
			}
		} finally {
			submitting = false;
		}
	}

	async function regenerateDocument(): Promise<void> {
		if (!runId || regenerating) return;
		const confirmed = window.confirm(
			'Regenerate this lesson document from the approved plan? Unsubmitted edits here will be discarded, and a new document will be written and checked.'
		);
		if (!confirmed) return;
		regenerating = true;
		error = null;
		notice = null;
		try {
			await regenerateSharedDocument(runId);
			phase = 'rechecking';
			recheckPoll.start();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not regenerate the lesson document.';
		} finally {
			regenerating = false;
		}
	}

	function setValue(key: string, next: string): void {
		values = { ...values, [key]: next };
	}

	function fieldsFor(section: SharedSection, node: SharedNode): EditableField[] {
		return baselineFields.filter((field) => field.section_id === section.id && field.node_id === node.id);
	}

	function accessibilityField(section: SharedSection, node: SharedNode): EditableField | undefined {
		return fieldsFor(section, node).find((field) => field.field === 'accessibility_description');
	}

	function nonAccessibilityFields(section: SharedSection, node: SharedNode): EditableField[] {
		return fieldsFor(section, node).filter((field) => field.field !== 'accessibility_description');
	}

	onMount(() => void resolveAndLoad());
	onDestroy(() => recheckPoll.stop());
</script>

<div class="review-ws">
	<header class="bar">
		<div>
			<h1>Review flagged content</h1>
			{#if ctx.lesson}<p class="lesson-title">{ctx.lesson.title}</p>{/if}
		</div>
		<a class="link" href={lessonWorkspaceHref(ctx.unitId, ctx.lessonId, 'plan')}>Back to lesson</a>
	</header>

	{#if ctx.statusError}
		<InlineError message={`Lesson status is stale: ${ctx.statusError}`} hint="Refresh the lesson workspace before editing." />
	{/if}
	{#if error}<InlineError message={error} />{/if}
	{#if notice}<p class="notice" role="status">{notice}</p>{/if}

	{#if loading}
		<p class="muted">Loading review draft…</p>
	{:else if phase === 'rechecking'}
		<EmptyState title="Re-checking…" description="Your corrections are being re-validated. This page updates automatically when the result is known." />
	{:else if phase === 'ready'}
		<EmptyState title="This lesson document is now ready" description="Quality checks passed. Learn and Print can now be generated or refreshed from this document.">
			{#snippet actions()}
				<a class="link" href={lessonWorkspaceHref(ctx.unitId, ctx.lessonId, 'learn')}>Go to Learn</a>
				<a class="link" href={lessonWorkspaceHref(ctx.unitId, ctx.lessonId, 'print')}>Go to Print</a>
			{/snippet}
		</EmptyState>
	{:else if phase === 'failed'}
		<EmptyState title="Re-check failed" description="The re-validation run failed. Return to the lesson to see its current state." />
	{:else if !document}
		<EmptyState title="No review draft available" description={error ?? 'There is nothing to review for this lesson right now.'} />
	{:else}
		{#if phase === 'needs_review_again'}
			<InlineError message="Quality checks flagged new issues after re-checking. Please review them below." />
		{/if}
		<section class="issues" aria-label="Flagged issues">
			<h2>Flagged issues ({issues.length})</h2>
			{#if issues.length === 0}
				<p class="muted">No open issues.</p>
			{:else}
				{#each document.sections as section (section.id)}
					{#if issuesBySection.get(section.id)?.length}
						<div class="issue-group">
							<h3>{section.title}</h3>
							<ul>
								{#each issuesBySection.get(section.id) ?? [] as issue}
									<li>
										<div class="issue-head">
											<Badge tone="attention">{issueLabel(issue.issue_code)}</Badge>
											{#if issue.affected_node_ids.length}<span class="targets">Nodes: {issue.affected_node_ids.join(', ')}</span>{/if}
										</div>
										<p>{issue.explanation}</p>
										<p class="required"><strong>Required correction:</strong> {issue.required_correction}</p>
									</li>
								{/each}
							</ul>
						</div>
					{/if}
				{/each}
			{/if}
		</section>

		<section class="sections" aria-label="Lesson content">
			{#each document.sections as section (section.id)}
				<article class="section" class:flagged={issuesBySection.has(section.id)}>
					<h2>{section.title}</h2>
					{#each section.nodes as node (node.id)}
						<div class="node" class:flagged={flaggedNodeIds.has(node.id)}>
							{#if node.kind === 'task_anchor'}
								<p class="frozen">Question — you can correct its wording; the answer key is locked.{#if node.role} · {node.role}{/if}</p>
								{#each fieldsFor(section, node) as field (field.key)}
									<label class="field">
										<span>{field.label}</span>
										<textarea
											rows={field.field === 'task_prompt' ? 3 : 2}
											value={values[field.key] ?? ''}
											oninput={(event) => setValue(field.key, (event.target as HTMLTextAreaElement).value)}
										></textarea>
									</label>
								{/each}
							{:else}
								{#if node.kind === 'figure'}
									<p class="frozen">Figure — asset {(node.display as { asset_id?: string | null })?.asset_id ?? 'unassigned'} (image editing is not supported here)</p>
								{/if}
								{#each nonAccessibilityFields(section, node) as field (field.key)}
									<label class="field">
										<span>{field.label}</span>
										<textarea
											rows={field.field === 'callout_title' || field.field === 'figure_caption' || field.field === 'figure_alt_text' || field.field === 'list_item_text' || field.field === 'table_cell_text' ? 2 : 4}
											value={values[field.key] ?? ''}
											oninput={(event) => setValue(field.key, (event.target as HTMLTextAreaElement).value)}
										></textarea>
									</label>
								{/each}
								{#if accessibilityField(section, node)}
									{@const a11yField = accessibilityField(section, node)!}
									<label class="field muted-field">
										<span>{a11yField.label}</span>
										<textarea
											rows="2"
											value={values[a11yField.key] ?? ''}
											oninput={(event) => setValue(a11yField.key, (event.target as HTMLTextAreaElement).value)}
										></textarea>
									</label>
								{/if}
							{/if}
						</div>
					{/each}
				</article>
			{/each}
		</section>

		<footer class="actions">
			<Button variant="secondary" busy={saving} disabled={!hasUnsavedChanges || saving} onclick={() => void saveDraft()}>
				{saving ? 'Saving…' : 'Save draft'}
			</Button>
			<Button busy={submitting} disabled={hasUnsavedChanges || submitting} onclick={() => void submitDraft()}>
				{submitting ? 'Submitting…' : 'Submit for re-check'}
			</Button>
			{#if hasUnsavedChanges}<span class="hint">Save your changes before submitting.</span>{/if}
			<span class="regen">
				<Button variant="secondary" busy={regenerating} disabled={regenerating || submitting || saving} onclick={() => void regenerateDocument()}>
					{regenerating ? 'Regenerating…' : 'Regenerate document'}
				</Button>
				<span class="hint">Use this when an issue can't be fixed by editing wording (for example, a wrong answer key).</span>
			</span>
		</footer>
	{/if}
</div>

<style>
	.review-ws { display: grid; gap: var(--space-4); }
	.bar { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-3); flex-wrap: wrap; }
	.bar h1 { margin: 0; font-family: var(--font-serif); font-size: 1.4rem; }
	.lesson-title { margin: 0.2rem 0 0; color: var(--ink-2); }
	.link { color: var(--accent); font-size: 0.875rem; font-weight: 550; text-decoration: none; }
	.muted { color: var(--ink-2); }
	.notice { color: var(--success); font-size: 0.875rem; }
	.issues, .sections { display: grid; gap: var(--space-3); }
	.issues h2, .sections h2 { margin: 0; font: 600 1.05rem var(--font-serif); }
	.issue-group { border: 1px solid var(--rule); border-radius: var(--radius-lg); background: var(--surface); padding: var(--space-3); }
	.issue-group h3 { margin: 0 0 var(--space-2); font-size: 0.9375rem; }
	.issue-group ul { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-2); }
	.issue-group li { border-left: 3px solid var(--danger); border-radius: var(--radius-sm); background: color-mix(in srgb, var(--danger) 5%, transparent); padding: var(--space-2) var(--space-3); }
	.issue-head { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
	.targets { color: var(--ink-2); font-size: 0.8125rem; }
	.required { color: var(--ink); }
	.section { border: 1px solid var(--rule); border-radius: var(--radius-lg); background: var(--surface); padding: var(--space-4); }
	.section.flagged { border-color: var(--danger); }
	.section h2 { font-size: 1.05rem; margin: 0 0 var(--space-3); }
	.node { padding: var(--space-2) 0; border-top: 1px solid var(--rule); }
	.node:first-of-type { border-top: none; }
	.node.flagged { background: color-mix(in srgb, var(--danger) 6%, transparent); border-radius: var(--radius-sm); }
	.frozen { color: var(--ink-2); font-style: italic; font-size: 0.875rem; }
	.regen { display: inline-flex; align-items: center; gap: var(--space-2); margin-left: auto; flex-wrap: wrap; }
	.field { display: grid; gap: 0.35rem; margin-bottom: var(--space-2); font-size: 0.8125rem; font-weight: 600; color: var(--ink-2); }
	.field.muted-field { font-weight: 500; }
	textarea { font: inherit; font-weight: 400; padding: 0.55rem 0.7rem; border-radius: var(--radius-md); border: 1px solid var(--rule); background: var(--surface); color: var(--ink); resize: vertical; width: 100%; box-sizing: border-box; }
	.actions { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
	.hint { color: var(--ink-2); font-size: 0.8125rem; }
</style>
