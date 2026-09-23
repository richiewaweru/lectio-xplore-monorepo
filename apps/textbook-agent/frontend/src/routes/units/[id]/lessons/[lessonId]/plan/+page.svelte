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
		approveChunkedPlan,
		regenerateChunkedPlan
	} from '$lib/api/lesson-planning';
	import {
		getLessonApproach,
		approveLessonApproach,
		rejectLessonApproach
	} from '$lib/api/teaching-plan';
	import { realizePrintFromGeneration, retryNativeGeneration } from '$lib/api/realizations';
	import type { PathLesson, PreparedLessonStatus, Unit, UnitPath } from '$lib/types/units';
	import type { V3ChunkedPlanState, V3StructuralPlan } from '$lib/types/v3';
	import { Button, ProgressSteps, InlineError, Card } from '$lib/ui';
	import {
		lessonWorkspaceHref,
		resolvePlanGenerationId,
		lessonArtifactUi,
		preparationIsApprovedAndFresh,
		canonicalPreparationState
	} from '$lib/curriculum/lessons/lesson-context';
	import {
		planFailureMessage
	} from '$lib/curriculum/lessons/plan-status';
	import StructuralPlanPreview from '$lib/curriculum/lessons/StructuralPlanPreview.svelte';
	import StructuralPlanActions from '$lib/curriculum/lessons/StructuralPlanActions.svelte';
	import TeachingPlanReview from '$lib/curriculum/lessons/TeachingPlanReview.svelte';
	import {
		canApproveTeachingPlan,
		isVerifiedApprovedTeachingPlan,
		type LessonApproachView
	} from '$lib/curriculum/lessons/teaching-plan-review';

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
		setPreparation: (next: PreparedLessonStatus | null) => void;
	};

	const ctx = getContext<Ctx>('lessonWorkspace');

	let busy = $state<string | null>(null);
	let error = $state<string | null>(null);
	let changeNote = $state('');
	let showChangeNote = $state(false);
	let chunked = $state<V3ChunkedPlanState | null>(null);
	let structuralPlan = $state<V3StructuralPlan | null>(null);
	let lessonApproach = $state<LessonApproachView | null>(null);
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
	const approvedFresh = $derived(ctx.statusFresh && preparationIsApprovedAndFresh(preparation));
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

	async function refreshAndHydrate(gid: string) {
		try {
			await ctx.refreshPreparation();
		} catch (err) {
			error = `Lesson status could not be refreshed: ${friendly(err)}`;
			stopPoll();
			return;
		}
		await hydrateFromGeneration(gid);
	}

	async function hydrateFromGeneration(gid: string) {
		if (hydrationInFlight) return;
		hydrationInFlight = true;
		error = null;
		try {
			const workspacePrep = preparation?.workspace?.preparation;
			if (workspacePrep?.state === 'approved') {
				try { lessonApproach = await getLessonApproach(gid); }
				catch (err) { lessonApproach = null; error = `Could not verify the approved Teaching Plan: ${friendly(err)}`; }
				phase = isVerifiedApprovedTeachingPlan(lessonApproach) && approvedFresh ? 'approved' : 'failed_terminal';
				if (phase === 'failed_terminal' && !error) error = 'The approved Teaching Plan is stale or could not be verified. Reprepare and review it before creating outputs.';
				stopPoll();
				return;
			}
			if (workspacePrep?.state === 'awaiting_review' && workspacePrep.review_kind === 'teaching_plan') {
				try { lessonApproach = await getLessonApproach(gid); } catch { lessonApproach = null; }
				phase = 'teaching';
				stopPoll();
				return;
			}
			if (workspacePrep?.state === 'failed_recoverable' || workspacePrep?.state === 'failed_terminal') {
				phase = workspacePrep.state;
				error = workspacePrep.error?.message ?? null;
				stopPoll();
				return;
			}
			if (workspacePrep?.state === 'planning') {
				phase = 'working';
				if (!pollTimer) pollTimer = setInterval(() => void refreshAndHydrate(gid), 2000);
				return;
			}
			if (workspacePrep?.state === 'not_started' || canonicalPreparationState(preparation) === 'legacy_ambiguous') {
				phase = workspacePrep?.state === 'not_started' ? 'idle' : 'failed_terminal';
				error = phase === 'failed_terminal' ? 'This preparation has ambiguous legacy state. Reprepare it before approval.' : null;
				stopPoll();
				return;
			}
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
			if (workspacePrep?.state === 'awaiting_review' && workspacePrep.review_kind === 'structural') {
				phase = 'structural';
				stopPoll();
				return;
			}
		stopPoll();
		phase = 'failed_terminal';
		error = 'The canonical preparation state is not an active review state. Refresh status or reprepare the lesson.';
		} catch (err) {
			error = friendly(err);
			phase = 'idle';
		} finally {
			hydrationInFlight = false;
		}
	}

	async function prepareLesson() {
		if (!ctx.statusFresh || !path || !lesson) return;
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
			const gid = prepared.generation_id || resolvePlanGenerationId(status);
			if (gid) await hydrateFromGeneration(gid);
		} catch (err) {
			error = friendly(err);
			phase = 'idle';
		} finally {
			busy = null;
		}
	}

	async function approveStructural() {
		if (!ctx.statusFresh || !chunked) return;
		busy = 'approve-structural';
		error = null;
		try {
			const title = lesson?.title?.trim() || 'Lesson';
			const next = await approveChunkedPlan(chunked.generation_id, { display_title: title });
			chunked = next;
			phase = 'working';
			// Poll until teaching review or failure
			stopPoll();
			pollTimer = setInterval(() => void refreshAndHydrate(chunked!.generation_id), 2000);
			await hydrateFromGeneration(chunked.generation_id);
		} catch (err) {
			const message = friendly(err);
			if (message.includes('Generation is not awaiting explicit approval')) {
				// The worker can advance to Teaching Plan review between status load
				// and this structural action. Re-read canonical state so the page
				// does not leave a stale structural approval control visible.
				try {
					await ctx.refreshPreparation();
					const current = preparation?.workspace?.preparation;
					if (current?.state !== 'awaiting_review' || current.review_kind !== 'structural') {
						error = null;
						await hydrateFromGeneration(chunked.generation_id);
					} else {
						error = message;
					}
				} catch {
					error = message;
				}
			} else {
				error = message;
			}
		} finally {
			busy = null;
		}
	}

	async function regenerateStructural(note: string) {
		if (!ctx.statusFresh || !chunked) return;
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
		const approach = lessonApproach;
		if (!ctx.statusFresh || !generationId || !approach || !canApproveTeachingPlan(approach)) return;
		busy = 'approve-teaching';
		error = null;
		try {
			const review = approach.teaching_review!;
			const pendingHash = approach.teaching_plan_identity!.pending_content_hash!;
			await approveLessonApproach(generationId, {
				expected_revision: review.revision!,
				expected_content_hash: pendingHash,
				teacher_note: changeNote.trim() || 'Approved',
				// Unit approval is shared by both realizations. Keep it path-neutral;
				// Print and Learn are admitted independently by their own actions.
				path: 'learn'
			});
			const refreshed = await getLessonApproach(generationId);
			lessonApproach = refreshed;
			if (
				!isVerifiedApprovedTeachingPlan(refreshed) ||
				refreshed.teaching_plan_identity?.approved_revision !== review.revision ||
				refreshed.teaching_plan_identity?.approved_content_hash !== pendingHash
			) {
				throw new Error('Approval was saved, but its Teaching Plan identity could not be verified. Reload the review.');
			}
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
		if (!ctx.statusFresh || !generationId || !lessonApproach) return;
		busy = 'reject-teaching';
		error = null;
		try {
			const review = (lessonApproach.teaching_review || {}) as { revision?: number };
			await rejectLessonApproach(generationId, {
				expected_revision: Number(review.revision || 1),
				teacher_note: changeNote.trim() || 'Please revise'
			});
			changeNote = '';
			showChangeNote = false;
			phase = 'structural';
			await hydrateFromGeneration(generationId);
		} catch (err) {
			error = friendly(err);
		} finally {
			busy = null;
		}
	}

	async function createLearn() {
		if (!path || !lesson || !approvedFresh) return;
		busy = 'learn';
		error = null;
		try {
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
		if (!path || !lesson || !approvedFresh) return;
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
		const generationToRetry = generationId ?? chunked?.generation_id;
		if (!ctx.statusFresh || !generationToRetry || preparation?.workspace?.preparation?.error?.retryable !== true) return;
		busy = 'retry-generation';
		error = null;
		try {
			await retryNativeGeneration(generationToRetry);
			phase = 'working';
			stopPoll();
			pollTimer = setInterval(() => void refreshAndHydrate(generationToRetry), 2000);
			await refreshAndHydrate(generationToRetry);
		} catch (err) {
			error = friendly(err);
		} finally {
			busy = null;
		}
	}

	async function retryArtifact(artifact: typeof learnArtifact) {
		if (!ctx.statusFresh || !path || !lesson || !artifact.realizationId || !artifact.retryable) return;
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

	const teachingReview = $derived(lessonApproach?.teaching_review ?? null);
</script>

<div class="plan">
	<div class="plan-top">
		<h2>Creating your lesson</h2>
		<ProgressSteps {steps} currentId={currentStepId} {completedIds} />
	</div>

	{#if error}
		<InlineError message={error} hint="Your unit and lesson path are safe. You can retry." />
	{/if}
	{#if ctx.statusError}<InlineError message={`Lesson status is stale: ${ctx.statusError}`} hint="Refresh the page status before creating or retrying an output." />{/if}

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
				<Button disabled={!ctx.statusFresh} busy={busy === 'prepare'} onclick={() => void prepareLesson()}>
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
			{#if phase === 'failed_recoverable' && preparation?.workspace?.preparation?.error?.retryable === true}
				<Button disabled={!ctx.statusFresh} busy={busy === 'retry-generation'} onclick={() => void retryFailedGeneration()}>
					{busy === 'retry-generation' ? 'Retrying…' : 'Retry'}
				</Button>
			{:else}
				<p class="warn">{preparation?.workspace?.preparation?.error?.recovery_action === 'reprepare' ? 'Reprepare this lesson from the unit workspace, then review the new plan.' : 'This failure cannot be retried here. Review the lesson inputs or regenerate the lesson from the unit workspace.'}</p>
			{/if}
		</Card>
	{:else if phase === 'structural'}
		<section class="stage">
			<p class="eyebrow">Structural plan</p>
			{#if structuralPlan || chunked}
				<div class="preview-wrap">
					{#if structuralPlan}
						<StructuralPlanPreview plan={structuralPlan} />
					{/if}
				</div>
				<StructuralPlanActions
					isRunning={busy !== null || !ctx.statusFresh}
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
				{#if lessonApproach?.teaching_plan}
					<TeachingPlanReview
						plan={lessonApproach.teaching_plan}
						review={teachingReview ?? undefined}
						identity={lessonApproach.teaching_plan_identity ?? undefined}
					/>
				{:else}
					<p>The Teaching Plan details are not available yet. Approval is disabled until the content can be verified.</p>
				{/if}
			</Card>
			<div class="actions">
				<Button variant="secondary" disabled={!ctx.statusFresh} onclick={() => (showChangeNote = !showChangeNote)}>Request changes</Button>
				<Button disabled={!ctx.statusFresh || !canApproveTeachingPlan(lessonApproach)} busy={busy === 'approve-teaching'} onclick={() => void approveTeaching()}>
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
				{#if lessonApproach?.teaching_plan && isVerifiedApprovedTeachingPlan(lessonApproach)}
					<TeachingPlanReview
						plan={lessonApproach.teaching_plan}
						review={teachingReview ?? undefined}
						identity={lessonApproach.teaching_plan_identity ?? undefined}
					/>
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
								disabled={!approvedFresh}
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
								{#if artifact.realizationId && artifact.retryable && ctx.statusFresh && path && lesson}<Button variant="secondary" busy={busy === artifact.path} onclick={() => void retryArtifact(artifact)}>Retry</Button>{/if}
								{#if artifact.recoveryAction === 'reprepare'}<a class="link" href={lessonWorkspaceHref(unitId, lessonId, 'plan')}>Reprepare and review</a>{/if}
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
	.preview-wrap {
		border: 1px solid var(--rule);
		border-radius: var(--radius-lg);
		overflow: hidden;
		background: var(--surface);
	}
</style>
