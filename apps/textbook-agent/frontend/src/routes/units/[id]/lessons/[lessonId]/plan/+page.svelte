<script lang="ts">
	import { getContext, onDestroy, untrack } from 'svelte';
	import { goto } from '$app/navigation';
	import {
		getUnitGroups,
		preparePathLesson,
		regeneratePathLesson,
		generateLearnRealization,
		generatePrintRealization,
		retryLessonRealization,
		getPreparedLessonStatus
	} from '$lib/api/units';
	import {
		getPreparationStructure,
		startPreparationPlan,
		regeneratePreparationPlan,
		retryPreparationRun
	} from '$lib/api/lesson-planning';
	import {
		getLessonApproach,
		approveLessonApproach,
		rejectLessonApproach
	} from '$lib/api/teaching-plan';
	import { realizePrintFromGeneration } from '$lib/api/realizations';
	import type { PathLesson, PreparedLessonStatus, Unit, UnitPath } from '$lib/types/units';
	import type { V3StructuralPlan } from '$lib/types/v3';
	import { Button, ProgressSteps, InlineError, Card } from '$lib/ui';
	import {
		lessonWorkspaceHref,
		resolvePlanGenerationId,
		lessonArtifactUi,
		preparationIsApprovedAndFresh
	} from '$lib/curriculum/lessons/lesson-context';
	import {
		canRegeneratePlan,
		canRetryPlan,
		isPlanPollingState,
		LEGACY_UNSUPPORTED_COPY,
		planFailureMessage,
		planPhaseFromPreparation,
		planProgressText
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

	const POLL_MS = 2000;

	let busy = $state<string | null>(null);
	let error = $state<string | null>(null);
	let changeNote = $state('');
	let showChangeNote = $state(false);
	let structuralPlan = $state<V3StructuralPlan | null>(null);
	let lessonApproach = $state<LessonApproachView | null>(null);
	// Verification of the approved Teaching Plan: null until checked.
	let approvalCheck = $state<'ok' | 'bad' | null>(null);
	// Set once this page verified an approval it just submitted.
	let approvedLocally = $state(false);
	let hydrationSeq = 0;

	const unitId = $derived(ctx.unitId);
	const lessonId = $derived(ctx.lessonId);
	const path = $derived(ctx.path);
	const lesson = $derived(ctx.lesson);
	const preparation = $derived(ctx.preparation);
	const prep = $derived(preparation?.workspace?.preparation ?? null);
	const generationId = $derived(resolvePlanGenerationId(preparation));
	const approvedFresh = $derived(ctx.statusFresh && preparationIsApprovedAndFresh(preparation));
	const learnArtifact = $derived(lessonArtifactUi(preparation, 'learn'));
	const printArtifact = $derived(lessonArtifactUi(preparation, 'print'));

	const phase = $derived.by(() => {
		if (approvedLocally) return 'approved' as const;
		const mapped = planPhaseFromPreparation(prep);
		if (mapped === 'approved') {
			if (approvalCheck === 'ok' && approvedFresh) return 'approved' as const;
			if (approvalCheck === 'bad' || approvalCheck === 'ok') return 'failed_terminal' as const;
			return 'working' as const;
		}
		return mapped;
	});

	const workingText = $derived(
		prep?.state === 'approved' && approvalCheck === null
			? 'Verifying the approved Teaching Plan…'
			: planProgressText(prep?.progress)
	);

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

	const failureText = $derived(
		prep?.state === 'approved'
			? 'The approved Teaching Plan is stale or could not be verified. Re-prepare and review it before creating outputs.'
			: planFailureMessage(prep)
	);

	function friendly(err: unknown): string {
		return err instanceof Error ? err.message : 'Something went wrong.';
	}

	// Poll lesson-status only, and only while the preparation Run is planning.
	$effect(() => {
		if (!isPlanPollingState(prep?.state)) return;
		const timer = setInterval(() => {
			ctx.refreshPreparation().catch((err) => {
				error = `Lesson status could not be refreshed: ${friendly(err)}`;
				clearInterval(timer);
			});
		}, POLL_MS);
		return () => clearInterval(timer);
	});

	// Load review/approval detail for the current canonical state.
	$effect(() => {
		const gid = generationId;
		const state = prep?.state;
		const kind = prep?.review_kind ?? null;
		untrack(() => void hydrate(gid, state, kind));
	});

	async function hydrate(
		gid: string | null,
		state: string | undefined,
		kind: 'structural' | 'teaching_plan' | null
	) {
		const seq = ++hydrationSeq;
		if (!gid) return;
		if (state === 'approved') {
			approvalCheck = null;
			let approach: LessonApproachView | null = null;
			let loadError: string | null = null;
			try {
				approach = await getLessonApproach(gid);
			} catch (err) {
				loadError = `Could not verify the approved Teaching Plan: ${friendly(err)}`;
			}
			if (seq !== hydrationSeq) return;
			lessonApproach = approach;
			approvalCheck = isVerifiedApprovedTeachingPlan(approach) ? 'ok' : 'bad';
			if (loadError) error = loadError;
			return;
		}
		if (state === 'awaiting_review' && kind === 'teaching_plan') {
			let approach: LessonApproachView | null = null;
			try {
				approach = await getLessonApproach(gid);
			} catch {
				approach = null;
			}
			if (seq === hydrationSeq) lessonApproach = approach;
			return;
		}
		if (state === 'awaiting_review' && kind === 'structural') {
			try {
				const planDoc = await getPreparationStructure(gid);
				if (seq === hydrationSeq) structuralPlan = planDoc.structural_plan;
			} catch (err) {
				if (seq === hydrationSeq) error = `Could not load the structural plan: ${friendly(err)}`;
			}
		}
	}

	async function refreshStatus() {
		try {
			await ctx.refreshPreparation();
		} catch (err) {
			error = `Lesson status could not be refreshed: ${friendly(err)}`;
		}
	}

	async function groupIdsForUnit(): Promise<string[]> {
		try {
			const groups = await getUnitGroups(unitId);
			return groups.groups.map((g) => g.id);
		} catch {
			return [];
		}
	}

	async function prepareLesson() {
		if (!ctx.statusFresh || !path || !lesson) return;
		busy = 'prepare';
		error = null;
		try {
			await preparePathLesson(unitId, path, lesson, 'first_exposure', await groupIdsForUnit());
			ctx.setPreparation(await getPreparedLessonStatus(unitId, lessonId));
		} catch (err) {
			error = friendly(err);
		} finally {
			busy = null;
		}
	}

	// Stage-1 re-prepare: used for legacy lessons and structural regeneration.
	async function reprepareLesson(reason: string) {
		if (!ctx.statusFresh || !path || !lesson) return;
		busy = 'reprepare';
		error = null;
		try {
			await regeneratePathLesson(unitId, path, lesson, 'first_exposure', reason, await groupIdsForUnit());
			ctx.setPreparation(await getPreparedLessonStatus(unitId, lessonId));
		} catch (err) {
			error = friendly(err);
		} finally {
			busy = null;
		}
	}

	async function approveStructural() {
		if (!ctx.statusFresh || !generationId) return;
		busy = 'approve-structural';
		error = null;
		try {
			// Idempotent: a repeat click returns the existing Run.
			await startPreparationPlan(generationId, { display_title: lesson?.title?.trim() || 'Lesson' });
			await refreshStatus();
		} catch (err) {
			error = friendly(err);
		} finally {
			busy = null;
		}
	}

	async function regenerateStructural(note: string) {
		await reprepareLesson(note || 'Teacher requested a new structure.');
	}

	async function retryPlan() {
		const runId = prep?.run_id;
		if (!ctx.statusFresh || !runId || !canRetryPlan(prep)) return;
		busy = 'retry-plan';
		error = null;
		try {
			await retryPreparationRun(runId, prep?.progress?.failed_work_item_ids ?? []);
			await refreshStatus();
		} catch (err) {
			error = friendly(err);
		} finally {
			busy = null;
		}
	}

	async function regeneratePlan() {
		if (!ctx.statusFresh || !generationId) return;
		busy = 'regenerate-plan';
		error = null;
		try {
			await regeneratePreparationPlan(generationId);
			await refreshStatus();
		} catch (err) {
			// 409 codes (not regeneratable / attempts exhausted / no run) carry
			// a teacher-readable message from the server.
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
			approvalCheck = 'ok';
			approvedLocally = true;
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
			// A rejected plan projects as failed_terminal (regenerate the plan).
			await refreshStatus();
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

	onDestroy(() => {
		hydrationSeq++;
	});

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
	{:else if busy === 'prepare' || busy === 'reprepare' || phase === 'working'}
		<Card padding="lg">
			<p class="working">{busy === 'prepare' || busy === 'reprepare' ? 'Preparing structure and teaching plan…' : workingText}</p>
		</Card>
	{:else if phase === 'legacy_unsupported'}
		<Card padding="lg">
			<h3>This lesson needs re-preparing</h3>
			<p>{LEGACY_UNSUPPORTED_COPY}</p>
			<Button disabled={!ctx.statusFresh || !path || !lesson} busy={busy === 'reprepare'} onclick={() => void reprepareLesson('Prepared before the planning update.')}>
				{busy === 'reprepare' ? 'Re-preparing…' : 'Re-prepare lesson'}
			</Button>
		</Card>
	{:else if phase === 'failed_recoverable' || phase === 'failed_terminal'}
		<Card padding="lg">
			<h3>{phase === 'failed_recoverable' ? 'Lesson preparation needs a retry' : 'Lesson preparation failed'}</h3>
			<p>{failureText}</p>
			<div class="actions">
				{#if canRetryPlan(prep)}
					<Button disabled={!ctx.statusFresh} busy={busy === 'retry-plan'} onclick={() => void retryPlan()}>
						{busy === 'retry-plan' ? 'Retrying…' : 'Retry'}
					</Button>
				{/if}
				{#if canRegeneratePlan(prep)}
					<Button
						variant={canRetryPlan(prep) ? 'secondary' : 'primary'}
						disabled={!ctx.statusFresh}
						busy={busy === 'regenerate-plan'}
						onclick={() => void regeneratePlan()}
					>
						{busy === 'regenerate-plan' ? 'Regenerating…' : 'Regenerate plan'}
					</Button>
				{:else if !canRetryPlan(prep)}
					<Button disabled={!ctx.statusFresh || !path || !lesson} busy={busy === 'reprepare'} onclick={() => void reprepareLesson('Re-prepare after a failed preparation.')}>
						{busy === 'reprepare' ? 'Re-preparing…' : 'Re-prepare lesson'}
					</Button>
				{/if}
			</div>
		</Card>
	{:else if phase === 'structural'}
		<section class="stage">
			<p class="eyebrow">Structural plan</p>
			{#if structuralPlan}
				<div class="preview-wrap">
					<StructuralPlanPreview plan={structuralPlan} />
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
