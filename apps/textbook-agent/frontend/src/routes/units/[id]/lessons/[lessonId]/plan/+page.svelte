<script lang="ts">
	import { getContext, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import {
		getUnitGroups,
		preparePathLesson,
		generateLearnRealization,
		generatePrintRealization,
		retryLessonRealization,
		getPreparedLessonStatus
	} from '$lib/api/units';
	import {
		getChunkedPlan,
		getChunkedPlanStatus,
		getLessonApproach,
		approveChunkedPlan,
		approveLessonApproach,
		rejectLessonApproach,
		regenerateChunkedPlan,
		realizeLearnFromGeneration,
		realizePrintFromGeneration,
		retryNativeGeneration
	} from '$lib/api/v3';
	import type { PathLesson, PreparedLessonStatus, Unit, UnitPath } from '$lib/types/units';
	import type { V3ChunkedPlanState, V3StructuralPlan } from '$lib/types/v3';
	import { Button, ProgressSteps, InlineError, Card } from '$lib/ui';
	import {
		lessonWorkspaceHref,
		resolvePlanGenerationId,
		lessonArtifactUi
	} from '$lib/curriculum/lessons/lesson-context';
	import {
		failureAllowsRetry,
		isPlanGenerationActive,
		isPlanGenerationFailure,
		planFailureMessage
	} from '$lib/curriculum/lessons/plan-status';
	import V3PlanPreview from '$lib/print/components/studio/V3PlanPreview.svelte';
	import V3PlanActions from '$lib/print/components/studio/V3PlanActions.svelte';

	type Ctx = {
		unitId: string;
		lessonId: string;
		unit: Unit | null;
		path: UnitPath | null;
		lesson: PathLesson | null;
		preparation: PreparedLessonStatus | null;
		refreshPreparation: () => Promise<void>;
		setPreparation: (next: PreparedLessonStatus | null) => void;
	};

	const ctx = getContext<Ctx>('lessonWorkspace');

	let busy = $state<string | null>(null);
	let error = $state<string | null>(null);
	let changeNote = $state('');
	let showChangeNote = $state(false);
	let chunked = $state<V3ChunkedPlanState | null>(null);
	let structuralPlan = $state<V3StructuralPlan | null>(null);
	let lessonApproach = $state<Record<string, unknown> | null>(null);
	let pollTimer: ReturnType<typeof setInterval> | null = null;
	let hydrationInFlight = false;

	type PlanPhase = 'idle' | 'structural' | 'teaching' | 'approved' | 'working' | 'failed_recoverable' | 'failed_terminal';
	let phase = $state<PlanPhase>('idle');

	const unitId = $derived(ctx.unitId);
	const lessonId = $derived(ctx.lessonId);
	const path = $derived(ctx.path);
	const lesson = $derived(ctx.lesson);
	const preparation = $derived(ctx.preparation);
	const generationId = $derived(resolvePlanGenerationId(preparation));
	const learnArtifact = $derived(lessonArtifactUi(preparation, 'learn'));
	const printArtifact = $derived(lessonArtifactUi(preparation, 'print'));

	const steps = [
		{ id: 'structural', label: 'Structural plan' },
		{ id: 'teaching', label: 'Teaching plan' },
		{ id: 'approved', label: 'Approval' }
	];

	const currentStepId = $derived.by(() => {
		if (phase === 'approved') return 'approved';
		if (phase === 'teaching') return 'teaching';
		return 'structural';
	});

	const completedIds = $derived.by(() => {
		if (phase === 'approved') return ['structural', 'teaching', 'approved'];
		if (phase === 'teaching') return ['structural'];
		return [] as string[];
	});

	function friendly(err: unknown): string {
		return err instanceof Error ? err.message : 'Something went wrong.';
	}

	function stopPoll() {
		if (pollTimer) {
			clearInterval(pollTimer);
			pollTimer = null;
		}
	}

	async function hydrateFromGeneration(gid: string) {
		if (hydrationInFlight) return;
		hydrationInFlight = true;
		error = null;
		try {
			const status = await getChunkedPlanStatus(gid);
			chunked = {
				generation_id: gid,
				stage: status.stage,
				structural_plan: null,
				section_briefs: {},
				failed_sections: status.failed_sections ?? [],
				blueprint_id: status.blueprint_id,
					execution_started: status.execution_started,
				next_action: status.next_action,
				error: status.error,
				error_type: status.error_type,
				error_detail: status.error_detail,
				inferred_lesson_mode: null,
				lesson_mode_confidence: null
			};
			try {
				const planDoc = await getChunkedPlan(gid);
				structuralPlan = planDoc.structural_plan;
				chunked = { ...chunked, structural_plan: planDoc.structural_plan };
			} catch {
				/* plan may not be ready */
			}
			const stage = String(status.stage ?? '');
			// The preparation worker can retain a pre-approval pipeline stage after
			// the path-neutral Learn approval has been persisted. The durable review
			// record is authoritative, so hydrate it before interpreting the worker
			// stage; otherwise the workspace can remain stuck on “Preparing”.
			try {
				lessonApproach = await getLessonApproach(gid);
				const reviewStatus = String(
					((lessonApproach.teaching_review || {}) as { status?: unknown }).status || ''
				).toLowerCase();
				if (reviewStatus === 'approved') {
					phase = 'approved';
					stopPoll();
					return;
				}
			} catch {
				/* Teaching plan may still be generating. */
			}
			// A failed Print/Learn realization must not erase the teacher's
			// already-approved Teaching Plan. Keep the approval controls visible so
			// the other fork can be retried from the same revision.
			if (stage.includes('fail')) {
				try {
					lessonApproach = await getLessonApproach(gid);
					const reviewStatus = String(
						((lessonApproach.teaching_review || {}) as { status?: unknown }).status || ''
					).toLowerCase();
					if (reviewStatus === 'approved') {
						phase = 'approved';
						stopPoll();
						return;
					}
				} catch {
					/* keep the failure state below when teaching review is unavailable */
				}
			}
			if (isPlanGenerationFailure(status)) {
				phase = status.stage === 'failed_recoverable' ? 'failed_recoverable' : 'failed_terminal';
				stopPoll();
				return;
			}
			if (stage === 'awaiting_teaching_approval') {
				lessonApproach = await getLessonApproach(gid);
				const reviewStatus = String(
					((lessonApproach.teaching_review || {}) as { status?: unknown }).status || ''
				).toLowerCase();
				if (reviewStatus === 'approved') {
					phase = 'approved';
					stopPoll();
					return;
				}
				phase = 'teaching';
				stopPoll();
				return;
			}
			if (
				stage === 'awaiting_review' ||
				stage === 'plan_ready' ||
				stage === 'assembly_blocked' ||
				stage === 'stage2_error'
			) {
				phase = 'structural';
				stopPoll();
				return;
			}
			if (
				stage === 'ready' ||
				stage === 'complete' ||
				stage === 'completed' ||
				stage === 'awaiting_visuals'
			) {
				try {
					lessonApproach = await getLessonApproach(gid);
				} catch {
					/* The approved-plan shell remains visible if the detail fetch is unavailable. */
				}
				phase = 'approved';
				stopPoll();
				return;
			}
			if (isPlanGenerationActive(status)) {
				phase = 'working';
				if (!pollTimer) pollTimer = setInterval(() => void hydrateFromGeneration(gid), 2000);
				return;
			}
			stopPoll();
			phase = 'idle';
		} catch (err) {
			error = friendly(err);
			phase = 'idle';
		} finally {
			hydrationInFlight = false;
		}
	}

	async function prepareLesson() {
		if (!path || !lesson) return;
		busy = 'prepare';
		error = null;
		phase = 'working';
		try {
			let groupIds: string[] = [];
			try {
				const groups = await getUnitGroups(unitId);
				groupIds = groups.groups.map((g) => g.id);
			} catch {
				groupIds = [];
			}
			const prepared = await preparePathLesson(unitId, path, lesson, 'first_exposure', groupIds);
			const status = await getPreparedLessonStatus(unitId, lessonId);
			ctx.setPreparation(status);
			const gid = prepared.generation_id || status.generation_id;
			if (gid) await hydrateFromGeneration(gid);
		} catch (err) {
			error = friendly(err);
			phase = 'idle';
		} finally {
			busy = null;
		}
	}

	async function approveStructural() {
		if (!chunked) return;
		busy = 'approve-structural';
		error = null;
		try {
			const title = lesson?.title?.trim() || 'Lesson';
			const next = await approveChunkedPlan(chunked.generation_id, { display_title: title });
			chunked = next;
			phase = 'working';
			// Poll until teaching review or failure
			stopPoll();
			pollTimer = setInterval(() => void hydrateFromGeneration(chunked!.generation_id), 2000);
			await hydrateFromGeneration(chunked.generation_id);
		} catch (err) {
			error = friendly(err);
		} finally {
			busy = null;
		}
	}

	async function regenerateStructural(note: string) {
		if (!chunked) return;
		busy = 'regen';
		error = null;
		try {
			const next = await regenerateChunkedPlan({
				generation_id: chunked.generation_id,
				note
			});
			chunked = next;
			phase = 'structural';
		} catch (err) {
			error = friendly(err);
		} finally {
			busy = null;
		}
	}

	async function approveTeaching() {
		if (!chunked || !lessonApproach) return;
		busy = 'approve-teaching';
		error = null;
		try {
			const review = (lessonApproach.teaching_review || {}) as { revision?: number };
			await approveLessonApproach(chunked.generation_id, {
				expected_revision: Number(review.revision || 1),
				teacher_note: changeNote.trim() || 'Approved',
				// Unit approval is shared by both realizations. Keep it path-neutral;
				// Print and Learn are admitted independently by their own actions.
				path: 'learn'
			});
			await ctx.refreshPreparation();
			phase = 'approved';
			stopPoll();
		} catch (err) {
			error = friendly(err);
		} finally {
			busy = null;
		}
	}

	async function requestTeachingChanges() {
		if (!chunked || !lessonApproach) return;
		busy = 'reject-teaching';
		error = null;
		try {
			const review = (lessonApproach.teaching_review || {}) as { revision?: number };
			await rejectLessonApproach(chunked.generation_id, {
				expected_revision: Number(review.revision || 1),
				teacher_note: changeNote.trim() || 'Please revise'
			});
			changeNote = '';
			showChangeNote = false;
			phase = 'structural';
			await hydrateFromGeneration(chunked.generation_id);
		} catch (err) {
			error = friendly(err);
		} finally {
			busy = null;
		}
	}

	async function createLearn() {
		if (!path || !lesson) return;
		busy = 'learn';
		error = null;
		try {
			// Realize directly from the approved shared preparation. Do not fall
			// through to the retired unit endpoint: it can mask the precise
			// admission/contract error and create a second attempt.
			const gid = generationId;
			if (gid) {
				await realizeLearnFromGeneration(gid);
				await ctx.refreshPreparation();
				await goto(lessonWorkspaceHref(unitId, lessonId, 'learn'));
				return;
			}
			await generateLearnRealization(unitId, path, lesson);
			await ctx.refreshPreparation();
			await goto(lessonWorkspaceHref(unitId, lessonId, 'learn'));
		} catch (err) {
			error = friendly(err);
		} finally {
			busy = null;
		}
	}

	async function createPrint() {
		if (!path || !lesson) return;
		busy = 'print';
		error = null;
		try {
			const gid = generationId;
			if (gid) {
				await realizePrintFromGeneration(gid);
			} else {
				await generatePrintRealization(unitId, path, lesson);
			}
			await ctx.refreshPreparation();
			await goto(lessonWorkspaceHref(unitId, lessonId, 'print'));
		} catch (err) {
			error = friendly(err);
		} finally {
			busy = null;
		}
	}

	async function retryFailedGeneration() {
		if (!chunked || !failureAllowsRetry(chunked)) return;
		busy = 'retry-generation';
		error = null;
		try {
			await retryNativeGeneration(chunked.generation_id);
			phase = 'working';
			stopPoll();
			pollTimer = setInterval(() => void hydrateFromGeneration(chunked!.generation_id), 2000);
			await hydrateFromGeneration(chunked.generation_id);
		} catch (err) {
			error = friendly(err);
		} finally {
			busy = null;
		}
	}

	async function retryArtifact(artifact: typeof learnArtifact) {
		if (!path || !lesson || !artifact.realizationId) return;
		busy = artifact.path;
		error = null;
		try {
			await retryLessonRealization(unitId, path, lesson, artifact.realizationId);
			await ctx.refreshPreparation();
		} catch (err) {
			error = friendly(err);
		} finally {
			busy = null;
		}
	}

	function artifactTitle(pathName: 'learn' | 'print'): string {
		return pathName === 'learn' ? 'Learn' : 'Print';
	}

	$effect(() => {
		const gid = generationId;
		if (gid && phase === 'idle') {
			void hydrateFromGeneration(gid);
		}
	});

	onDestroy(stopPoll);

	const teachingReview = $derived((lessonApproach?.teaching_review || null) as Record<string, unknown> | null);
</script>

<div class="plan">
	<div class="plan-top">
		<h2>Creating your lesson</h2>
		<ProgressSteps {steps} currentId={currentStepId} {completedIds} />
	</div>

	{#if error}
		<InlineError message={error} hint="Your unit and lesson path are safe. You can retry." />
	{/if}

	{#if phase === 'idle' && !generationId}
		<Card padding="lg">
			<h3>Review the plan for this lesson</h3>
			<p>
				Lectio will draft a structural plan and a teaching plan. Approve them before creating Learn or Print
				materials.
			</p>
			{#if path?.status !== 'approved'}
				<p class="warn">Lock in the unit path first, then prepare this lesson.</p>
			{:else}
				<Button busy={busy === 'prepare'} onclick={() => void prepareLesson()}>
					{busy === 'prepare' ? 'Preparing…' : 'Prepare lesson'}
				</Button>
			{/if}
		</Card>
	{:else if phase === 'working'}
		<Card padding="lg">
			<p class="working">Preparing structure and teaching plan…</p>
		</Card>
	{:else if phase === 'failed_recoverable' || phase === 'failed_terminal'}
		<Card padding="lg">
			<h3>{phase === 'failed_recoverable' ? 'Lesson preparation needs a retry' : 'Lesson preparation failed'}</h3>
			<p>{planFailureMessage(chunked ?? { stage: phase, error: null, error_detail: null })}</p>
			{#if phase === 'failed_recoverable'}
				<Button busy={busy === 'retry-generation'} onclick={() => void retryFailedGeneration()}>
					{busy === 'retry-generation' ? 'Retrying…' : 'Retry'}
				</Button>
			{:else}
				<p class="warn">This failure is terminal. Review the lesson inputs or regenerate the lesson from the unit workspace.</p>
			{/if}
		</Card>
	{:else if phase === 'structural'}
		<section class="stage">
			<p class="eyebrow">Structural plan</p>
			{#if structuralPlan || chunked}
				<div class="preview-wrap">
					{#if structuralPlan}
						<V3PlanPreview plan={structuralPlan} />
					{/if}
				</div>
				<V3PlanActions
					isRunning={busy !== null}
					onApprove={() => void approveStructural()}
					onRegenerate={(note) => void regenerateStructural(note)}
					onRecovery={() => void approveStructural()}
				/>
			{:else}
				<p>Loading structural plan…</p>
			{/if}
		</section>
	{:else if phase === 'teaching'}
		<section class="stage">
			<p class="eyebrow">Teaching plan</p>
			<Card padding="md">
				{#if teachingReview}
					{#each Object.entries(teachingReview) as [key, value]}
						{#if key !== 'revision' && key !== 'status' && typeof value === 'string' && value.trim()}
							<details open={['objective', 'purpose', 'pedagogical_arc'].includes(key)}>
								<summary>{key.replaceAll('_', ' ')}</summary>
								<p>{value}</p>
							</details>
						{:else if key !== 'revision' && key !== 'status' && Array.isArray(value) && value.length}
							<details>
								<summary>{key.replaceAll('_', ' ')}</summary>
								<ul>
									{#each value as item}
										<li>{typeof item === 'string' ? item : JSON.stringify(item)}</li>
									{/each}
								</ul>
							</details>
						{/if}
					{/each}
				{:else}
					<p>Loading teaching plan…</p>
				{/if}
			</Card>
			<div class="actions">
				<Button variant="secondary" onclick={() => (showChangeNote = !showChangeNote)}>Request changes</Button>
				<Button busy={busy === 'approve-teaching'} onclick={() => void approveTeaching()}>
					{busy === 'approve-teaching' ? 'Approving…' : 'Approve plan'}
				</Button>
			</div>
			{#if showChangeNote}
				<label class="note">
					<span>What should change?</span>
					<textarea bind:value={changeNote} rows="3" placeholder="Optional note for Lectio"></textarea>
					<Button
						variant="secondary"
						busy={busy === 'reject-teaching'}
						onclick={() => void requestTeachingChanges()}
					>
						Send request
					</Button>
				</label>
			{/if}
		</section>
	{:else if phase === 'approved'}
		<section class="approved">
			<Card padding="lg">
				<h3>Teaching plan approved</h3>
				{#if teachingReview}
					<div class="teaching-plan">
						{#each Object.entries(teachingReview) as [key, value]}
							{#if key !== 'revision' && key !== 'status' && typeof value === 'string' && value.trim()}
								<details open={['objective', 'purpose', 'pedagogical_arc'].includes(key)}>
									<summary>{key.replaceAll('_', ' ')}</summary>
									<p>{value}</p>
								</details>
							{:else if key !== 'revision' && key !== 'status' && Array.isArray(value) && value.length}
								<details>
									<summary>{key.replaceAll('_', ' ')}</summary>
									<ul>{#each value as item}<li>{typeof item === 'string' ? item : JSON.stringify(item)}</li>{/each}</ul>
								</details>
							{/if}
						{/each}
					</div>
				{/if}
			</Card>
			<div class="outputs">
				<p class="eyebrow">Outputs</p>
				{#each [learnArtifact, printArtifact] as artifact}
					<Card padding="md">
						<div class="output-head">
							<div>
								<h3>{artifactTitle(artifact.path)}</h3>
								<p class="status-line">{artifact.state === 'not_created' ? 'Not created' : artifact.state.replaceAll('_', ' ')}</p>
							</div>
							{#if artifact.state === 'ready'}<span class="ready">Ready</span>{/if}
						</div>
						{#if artifact.state === 'not_created'}
							<p>Create this output from the approved teaching plan.</p>
							<Button
								variant={artifact.path === 'learn' ? 'primary' : 'secondary'}
								busy={busy === artifact.path}
								onclick={() => void (artifact.path === 'learn' ? createLearn() : createPrint())}
							>
								{busy === artifact.path ? `Creating ${artifactTitle(artifact.path)}…` : `Create ${artifactTitle(artifact.path)}`}
							</Button>
						{:else if artifact.state === 'preparing'}
							<p>This output is being prepared. You can view its status in the workspace.</p>
							<a class="link" href={lessonWorkspaceHref(unitId, lessonId, artifact.path)}>View {artifactTitle(artifact.path)}</a>
						{:else if artifact.state === 'ready'}
							<p>This output is ready to review and edit.</p>
							<div class="actions">
								{#if artifact.openHref}<a class="link" href={artifact.openHref}>Open {artifactTitle(artifact.path)}</a>{/if}
								<a class="link" href={lessonWorkspaceHref(unitId, lessonId, artifact.path)}>View {artifactTitle(artifact.path)}</a>
							</div>
						{:else}
							<p>{artifact.errorSummary || 'This output exists but needs attention.'}</p>
							<div class="actions">
								{#if artifact.openHref}<a class="link" href={artifact.openHref}>Open {artifactTitle(artifact.path)}</a>{/if}
								<a class="link" href={lessonWorkspaceHref(unitId, lessonId, artifact.path)}>Issues</a>
								{#if artifact.realizationId && path && lesson}<Button variant="secondary" busy={busy === artifact.path} onclick={() => void retryArtifact(artifact)}>Retry</Button>{/if}
							</div>
						{/if}
					</Card>
				{/each}
			</div>
		</section>
	{/if}
</div>

<style>
	.plan {
		display: grid;
		gap: var(--space-5);
	}
	.plan-top {
		display: grid;
		gap: var(--space-4);
	}
	h2,
	h3 {
		margin: 0;
		font-family: var(--font-serif);
		font-weight: 600;
	}
	h2 {
		font-size: 1.25rem;
	}
	h3 {
		font-size: 1.15rem;
		margin-bottom: 0.5rem;
	}
	p {
		margin: 0 0 1rem;
		color: var(--ink-2);
		line-height: 1.5;
	}
	.warn {
		color: var(--amber);
	}
	.working {
		color: var(--ink-2);
		font-size: 0.95rem;
	}
	.eyebrow {
		margin: 0 0 0.75rem;
		color: var(--ink-3);
		font-size: 0.75rem;
		font-weight: 600;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}
	.stage {
		display: grid;
		gap: var(--space-4);
	}
	.actions {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2);
		margin-top: var(--space-3);
	}
	.approved,
	.outputs {
		display: grid;
		gap: var(--space-4);
	}
	.outputs {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}
	.output-head {
		display: flex;
		justify-content: space-between;
		gap: var(--space-3);
	}
	.output-head h3 {
		margin-bottom: 0.25rem;
	}
	.status-line {
		margin: 0;
		text-transform: capitalize;
	}
	.ready {
		color: var(--success);
		font-size: 0.8125rem;
		font-weight: 600;
	}
	.teaching-plan {
		display: grid;
		gap: var(--space-2);
	}
	.teaching-plan details {
		border-top: 1px solid var(--rule);
		padding-top: var(--space-2);
	}
	@media (max-width: 720px) {
		.outputs {
			grid-template-columns: 1fr;
		}
	}
	.note {
		display: grid;
		gap: 0.5rem;
		margin-top: var(--space-3);
	}
	.note span {
		font-size: 0.8125rem;
		font-weight: 600;
		color: var(--ink-2);
	}
	textarea {
		width: 100%;
		box-sizing: border-box;
		border: 1px solid var(--rule);
		border-radius: var(--radius-md);
		padding: 0.65rem 0.75rem;
		font: inherit;
		background: var(--surface);
	}
	details {
		border-bottom: 1px solid var(--rule);
		padding: 0.75rem 0;
	}
	summary {
		cursor: pointer;
		font-weight: 600;
		text-transform: capitalize;
	}
	details p,
	details ul {
		margin: 0.5rem 0 0;
		color: var(--ink-2);
		font-size: 0.9rem;
		line-height: 1.5;
	}
	.preview-wrap {
		border: 1px solid var(--rule);
		border-radius: var(--radius-lg);
		overflow: hidden;
		background: var(--surface);
	}
</style>
