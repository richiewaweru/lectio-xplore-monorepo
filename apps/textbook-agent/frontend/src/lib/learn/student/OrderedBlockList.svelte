<script lang="ts">
	/**
	 * Ordered block renderer — walks authoritative block_ids (P06-L02).
	 * Production mode posts attempts; preview keeps local-only evaluation.
	 */
	import {
		LectioBlockRuntimeSurface,
		SequenceInteraction,
		type BlockInstance,
		type LessonDocument,
		type LearnInteractionContract,
		type MediaReference
	} from '@lectio/learn';
	import { orderedBlocksInSection } from '@lectio/learn';
	import type { StoredAttempt } from './api/attempts';

	export type AttemptSubmitHandler = (args: {
		interactionId: string;
		sectionId: string;
		response: Record<string, unknown>;
	}) => Promise<{
		outcome: string;
		feedback: string;
		score_earned?: number;
		score_possible?: number;
	}>;

	interface Props {
		document: LessonDocument;
		sectionId: string;
		/** Preview: interactions never persist production attempts. */
		preview?: boolean;
		onPreviewSubmit?: (interactionId: string) => void;
		/** Latest persisted attempt per interaction_id (restore after refresh). */
		attemptsByInteraction?: Map<string, StoredAttempt>;
		/** Production submission bridge. */
		onSubmitAttempt?: AttemptSubmitHandler;
	}

	let {
		document,
		sectionId,
		preview = false,
		onPreviewSubmit,
		attemptsByInteraction = new Map(),
		onSubmitAttempt
	}: Props = $props();

	const blocks = $derived(orderedBlocksInSection(document, sectionId));
	const media = $derived(document.media ?? {});

	function interactionOf(block: BlockInstance): LearnInteractionContract | null {
		return (block.learn_interaction as LearnInteractionContract | undefined) ?? null;
	}

	function sequenceSteps(contract: LearnInteractionContract) {
		const config = contract.config as {
			order?: string[];
			items?: Array<{ id: string; label: string }>;
		};
		const items = config.items ?? [];
		if (items.length > 0) return items;
		return (config.order ?? []).map((id) => ({ id, label: id }));
	}

	function restoredOrder(contract: LearnInteractionContract): string[] | undefined {
		const attempt = attemptsByInteraction.get(contract.id);
		const order = attempt?.response_json?.order;
		return Array.isArray(order) ? order.map(String) : undefined;
	}

	function restoredEvaluation(contract: LearnInteractionContract) {
		const attempt = attemptsByInteraction.get(contract.id);
		if (!attempt) return null;
		const fb = contract.feedback;
		const feedback =
			attempt.outcome === 'correct'
				? fb.correct
				: attempt.outcome === 'partial'
					? (fb.partial ?? fb.incorrect)
					: fb.incorrect;
		return {
			outcome: attempt.outcome,
			feedback,
			score_earned: attempt.score_earned,
			score_possible: attempt.score_possible
		};
	}
</script>

<div
	class="ordered-block-list"
	data-testid="ordered-block-list"
	data-section-id={sectionId}
	data-preview={preview ? 'true' : 'false'}
	data-persist-attempts={preview ? 'false' : 'true'}
	data-block-count={blocks.length}
>
	{#each blocks as block (block.id)}
		{@const contract = interactionOf(block)}
		<div
			class="ordered-block"
			data-testid="ordered-block"
			data-block-id={block.id}
			data-component-id={block.component_id}
			data-position={block.position}
		>
			{#if contract?.kind === 'sequence'}
				<SequenceInteraction
					prompt={contract.prompt}
					steps={sequenceSteps(contract)}
					correctOrder={(contract.config.order as string[]) ?? []}
					feedback={contract.feedback}
					ariaLabel={contract.accessibility?.aria_label ?? contract.prompt}
					initialOrder={restoredOrder(contract)}
					initialEvaluation={restoredEvaluation(contract)}
					onSubmit={
						preview || !onSubmitAttempt
							? undefined
							: async (order) => {
									const result = await onSubmitAttempt({
										interactionId: contract.id,
										sectionId,
										response: { order }
									});
									onPreviewSubmit?.(contract.id);
									return result;
								}
					}
				/>
				{#if preview}
					<p class="preview-note" data-testid="preview-attempt-isolation">
						Preview — attempts are not saved.
					</p>
					<span hidden data-preview-submit-hook={onPreviewSubmit ? 'ready' : 'unused'}></span>
				{/if}
			{:else if contract}
				<p class="unsupported">
					Interaction kind “{contract.kind}” is not mounted in this renderer yet.
				</p>
			{:else}
				<LectioBlockRuntimeSurface
					componentId={block.component_id}
					content={block.content}
					media={media as Record<string, MediaReference>}
				/>
			{/if}
		</div>
	{/each}
</div>

<style>
	.ordered-block-list {
		display: grid;
		gap: 16px;
	}
	.ordered-block {
		min-width: 0;
	}
	.preview-note {
		margin: 8px 0 0;
		color: var(--ink-3, #666);
		font: 500 11px 'IBM Plex Mono', monospace;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}
	.unsupported {
		margin: 0;
		padding: 12px;
		border: 1px dashed var(--rule, #ccc);
		border-radius: 8px;
		color: var(--ink-2, #444);
		font-size: 13px;
	}
</style>
