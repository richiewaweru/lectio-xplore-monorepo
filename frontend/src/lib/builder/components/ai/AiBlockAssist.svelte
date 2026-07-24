<script lang="ts">
	import { browser } from '$app/environment';
	import { generateBlock } from '$lib/builder/api/ai-client';
	import type { BlockGenerateContextBlock } from '$lib/builder/api/ai-client';
	import { blockHasDistinctContent, resolveBackendMode } from './ai-block-utils';
	import { getNewAiBlockAssist } from '$lib/settings/flags';
	import { tryBeginAiCall } from '$lib/builder/utils/ai-rate-limit';
	import type { BlockInstance, GradeBand } from 'lectio';
	import { connectivityStore } from '$lib/builder/stores/connectivity.svelte';
	import type { BlockAiRepairRequest } from '$lib/builder/issues';
	import { Sparkles } from 'lucide-svelte';

	let {
		block,
		lessonId,
		sectionId,
		subject,
		gradeBand,
		contextBlocks,
		token,
		apiConfigured,
		ongenerated,
		onBeforeGenerate,
		repairRequest = null,
		onRepairApplied
	}: {
		block: BlockInstance;
		lessonId?: string;
		sectionId?: string;
		subject: string;
		gradeBand: GradeBand;
		contextBlocks: BlockGenerateContextBlock[];
		token: string | null;
		apiConfigured: boolean;
		ongenerated: (content: Record<string, unknown>) => void;
		/** Optional version snapshot (e.g. before AI); failures are ignored. */
		onBeforeGenerate?: () => void | Promise<void>;
		repairRequest?: BlockAiRepairRequest | null;
		onRepairApplied?: (request: BlockAiRepairRequest) => void | Promise<void>;
	} = $props();

	let open = $state(false);
	let mode = $state<'fill' | 'improve' | 'custom'>('fill');
	let teacherNote = $state('');
	let keepAsBasis = $state(true);
	let highQuality = $state(false);
	let loading = $state(false);
	let error = $state<string | null>(null);
	let rateMessage = $state<string | null>(null);
	let processedRepairKey = $state<string | null>(null);
	let activeRepairKey = $state<string | null>(null);
	let instructionTextarea = $state<HTMLTextAreaElement | null>(null);

	const hasDistinctContent = $derived(blockHasDistinctContent(block.component_id, block.content));
	const hasNote = $derived(Boolean(teacherNote.trim()));
	const newAssistEnabled = getNewAiBlockAssist();
	const triggerLabel = $derived(hasDistinctContent ? 'Edit with AI' : 'Generate content');
	const actionLabel = $derived(
		hasDistinctContent ? (keepAsBasis ? 'Improve' : 'Rewrite') : 'Generate'
	);

	const needsNetwork = $derived(!connectivityStore.online);

	function close(): void {
		open = false;
		activeRepairKey = null;
		error = null;
		rateMessage = null;
	}

	$effect(() => {
		if (
			!repairRequest ||
			repairRequest.targetBlockId !== block.id ||
			repairRequest.requestKey === processedRepairKey
		) return;
		processedRepairKey = repairRequest.requestKey;
		activeRepairKey = repairRequest.requestKey;
		mode = 'custom';
		keepAsBasis = false;
		teacherNote = repairRequest.initialInstruction;
		highQuality = false;
		error = null;
		rateMessage = null;
		open = true;
		queueMicrotask(() => instructionTextarea?.focus());
	});

	$effect(() => {
		if (!browser || !open) return;
		function onPointerDown(e: PointerEvent): void {
			const t = e.target as HTMLElement;
			if (t.closest?.('[data-ai-assist-root]')) return;
			close();
		}
		document.addEventListener('pointerdown', onPointerDown, true);
		return () => document.removeEventListener('pointerdown', onPointerDown, true);
	});

	async function runGenerate() {
		rateMessage = null;
		error = null;
		if (!connectivityStore.online) {
			error = 'Requires internet.';
			return;
		}
		if (!token) {
			error = 'Sign in to use AI assistance.';
			return;
		}
		if (!apiConfigured) {
			error = 'Set PUBLIC_API_URL to use AI assistance.';
			return;
		}
		if (!newAssistEnabled && mode === 'custom' && !teacherNote.trim()) {
			error = 'Add a custom instruction.';
			return;
		}

		const backendMode = newAssistEnabled
			? resolveBackendMode({
					hasContent: hasDistinctContent,
					hasNote,
					keepAsBasis
				})
			: mode;

		const ticket = tryBeginAiCall(block.id);
		if (!ticket.ok) {
			rateMessage =
				ticket.reason === 'cooldown' && ticket.waitMs > 0
					? `Please wait ${Math.ceil(ticket.waitMs / 1000)}s before another AI request for this block.`
					: 'Too many AI requests in progress. Please wait…';
			return;
		}

		const activeRepair =
			repairRequest?.requestKey === activeRepairKey ? repairRequest : null;
		loading = true;
		try {
			try {
				await onBeforeGenerate?.();
			} catch {
				/* non-blocking */
			}
			const focusRaw =
				teacherNote.trim() ||
				(typeof block.content?.title === 'string' ? block.content.title : '') ||
				subject;
			const res = await generateBlock(
				{
					lesson_id: lessonId,
					section_id: sectionId,
					component_id: block.component_id,
					mode: backendMode,
					subject,
					focus: focusRaw,
					grade_band: gradeBand,
					context_blocks: contextBlocks,
					teacher_note:
						newAssistEnabled || backendMode === 'custom'
							? teacherNote.trim() || undefined
							: undefined,
					existing_content: backendMode === 'improve' ? block.content : undefined,
					model_tier: highQuality ? 'STANDARD' : 'FAST'
				},
				token
			);
			ongenerated(res.content);
			if (activeRepair) await onRepairApplied?.(activeRepair);
			close();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Generation failed';
		} finally {
			loading = false;
			ticket.finish();
		}
	}
</script>

<div class="relative" data-ai-assist-root>
	<button
		type="button"
		class="rounded-md p-1.5 text-violet-600 hover:bg-violet-50 disabled:cursor-not-allowed disabled:opacity-40"
		title={needsNetwork
			? 'Requires internet'
			: !apiConfigured
				? 'Configure PUBLIC_API_URL for AI'
				: !token
					? 'Sign in to use AI'
					: triggerLabel}
		disabled={needsNetwork || !apiConfigured || !token}
		data-testid="ai-assist-trigger"
			onclick={(e) => {
				e.stopPropagation();
				if (open) close();
				else {
					activeRepairKey = null;
					open = true;
				}
			}}
	>
		<Sparkles size={16} aria-hidden="true" />
		<span class="sr-only">{triggerLabel}</span>
	</button>

	{#if open}
		<div
			class="absolute right-0 top-full z-30 mt-1 w-72 rounded-lg border border-slate-200 bg-white p-3 text-left shadow-lg"
			role="dialog"
			aria-label="AI block assistance"
			tabindex="-1"
		>
			{#if needsNetwork}
				<p class="mb-2 text-xs text-amber-800" role="status">Requires internet</p>
			{/if}
			<p class="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">AI</p>
			{#if !newAssistEnabled}
				<div class="mb-2 flex flex-col gap-1 text-sm">
					<label class="flex cursor-pointer items-center gap-2">
						<input type="radio" bind:group={mode} name="ai-mode-{block.id}" value="fill" />
						Fill
					</label>
					{#if hasDistinctContent}
						<label class="flex cursor-pointer items-center gap-2">
							<input type="radio" bind:group={mode} name="ai-mode-{block.id}" value="improve" />
							Improve
						</label>
					{/if}
					<label class="flex cursor-pointer items-center gap-2">
						<input type="radio" bind:group={mode} name="ai-mode-{block.id}" value="custom" />
						Custom
					</label>
				</div>
			{/if}
			<label class="mb-2 block text-xs text-slate-600">
				{#if newAssistEnabled}
					<span class="mb-1 block font-medium text-slate-700">Instruction <span class="font-normal text-slate-500">(optional)</span></span>
				{:else if mode === 'custom'}
					<span class="mb-1 block font-medium text-slate-700">Instruction</span>
				{:else}
					<span class="mb-1 block font-medium text-slate-700">Optional note</span>
				{/if}
				<textarea
					bind:this={instructionTextarea}
					bind:value={teacherNote}
					aria-label="Instruction"
					rows="3"
					class="mt-1 w-full rounded border border-slate-200 px-2 py-1 text-sm"
					placeholder={newAssistEnabled
						? hasDistinctContent
							? 'What would you like to change?'
							: 'What should this block include?'
						: mode === 'custom'
							? 'e.g. Make this more engaging for Year 9'
							: 'Optional hint for the model'}
				></textarea>
			</label>
			{#if newAssistEnabled && hasDistinctContent}
				<label class="mb-2 flex cursor-pointer items-center gap-2 text-xs text-slate-700">
					<input type="checkbox" bind:checked={keepAsBasis} />
					Keep existing content as basis
				</label>
			{/if}
			<label class="mb-3 flex cursor-pointer items-center gap-2 text-xs text-slate-700">
				<input type="checkbox" bind:checked={highQuality} />
				Higher quality (slower)
			</label>
			{#if error}
				<p class="mb-2 text-xs text-red-600" role="alert">{error}</p>
			{/if}
			{#if rateMessage}
				<p class="mb-2 text-xs text-amber-800" role="status">{rateMessage}</p>
			{/if}
			<button
				type="button"
				class="w-full rounded-lg bg-violet-600 px-3 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50"
				disabled={loading || needsNetwork}
				data-testid="ai-assist-generate"
				onclick={() => void runGenerate()}
			>
				{loading ? 'Generating…' : newAssistEnabled ? actionLabel : 'Generate'}
			</button>
		</div>
	{/if}
</div>
