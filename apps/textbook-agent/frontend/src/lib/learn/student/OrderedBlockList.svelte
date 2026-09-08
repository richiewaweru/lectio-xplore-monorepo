<script lang="ts">
	/**
	 * Ordered block renderer — walks authoritative block_ids (P06-L02).
	 * Does not reconstruct SectionContent (lossy for repeats / interleaving).
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

	interface Props {
		document: LessonDocument;
		sectionId: string;
		/** Preview: interactions never persist production attempts. */
		preview?: boolean;
		onPreviewSubmit?: (interactionId: string) => void;
	}

	let { document, sectionId, preview = false, onPreviewSubmit }: Props = $props();

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
				/>
				{#if preview}
					<p class="preview-note" data-testid="preview-attempt-isolation">
						Preview — attempts are not saved.
					</p>
					<!-- Intentionally no production attempt POST; local SequenceInteraction state only. -->
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
