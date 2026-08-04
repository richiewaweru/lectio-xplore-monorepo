<script lang="ts">
	import { regenerateV3Visual, repairV3Card } from '$lib/api/v3';
	import type { V3DraftPack } from '$lib/types/v3';

	interface Props {
		issues?: Array<Record<string, unknown>>;
		title?: string;
		generationId?: string | null;
		pack?: V3DraftPack | null;
		onRegenerated?: () => void | Promise<void>;
	}

	let {
		issues = [],
		title = 'Issues to review',
		generationId = null,
		pack = null,
		onRegenerated
	}: Props = $props();
	let hints = $state<Record<string, string>>({});
	let pending = $state<Record<string, boolean>>({});
	let errors = $state<Record<string, string>>({});

	function asText(value: unknown): string {
		return typeof value === 'string' ? value.trim() : '';
	}

	function issueMeta(issue: Record<string, unknown>): string {
		return [asText(issue.section_id), asText(issue.category)].filter(Boolean).join(' - ');
	}

	function issueMessage(issue: Record<string, unknown>): string {
		if (asText(issue.category) === 'visual_quality_flagged') {
			const section = asText(issue.section_id) || asText(issue.generated_ref) || 'this section';
			const reasons = asText(issue.message).replace(/^image flagged by quality review:\s*/i, '');
			return `The image for '${section}' was generated but flagged for quality: ${reasons}. You can keep it or regenerate.`;
		}
		if (asText(issue.category) === 'visual_generation_failed' && asText(issue.message).startsWith('image omitted by quality gate:')) {
			const section = asText(issue.section_id) || 'this section';
			return `The image for '${section}' didn't meet quality standards and was left out — you can regenerate it or print text-only.`;
		}
		return String(issue.message ?? 'Unknown issue');
	}

	function visualId(issue: Record<string, unknown>): string {
		const target = asText(issue.repair_target_id);
		return target.startsWith('visual:') ? target.slice('visual:'.length) : '';
	}

	function visualFor(issue: Record<string, unknown>) {
		const id = visualId(issue);
		return pack?.visual_blocks?.find((block) => block.visual_id === id);
	}

	function hintFor(issue: Record<string, unknown>): string {
		const visual = visualFor(issue);
		if (!visual) return '';
		return hints[visual.visual_id] ?? visual.qc_correction_hint ?? '';
	}

	function cardId(issue: Record<string, unknown>): string {
		return asText(issue.category).startsWith('card_')
			? asText(issue.repair_target_id)
			: '';
	}

	function cardHint(issue: Record<string, unknown>): string {
		const id = cardId(issue);
		return hints[id] ?? asText(issue.qc_correction_hint) ?? asText(issue.message);
	}

	async function regenerate(issue: Record<string, unknown>): Promise<void> {
		const visual = visualFor(issue);
		if (!generationId || !visual || pending[visual.visual_id]) return;
		pending[visual.visual_id] = true;
		errors[visual.visual_id] = '';
		try {
			await regenerateV3Visual({
				generation_id: generationId,
				visual_id: visual.visual_id,
				teacher_hint: hintFor(issue)
			});
			await onRegenerated?.();
		} catch (error) {
			errors[visual.visual_id] = error instanceof Error ? error.message : 'Could not regenerate this image.';
		} finally {
			pending[visual.visual_id] = false;
		}
	}

	async function repairCard(issue: Record<string, unknown>): Promise<void> {
		const id = cardId(issue);
		if (!generationId || !id || pending[id]) return;
		pending[id] = true;
		errors[id] = '';
		try {
			await repairV3Card({
				generation_id: generationId,
				card_id: id,
				correction_hint: cardHint(issue)
			});
			await onRegenerated?.();
		} catch (error) {
			errors[id] = error instanceof Error ? error.message : 'Could not repair this concept card.';
		} finally {
			pending[id] = false;
		}
	}
</script>

{#if issues.length}
	<section class="rounded-lg border border-border/60 bg-card px-4 py-3 text-sm">
		<p class="font-semibold">{title}</p>
		<ul class="mt-3 space-y-2">
			{#each issues as issue}
				{@const visual = visualFor(issue)}
				{@const targetCardId = cardId(issue)}
				<li class="rounded-md border border-border/40 bg-background/60 px-3 py-2">
					<div class="flex gap-3">
						{#if asText(issue.category) === 'visual_quality_flagged' && visual?.image_url}
							<img class="h-20 w-20 rounded border object-cover" src={visual.image_url} alt={visual.qc_reasons?.join('; ') || 'Flagged generated image'} />
						{/if}
						<div class="min-w-0 flex-1">
							<p class="font-medium">{issueMessage(issue)}</p>
					{#if issueMeta(issue)}
								<p class="mt-1 text-xs text-muted-foreground">{issueMeta(issue)}</p>
					{/if}
							{#if asText(issue.category) === 'visual_quality_flagged' && visual && generationId}
								<label class="mt-2 block text-xs font-medium" for={`visual-hint-${visual.visual_id}`}>Regeneration note</label>
								<input
									id={`visual-hint-${visual.visual_id}`}
									class="mt-1 w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
									value={hintFor(issue)}
									oninput={(event) => (hints[visual.visual_id] = event.currentTarget.value)}
								/>
								<button
									type="button"
									class="mt-2 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-60"
									disabled={pending[visual.visual_id]}
									onclick={() => regenerate(issue)}
								>{pending[visual.visual_id] ? 'Regenerating…' : 'Regenerate image'}</button
								>
								{#if errors[visual.visual_id]}
									<p class="mt-2 text-xs text-destructive" role="alert">{errors[visual.visual_id]}</p>
								{/if}
							{/if}
							{#if targetCardId && generationId}
								<label class="mt-2 block text-xs font-medium" for={`card-hint-${targetCardId}`}>Card correction</label>
								<textarea
									id={`card-hint-${targetCardId}`}
									class="mt-1 min-h-20 w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
									value={cardHint(issue)}
									oninput={(event) => (hints[targetCardId] = event.currentTarget.value)}
								></textarea>
								<button
									type="button"
									class="mt-2 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-60"
									disabled={pending[targetCardId]}
									onclick={() => repairCard(issue)}
								>{pending[targetCardId] ? 'Repairing…' : 'Repair this card'}</button>
								{#if errors[targetCardId]}<p class="mt-2 text-xs text-destructive" role="alert">{errors[targetCardId]}</p>{/if}
							{/if}
						</div>
					</div>
				</li>
			{/each}
		</ul>
	</section>
{/if}
