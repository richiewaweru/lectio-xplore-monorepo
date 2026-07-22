<script lang="ts">
	import { regenerateV3Visual, type V3VisualBlock } from '$lib/api/v3';
	import type { BuilderIssue } from '$lib/builder/issues';

	let {
		issue,
		generationId,
		visual,
		onResolved = () => {},
		onRegenerated = async () => {}
	}: {
		issue: BuilderIssue;
		generationId: string | null;
		visual?: V3VisualBlock;
		onResolved?: (issue: BuilderIssue) => void;
		onRegenerated?: () => void | Promise<void>;
	} = $props();

	let teacherHint = $state('');
	let pending = $state(false);
	let error = $state<string | null>(null);
	const hint = $derived(teacherHint || visual?.qc_correction_hint || '');

	async function regenerate(): Promise<void> {
		if (!generationId || !visual || pending) return;
		pending = true;
		error = null;
		try {
			await regenerateV3Visual({
				generation_id: generationId,
				visual_id: visual.visual_id,
				teacher_hint: hint
			});
			onResolved(issue);
			await onRegenerated();
		} catch (reason) {
			error = reason instanceof Error ? reason.message : 'Could not regenerate this image.';
		} finally {
			pending = false;
		}
	}
</script>

{#if issue.visual_id && visual && generationId}
	<div class="mt-2 w-full">
		{#if visual.image_url}
			<img class="mb-2 h-24 w-24 rounded border object-cover" src={visual.image_url} alt={visual.qc_reasons?.join('; ') || 'Flagged generated image'} />
		{/if}
		<label class="block text-xs font-medium" for={`builder-visual-hint-${issue.id}`}>Regeneration note</label>
		<textarea
			id={`builder-visual-hint-${issue.id}`}
			class="mt-1 w-full rounded border border-amber-300 bg-white p-2 text-xs"
			rows="2"
			placeholder="Optional correction note"
			value={hint}
			oninput={(event) => (teacherHint = event.currentTarget.value)}
		></textarea>
		<button type="button" class="mt-2 rounded border border-amber-400 bg-white px-2 py-1 text-xs disabled:opacity-60" disabled={pending} onclick={() => void regenerate()}>
			{pending ? 'Regenerating…' : 'Regenerate image'}
		</button>
		{#if error}<p class="mt-2 text-xs text-red-700" role="alert">{error}</p>{/if}
	</div>
{/if}
