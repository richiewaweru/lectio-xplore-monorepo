/**
 * Unit workspace controller — owns load/plan/save/edit state, independent
 * operation lanes, dirty preservation, 409 conflict recovery, and scoped
 * progress subscriptions. Print/Learn path jobs are injected (composition).
 */

import { isApiError } from '$lib/api/errors';
import {
	createManagedReliabilitySubscription,
	getReliabilityRunStatus,
	type ManagedReliabilitySubscription
} from '$lib/api/reliability';
import {
	approveUnitPath,
	editUnitPathByChat,
	getPreparedLessonStatus,
	getHistoricalPath,
	getPathHistory,
	getTeachingSchedule,
	getLessonShape,
	getUnit,
	getUnitGroups,
	getUnitPath,
	listUnitResources,
	mergePathLessons,
	patchPathLesson,
	planUnitPath,
	preparePathLesson,
	generateLearnRealization,
	generatePrintRealization,
	regeneratePathLesson,
	restorePathVersion
} from '$lib/api/units';
import {
	applyProgressRefreshWhileEditing,
	conflictFrom409,
	isEditorDirty,
	resolveConflict,
	snapshotToDraft,
	type LessonEditorDraft
} from '$lib/curriculum/units/edit-protection';
import type { NativePathKind } from '$lib/curriculum/units/path-generation';
import {
	emptyBusyMap,
	isLaneBusy,
	type OperationBusyMap,
	type UnitOperationLane
} from '$lib/reliability/operation-lanes';
import type { PathJobLane } from '$lib/reliability/path-job-lane';
import type {
	ReliabilityAllowedAction,
	ReliabilityConflictState,
	ReliabilityProgressEvent,
	ReliabilityRunStatus
} from '$lib/types/reliability';
import type {
	KnowledgeType,
	LessonMode,
	PathLesson,
	PathVersionSummary,
	PreparedLessonStatus,
	ResourceComposition,
	LessonShapePreview,
	TeachingSchedule,
	Unit,
	UnitGroups,
	UnitPath,
	MergeCriticResult
} from '$lib/types/units';

export type UnitWorkspaceView = 'path' | 'schedule' | 'groups' | 'results' | 'resources' | 'history';

export interface UnitWorkspaceDeps {
	printJob: PathJobLane;
	learnJob: PathJobLane;
	/** Optional override for tests. */
	fetchRunStatus?: typeof getReliabilityRunStatus;
	subscribeRun?: typeof createManagedReliabilitySubscription;
	navigate?: (href: string) => void;
}

function lines(value: string): string[] {
	return value
		.split('\n')
		.map((item) => item.trim())
		.filter(Boolean);
}

function plannerInput(current: Unit) {
	return {
		topic: current.topic,
		subject: current.subject,
		grade_level: current.grade_level,
		destination_objective: current.destination_objective,
		starting_knowledge: current.starting_knowledge,
		curriculum_context: current.curriculum_context,
		class_notes: current.class_notes
	};
}

function lessonDraftFrom(lesson: PathLesson): LessonEditorDraft {
	return {
		title: lesson.title,
		objective: lesson.objective,
		must_establish: lesson.must_establish.join('\n'),
		exclusions: lesson.exclusions.join('\n')
	};
}

export function createUnitWorkspace(unitIdOrGetter: string | (() => string), deps: UnitWorkspaceDeps) {
	const getUnitId = typeof unitIdOrGetter === 'function' ? unitIdOrGetter : () => unitIdOrGetter;
	let unit = $state<Unit | null>(null);
	let path = $state<UnitPath | null>(null);
	let selectedId = $state<string | null>(null);
	let loading = $state(true);
	let busy = $state<OperationBusyMap>(emptyBusyMap());
	let error = $state<string | null>(null);
	let tabError = $state<string | null>(null);
	let lessonMode = $state<LessonMode>('first_exposure');
	let shape = $state<LessonShapePreview | null>(null);
	let misconceptionCount = $state(1);
	let preparation = $state<PreparedLessonStatus | null>(null);
	let history = $state<PathVersionSummary[]>([]);
	let historyLoaded = $state(false);
	let viewedVersion = $state<UnitPath | null>(null);
	let schedule = $state<TeachingSchedule | null>(null);
	let scheduleLoaded = $state(false);
	let groups = $state<UnitGroups | null>(null);
	let groupsLoaded = $state(false);
	let compositions = $state<ResourceComposition[]>([]);
	let resourcesLoaded = $state(false);
	let selectedGroupIds = $state<string[]>([]);
	let activeView = $state<UnitWorkspaceView>('path');
	let restoreReason = $state('Restore this version as a new editable draft.');
	let pendingAction = $state<{ label: string; description: string; run: () => Promise<void> } | null>(
		null
	);
	let regenerationReason = $state('The lesson changed after preparation.');
	let editTitle = $state('');
	let editObjective = $state('');
	let editMustEstablish = $state('');
	let editExclusions = $state('');
	let editBaseline = $state<LessonEditorDraft | null>(null);
	let conflict = $state<ReliabilityConflictState | null>(null);
	let chatMessage = $state('');
	let chatUnavailable = $state(false);
	let chatNote = $state<string | null>(null);
	let showVersions = $state(false);
	let showShapeDebug = $state(false);
	let shapeError = $state<string | null>(null);
	let dismissedSuggestions = $state<string[]>([]);
	let mergeDraft = $state<{
		hintKey: string;
		lessonAId: string;
		lessonBId: string;
		lessonALabel: string;
		lessonBLabel: string;
		objectiveA: string;
		objectiveB: string;
		title: string;
		objective: string;
		mustEstablish: string;
		knowledgeType: KnowledgeType | '';
	} | null>(null);
	let runStatus = $state<ReliabilityRunStatus | null>(null);
	let allowedActions = $state<ReadonlySet<ReliabilityAllowedAction>>(new Set());
	let lastProgressEvent = $state<ReliabilityProgressEvent | null>(null);
	let subscription: ManagedReliabilitySubscription | null = null;
	let disposed = false;

	const navigate = deps.navigate ?? ((href: string) => {
		window.location.href = href;
	});
	const fetchRunStatus = deps.fetchRunStatus ?? getReliabilityRunStatus;
	const subscribeRun = deps.subscribeRun ?? createManagedReliabilitySubscription;

	const currentDraft = (): LessonEditorDraft => ({
		title: editTitle,
		objective: editObjective,
		must_establish: editMustEstablish,
		exclusions: editExclusions
	});

	const dirty = $derived(isEditorDirty(currentDraft(), editBaseline));

	const selected = $derived(path?.lessons.find((lesson) => lesson.id === selectedId) ?? null);
	const canLockIn = $derived(Boolean(path && path.lessons.length > 0 && path.status !== 'approved'));
	const planningFailed = $derived(Boolean(unit && !unit.active_path_version_id && !path));
	const canStartFresh = $derived(
		Boolean(
			preparation &&
				!preparation.stale &&
				preparation.workflow_stage === 'failed_terminal' &&
				preparation.can_regenerate
		)
	);
	const mergeSuggestions = $derived(
		(path?.merge_critic_results ?? []).filter((row) => row.source === 'deterministic')
	);
	const mergeDraftValid = $derived(
		Boolean(
			mergeDraft &&
				mergeDraft.title.trim() &&
				mergeDraft.objective.trim().length >= 3 &&
				lines(mergeDraft.mustEstablish).length >= 1 &&
				mergeDraft.knowledgeType
		)
	);

	function setLane(lane: UnitOperationLane, label: string | null): void {
		busy = { ...busy, [lane]: label };
	}

	function laneBusy(lane: UnitOperationLane): boolean {
		return isLaneBusy(busy, lane);
	}

	function actionAllowed(action: ReliabilityAllowedAction): boolean {
		if (allowedActions.size === 0) return true;
		return allowedActions.has(action);
	}

	function fillEditor(lesson: PathLesson): void {
		const draft = lessonDraftFrom(lesson);
		editTitle = draft.title;
		editObjective = draft.objective;
		editMustEstablish = draft.must_establish;
		editExclusions = draft.exclusions;
		editBaseline = draft;
		conflict = null;
	}

	function selectLesson(lesson: PathLesson): void {
		selectedId = lesson.id;
		fillEditor(lesson);
		shape = null;
		shapeError = null;
		preparation = null;
		showShapeDebug = false;
	}

	function suggestionKey(row: MergeCriticResult): string {
		return `${row.lesson_a}:${row.lesson_b}`;
	}

	function dependencySentences(lesson: PathLesson | null): string[] {
		if (!lesson || !path) return [];
		const sentences: string[] = [];
		for (const prerequisiteId of lesson.prerequisites) {
			const prerequisite = path.lessons.find((candidate) => candidate.id === prerequisiteId);
			if (prerequisite) sentences.push(`needs lesson ${prerequisite.position + 1}`);
		}
		return sentences;
	}

	function applyAllowedFromStatus(status: ReliabilityRunStatus | null): void {
		runStatus = status;
		allowedActions = new Set(status?.allowed_actions ?? []);
		if (status?.path === 'print') deps.printJob.applyStatus(status);
		if (status?.path === 'learn') deps.learnJob.applyStatus(status);
	}

	function detachSubscription(): void {
		subscription?.dispose();
		subscription = null;
	}

	function attachSubscription(ownerId: string, runId: string, afterSequence = 0): void {
		detachSubscription();
		if (disposed) return;
		subscription = subscribeRun(
			ownerId,
			runId,
			{
				onEvent(event) {
					lastProgressEvent = event;
					void refreshStatusPreservingDirty(runId);
				},
				onError() {
					/* reconnect is explicit via reconnectSubscription */
				}
			},
			{ afterSequence }
		);
	}

	async function refreshStatusPreservingDirty(runId: string): Promise<void> {
		try {
			const status = await fetchRunStatus(runId);
			if (disposed) return;
			applyAllowedFromStatus(status);
			if (!selected || !dirty) return;
			const incoming = {
				title: selected.title,
				objective: selected.objective,
				must_establish: selected.must_establish.join('\n'),
				exclusions: selected.exclusions.join('\n'),
				revision: selected.revision
			};
			const result = applyProgressRefreshWhileEditing({
				dirty: true,
				draft: currentDraft(),
				incoming
			});
			if (result.preserved) {
				// Keep local edits; baseline stays dirty relative to server.
				return;
			}
		} catch {
			/* status endpoint may be absent until P04 ships */
		}
	}

	async function runLane(
		lane: UnitOperationLane,
		label: string,
		action: () => Promise<unknown>,
		reload = true
	): Promise<void> {
		setLane(lane, label);
		error = null;
		try {
			await action();
			if (reload) await load({ preserveSelection: true, preserveDirty: dirty });
		} catch (err) {
			const message = err instanceof Error ? err.message : 'That change did not go through.';
			error = message;
			if (isApiError(err) && err.status === 409) {
				conflict = conflictFrom409({
					message,
					draft: currentDraft(),
					localRevision: selected?.revision ?? path?.revision ?? null,
					serverRevision: null
				});
				// Do not reload over local edits on conflict.
			}
		} finally {
			setLane(lane, null);
		}
	}

	async function load(
		options: { preserveSelection?: boolean; preserveDirty?: boolean } = {}
	): Promise<void> {
		loading = true;
		error = null;
		const preservedDraft = options.preserveDirty ? currentDraft() : null;
		try {
			unit = await getUnit(getUnitId());
			if (unit.active_path_version_id) {
				path = await getUnitPath(getUnitId());
			} else {
				path = null;
			}
			if (path?.lessons.length) {
				const target = options.preserveSelection
					? (path.lessons.find((lesson) => lesson.id === selectedId) ?? path.lessons[0])
					: path.lessons[0];
				if (preservedDraft && options.preserveDirty) {
					selectedId = target.id;
					editTitle = preservedDraft.title;
					editObjective = preservedDraft.objective;
					editMustEstablish = preservedDraft.must_establish;
					editExclusions = preservedDraft.exclusions;
					editBaseline = null;
					shape = null;
					shapeError = null;
					preparation = null;
				} else {
					selectLesson(target);
				}
			} else {
				selectedId = null;
			}
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not load the unit workspace.';
		} finally {
			loading = false;
		}
	}

	async function openTab(view: UnitWorkspaceView): Promise<void> {
		activeView = view;
		tabError = null;
		if (!unit) return;
		try {
			if (view === 'groups' && !groupsLoaded) {
				groups = await getUnitGroups(getUnitId());
				selectedGroupIds = groups.groups.map((group) => group.id);
				groupsLoaded = true;
			} else if (view === 'schedule' && !scheduleLoaded) {
				schedule = await getTeachingSchedule(getUnitId());
				scheduleLoaded = true;
			} else if (view === 'resources' && !resourcesLoaded) {
				if (!groupsLoaded) {
					groups = await getUnitGroups(getUnitId());
					selectedGroupIds = groups.groups.map((group) => group.id);
					groupsLoaded = true;
				}
				if (!scheduleLoaded) {
					schedule = await getTeachingSchedule(getUnitId());
					scheduleLoaded = true;
				}
				compositions = await listUnitResources(getUnitId());
				resourcesLoaded = true;
			} else if (view === 'history' && !historyLoaded) {
				history = await getPathHistory(getUnitId());
				historyLoaded = true;
			} else if (view === 'results' && !groupsLoaded) {
				groups = await getUnitGroups(getUnitId());
				selectedGroupIds = groups.groups.map((group) => group.id);
				groupsLoaded = true;
			}
		} catch (err) {
			tabError = err instanceof Error ? err.message : 'Could not load this tab.';
		}
	}

	async function planOrReplan(replan: boolean): Promise<void> {
		if (!unit) return;
		if (!actionAllowed('plan')) {
			error = 'Planning is not available for the current server status.';
			return;
		}
		await runLane(replan ? 'plan' : 'plan', replan ? 'Planning…' : 'Planning…', async () => {
			path = await planUnitPath(getUnitId(), plannerInput(unit as Unit), replan, path ?? undefined);
			unit = await getUnit(getUnitId());
			historyLoaded = false;
			if (path.lessons.length) selectLesson(path.lessons[0]);
		}, false);
	}

	async function saveLesson(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (!selected) return;
		if (!actionAllowed('save')) {
			error = 'Saving is not available for the current server status.';
			return;
		}
		await runLane('save', 'Saving…', async () => {
			const patched = await patchPathLesson(getUnitId(), path as UnitPath, selected, {
				title: editTitle.trim(),
				objective: editObjective.trim(),
				must_establish: lines(editMustEstablish),
				exclusions: lines(editExclusions)
			});
			await load({ preserveSelection: true, preserveDirty: false });
			if (path) {
				const updated = path.lessons.find((lesson) => lesson.id === selected.id);
				if (updated) {
					updated.revision = patched.revision;
					fillEditor(updated);
				}
			}
			conflict = null;
		}, false);
	}

	async function sendChatEdit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (!path || chatUnavailable || chatMessage.trim().length < 2) return;
		setLane('chat', 'Updating…');
		error = null;
		chatNote = null;
		try {
			const result = await editUnitPathByChat(getUnitId(), path, chatMessage.trim());
			chatMessage = '';
			chatNote = result.issues?.length ? result.issues.join(' ') : (result.note ?? null);
			await load({ preserveSelection: true });
		} catch (err) {
			if (isApiError(err) && err.status === 404) {
				chatUnavailable = true;
			} else {
				error = err instanceof Error ? err.message : 'Could not update the lessons from that message.';
			}
		} finally {
			setLane('chat', null);
		}
	}

	async function ensurePreparationStatus(): Promise<void> {
		if (!selected) return;
		const draft = currentDraft();
		const wasDirty = dirty;
		try {
			const next = await getPreparedLessonStatus(getUnitId(), selected.id);
			preparation = next;
			if (!next.stale && next.workflow_stage === 'failed_terminal') {
				regenerationReason = 'The previous generation did not finish.';
			}
			if (wasDirty) {
				editTitle = draft.title;
				editObjective = draft.objective;
				editMustEstablish = draft.must_establish;
				editExclusions = draft.exclusions;
			}
			const runId = next.generation_id;
			if (runId) {
				attachSubscription(getUnitId(), runId, 0);
				await refreshStatusPreservingDirty(runId);
			}
		} catch (err) {
			preparation = null;
			error = err instanceof Error ? err.message : 'Could not load preparation status.';
		}
	}

	async function ensureShape(): Promise<void> {
		if (!selected) return;
		try {
			shape = await getLessonShape(getUnitId(), selected.id, lessonMode, misconceptionCount);
			shapeError = null;
		} catch (err) {
			shape = null;
			shapeError = err instanceof Error ? err.message : 'Could not load this lesson shape.';
		}
	}

	async function updateShapeSettings(mode: LessonMode, count: number): Promise<void> {
		if (!selected) return;
		lessonMode = mode;
		misconceptionCount = count;
		shape = null;
		await ensureShape();
	}

	async function updateShapeRevision(revision: number): Promise<void> {
		if (!selected) return;
		selected.revision = revision;
		await ensurePreparationStatus();
	}

	async function prepare(pathKind: NativePathKind = 'print'): Promise<void> {
		if (!selected) return;
		const lane: UnitOperationLane = pathKind;
		const job = pathKind === 'print' ? deps.printJob : deps.learnJob;
		const pathApproved = path?.status === 'approved';
		if (!job.canPrepare(Boolean(pathApproved), selected.skipped)) {
			error =
				pathKind === 'print'
					? 'Print generation is not available right now.'
					: 'Learn generation is not available right now.';
			return;
		}
		if (!job.begin(pathKind === 'print' ? 'Generating Print…' : 'Generating Learn…')) return;
		setLane(lane, job.busyLabel);
		error = null;
		try {
			if (!groupsLoaded) {
				try {
					groups = await getUnitGroups(getUnitId());
					selectedGroupIds = groups.groups.map((group) => group.id);
					groupsLoaded = true;
				} catch {
					selectedGroupIds = [];
				}
			}
			const existingGenerationId = preparation?.generation_id || selected.pack_id;
			if (existingGenerationId) {
				try {
					if (pathKind === 'learn') {
						const result = await generateLearnRealization(getUnitId(), path as UnitPath, selected);
						const href =
							result.open_href ||
							(result.editable_lesson_id
								? `/builder/${encodeURIComponent(result.editable_lesson_id)}`
								: null);
						if (href) {
							navigate(href);
							return;
						}
					} else {
						const result = await generatePrintRealization(getUnitId(), path as UnitPath, selected);
						const href = result.open_href || `/studio/print/${encodeURIComponent(result.output_id)}`;
						navigate(href);
						return;
					}
				} catch (err) {
					if (isApiError(err) && err.status === 409) {
						const qs =
							pathKind === 'learn'
								? `?generation_id=${encodeURIComponent(existingGenerationId)}&path=learn`
								: `?generation_id=${encodeURIComponent(existingGenerationId)}`;
						navigate(`/studio${qs}`);
						return;
					}
					throw err;
				}
			}
			const prepared = await preparePathLesson(
				getUnitId(),
				path as UnitPath,
				selected,
				lessonMode,
				selectedGroupIds
			);
			attachSubscription(getUnitId(), prepared.generation_id, 0);
			if (pathKind === 'print') {
				navigate(`/studio?generation_id=${encodeURIComponent(prepared.generation_id)}`);
			} else {
				navigate(
					`/studio?generation_id=${encodeURIComponent(prepared.generation_id)}&path=learn`
				);
			}
		} catch (err) {
			error = err instanceof Error ? err.message : 'Generation did not start.';
		} finally {
			job.end();
			setLane(lane, null);
		}
	}

	async function regenerate(): Promise<void> {
		if (!selected || regenerationReason.trim().length < 3) return;
		if (!actionAllowed('regenerate')) {
			error = 'Regenerate is not available for the current server status.';
			return;
		}
		await runLane('regenerate', 'Making it again…', async () => {
			const prepared = await regeneratePathLesson(
				getUnitId(),
				path as UnitPath,
				selected,
				lessonMode,
				regenerationReason.trim(),
				selectedGroupIds
			);
			attachSubscription(getUnitId(), prepared.generation_id, 0);
			navigate(`/studio?generation_id=${encodeURIComponent(prepared.generation_id)}`);
		}, false);
	}

	async function confirmMergeReview(): Promise<void> {
		if (!path || !mergeDraft || !mergeDraftValid) return;
		const lessonA = path.lessons.find((lesson) => lesson.id === mergeDraft!.lessonAId);
		const lessonB = path.lessons.find((lesson) => lesson.id === mergeDraft!.lessonBId);
		if (!lessonA || !lessonB || !mergeDraft.knowledgeType) return;
		const draft = mergeDraft;
		await runLane('merge', 'Merging…', async () => {
			const result = await mergePathLessons(
				getUnitId(),
				path as UnitPath,
				[lessonA, lessonB],
				[lessonA.id, lessonB.id],
				{
					title: draft.title.trim(),
					objective: draft.objective.trim(),
					must_establish: lines(draft.mustEstablish),
					knowledge_type: draft.knowledgeType as KnowledgeType
				}
			);
			path = result.path;
			dismissedSuggestions = [...dismissedSuggestions, draft.hintKey];
			mergeDraft = null;
			const merged =
				path.lessons.find((lesson) => lesson.id === result.merged_lesson_id) ?? path.lessons[0];
			if (merged) selectLesson(merged);
		}, false);
	}

	function openMergeReview(row: MergeCriticResult): void {
		if (!path) return;
		const lessonA = path.lessons.find((lesson) => lesson.id === row.lesson_a);
		const lessonB = path.lessons.find((lesson) => lesson.id === row.lesson_b);
		if (!lessonA || !lessonB) return;
		const sameType = lessonA.primary_knowledge_type === lessonB.primary_knowledge_type;
		mergeDraft = {
			hintKey: suggestionKey(row),
			lessonAId: lessonA.id,
			lessonBId: lessonB.id,
			lessonALabel: `Lesson ${lessonA.position + 1}`,
			lessonBLabel: `Lesson ${lessonB.position + 1}`,
			objectiveA: lessonA.objective,
			objectiveB: lessonB.objective,
			title: `${lessonA.title} + ${lessonB.title}`,
			objective: '',
			mustEstablish: [...new Set([...lessonA.must_establish, ...lessonB.must_establish])].join('\n'),
			knowledgeType: sameType ? lessonA.primary_knowledge_type : ''
		};
	}

	function cancelMergeReview(): void {
		mergeDraft = null;
	}

	async function approvePath(): Promise<void> {
		if (!path) return;
		if (!actionAllowed('approve')) {
			error = 'Approve is not available for the current server status.';
			return;
		}
		await runLane('approve', 'Locking it in…', async () => {
			path = await approveUnitPath(getUnitId(), path as UnitPath);
			unit = await getUnit(getUnitId());
		}, false);
	}

	async function viewVersion(version: PathVersionSummary): Promise<void> {
		tabError = null;
		try {
			viewedVersion = await getHistoricalPath(getUnitId(), version.id);
		} catch (err) {
			tabError = err instanceof Error ? err.message : 'Could not load path history.';
		}
	}

	function confirmRestore(version: PathVersionSummary): void {
		if (!path || version.id === path.id) return;
		pendingAction = {
			label: `Restore path v${version.version}`,
			description: 'A new editable draft will be created. Nothing in history is deleted.',
			run: () =>
				runLane('restore', 'Restoring…', () =>
					restorePathVersion(getUnitId(), version.id, path as UnitPath, restoreReason)
				)
		};
	}

	async function runPendingAction(): Promise<void> {
		const action = pendingAction;
		pendingAction = null;
		if (action) await action.run();
	}

	function resolveEditConflict(choice: 'keep_editing' | 'reload_server'): void {
		if (!conflict) return;
		const serverSnapshot = selected
			? {
					title: selected.title,
					objective: selected.objective,
					must_establish: selected.must_establish.join('\n'),
					exclusions: selected.exclusions.join('\n'),
					revision: selected.revision
				}
			: null;
		const resolved = resolveConflict(conflict, choice, serverSnapshot);
		editTitle = resolved.draft.title;
		editObjective = resolved.draft.objective;
		editMustEstablish = resolved.draft.must_establish;
		editExclusions = resolved.draft.exclusions;
		editBaseline = resolved.baseline;
		conflict = null;
		if (choice === 'reload_server') {
			void load({ preserveSelection: true });
		}
	}

	function reconnectSubscription(): void {
		if (!subscription) return;
		subscription.reconnect(subscription.sink.lastSequence);
	}

	function dispose(): void {
		disposed = true;
		detachSubscription();
	}

	function canGeneratePrint(): boolean {
		return deps.printJob.canPrepare(path?.status === 'approved', Boolean(selected?.skipped));
	}

	function canGenerateLearn(): boolean {
		return deps.learnJob.canPrepare(path?.status === 'approved', Boolean(selected?.skipped));
	}

	return {
		get unit() {
			return unit;
		},
		get path() {
			return path;
		},
		set path(value) {
			path = value;
		},
		get selectedId() {
			return selectedId;
		},
		get selected() {
			return selected;
		},
		get loading() {
			return loading;
		},
		get busy() {
			return busy;
		},
		get error() {
			return error;
		},
		set error(value) {
			error = value;
		},
		get tabError() {
			return tabError;
		},
		get lessonMode() {
			return lessonMode;
		},
		get shape() {
			return shape;
		},
		set shape(value) {
			shape = value;
		},
		get misconceptionCount() {
			return misconceptionCount;
		},
		get preparation() {
			return preparation;
		},
		get history() {
			return history;
		},
		get historyLoaded() {
			return historyLoaded;
		},
		get viewedVersion() {
			return viewedVersion;
		},
		set viewedVersion(value) {
			viewedVersion = value;
		},
		get schedule() {
			return schedule;
		},
		set schedule(value) {
			schedule = value;
		},
		get groups() {
			return groups;
		},
		set groups(value) {
			groups = value;
		},
		get compositions() {
			return compositions;
		},
		set compositions(value) {
			compositions = value;
		},
		get selectedGroupIds() {
			return selectedGroupIds;
		},
		set selectedGroupIds(value) {
			selectedGroupIds = value;
		},
		get activeView() {
			return activeView;
		},
		get restoreReason() {
			return restoreReason;
		},
		set restoreReason(value) {
			restoreReason = value;
		},
		get pendingAction() {
			return pendingAction;
		},
		set pendingAction(value) {
			pendingAction = value;
		},
		get regenerationReason() {
			return regenerationReason;
		},
		set regenerationReason(value) {
			regenerationReason = value;
		},
		get editTitle() {
			return editTitle;
		},
		set editTitle(value) {
			editTitle = value;
		},
		get editObjective() {
			return editObjective;
		},
		set editObjective(value) {
			editObjective = value;
		},
		get editMustEstablish() {
			return editMustEstablish;
		},
		set editMustEstablish(value) {
			editMustEstablish = value;
		},
		get editExclusions() {
			return editExclusions;
		},
		set editExclusions(value) {
			editExclusions = value;
		},
		get dirty() {
			return dirty;
		},
		get conflict() {
			return conflict;
		},
		get chatMessage() {
			return chatMessage;
		},
		set chatMessage(value) {
			chatMessage = value;
		},
		get chatUnavailable() {
			return chatUnavailable;
		},
		get chatNote() {
			return chatNote;
		},
		get showVersions() {
			return showVersions;
		},
		set showVersions(value) {
			showVersions = value;
		},
		get showShapeDebug() {
			return showShapeDebug;
		},
		set showShapeDebug(value) {
			showShapeDebug = value;
		},
		get shapeError() {
			return shapeError;
		},
		set shapeError(value) {
			shapeError = value;
		},
		get dismissedSuggestions() {
			return dismissedSuggestions;
		},
		set dismissedSuggestions(value) {
			dismissedSuggestions = value;
		},
		get mergeDraft() {
			return mergeDraft;
		},
		set mergeDraft(value) {
			mergeDraft = value;
		},
		get mergeSuggestions() {
			return mergeSuggestions;
		},
		get mergeDraftValid() {
			return mergeDraftValid;
		},
		get canLockIn() {
			return canLockIn;
		},
		get planningFailed() {
			return planningFailed;
		},
		get canStartFresh() {
			return canStartFresh;
		},
		get runStatus() {
			return runStatus;
		},
		get allowedActions() {
			return allowedActions;
		},
		get lastProgressEvent() {
			return lastProgressEvent;
		},
		laneBusy,
		actionAllowed,
		canGeneratePrint,
		canGenerateLearn,
		selectLesson,
		suggestionKey,
		dependencySentences,
		load,
		openTab,
		planOrReplan,
		saveLesson,
		sendChatEdit,
		ensurePreparationStatus,
		ensureShape,
		updateShapeSettings,
		updateShapeRevision,
		prepare,
		regenerate,
		confirmMergeReview,
		openMergeReview,
		cancelMergeReview,
		approvePath,
		viewVersion,
		confirmRestore,
		runPendingAction,
		resolveEditConflict,
		reconnectSubscription,
		attachSubscription,
		detachSubscription,
		dispose,
		/** Test/helpers */
		snapshotToDraft,
		applyAllowedFromStatus
	};
}

export type UnitWorkspace = ReturnType<typeof createUnitWorkspace>;
