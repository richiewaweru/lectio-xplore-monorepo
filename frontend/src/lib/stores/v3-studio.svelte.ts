import type {
	ArchitectMode,
	BlueprintPreviewDTO,
	BookletStatus,
	CanvasSection,
	V3DraftPack,
	V3ChunkedPlanState,
	V3ClarificationAnswer,
	V3ClarificationQuestion,
	V3InputForm,
	V3ParentSnapshot,
	V3SignalSummary,
	V3Stage,
	V3SupplementContext,
	V3SupplementOption
} from '$lib/types/v3';

export type V3StudioStore = {
	stage: V3Stage;
	architectMode: ArchitectMode;
	form: V3InputForm | null;
	signals: V3SignalSummary | null;
	clarifications: V3ClarificationQuestion[];
	answers: V3ClarificationAnswer[];
	chunkedState: V3ChunkedPlanState | null;
	chunkedSectionStatus: Record<string, 'pending' | 'running' | 'retrying' | 'done' | 'failed'>;
	chunkedSectionErrors: Record<string, string[]>;
	blueprint: BlueprintPreviewDTO | null;
	/** Active v3 generation id after approve (used for PDF export). */
	generationId: string | null;
	canvas: CanvasSection[];
	draftPack: V3DraftPack | null;
	finalPack: V3DraftPack | null;
	activePack: V3DraftPack | null;
	bookletStatus: BookletStatus;
	bookletIssues: Array<Record<string, unknown>>;
	supplementOptions: V3SupplementOption[];
	supplementOptionsLoading: boolean;
	supplementOptionsError: string | null;
	supplementContext: V3SupplementContext | null;
	parentSnapshot: V3ParentSnapshot | null;
	error: string | null;
	coherenceHint: string | null;
	streamCancel: (() => void) | null;
};

export const v3Studio = $state<V3StudioStore>({
	stage: 'input',
	architectMode: 'standard',
	form: null,
	signals: null,
	clarifications: [],
	answers: [],
	chunkedState: null,
	chunkedSectionStatus: {},
	chunkedSectionErrors: {},
	blueprint: null,
	generationId: null,
	canvas: [],
	draftPack: null,
	finalPack: null,
	activePack: null,
	bookletStatus: 'streaming_preview',
	bookletIssues: [],
	supplementOptions: [],
	supplementOptionsLoading: false,
	supplementOptionsError: null,
	supplementContext: null,
	parentSnapshot: null,
	error: null,
	coherenceHint: null,
	streamCancel: null
});

export function captureParentSnapshot(): V3ParentSnapshot {
	return {
		generationId: v3Studio.generationId,
		blueprint: v3Studio.blueprint,
		canvas: v3Studio.canvas,
		draftPack: v3Studio.draftPack,
		finalPack: v3Studio.finalPack,
		activePack: v3Studio.activePack,
		bookletStatus: v3Studio.bookletStatus,
		bookletIssues: v3Studio.bookletIssues
	};
}

export function restoreParentFromSupplementReview(): void {
	const snapshot = v3Studio.parentSnapshot;
	if (!snapshot) return;

	v3Studio.streamCancel?.();
	v3Studio.generationId = snapshot.generationId;
	v3Studio.blueprint = snapshot.blueprint;
	v3Studio.canvas = snapshot.canvas;
	v3Studio.draftPack = snapshot.draftPack;
	v3Studio.finalPack = snapshot.finalPack;
	v3Studio.activePack = snapshot.activePack;
	v3Studio.bookletStatus = snapshot.bookletStatus;
	v3Studio.bookletIssues = snapshot.bookletIssues;
	v3Studio.supplementContext = null;
	v3Studio.parentSnapshot = null;
	v3Studio.stage = 'complete';
}

export function resetV3Studio(): void {
	v3Studio.streamCancel?.();
	v3Studio.stage = 'input';
	v3Studio.architectMode = 'standard';
	v3Studio.form = null;
	v3Studio.signals = null;
	v3Studio.clarifications = [];
	v3Studio.answers = [];
	v3Studio.chunkedState = null;
	v3Studio.chunkedSectionStatus = {};
	v3Studio.chunkedSectionErrors = {};
	v3Studio.blueprint = null;
	v3Studio.generationId = null;
	v3Studio.canvas = [];
	v3Studio.draftPack = null;
	v3Studio.finalPack = null;
	v3Studio.activePack = null;
	v3Studio.bookletStatus = 'streaming_preview';
	v3Studio.bookletIssues = [];
	v3Studio.supplementOptions = [];
	v3Studio.supplementOptionsLoading = false;
	v3Studio.supplementOptionsError = null;
	v3Studio.supplementContext = null;
	v3Studio.parentSnapshot = null;
	v3Studio.error = null;
	v3Studio.coherenceHint = null;
	v3Studio.streamCancel = null;
}
