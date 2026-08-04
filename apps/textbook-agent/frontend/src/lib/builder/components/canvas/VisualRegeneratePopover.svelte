<script lang="ts">
	import { regenerateV3Visual, type V3VisualBlock } from '$lib/api/v3';
	import { RefreshCw } from 'lucide-svelte';

	let {
		presentation,
		generationId,
		visual,
		onCompleted = () => {},
		onRegenerated = async () => {}
	}: {
		presentation: 'inline' | 'popover';
		generationId: string | null;
		visual?: V3VisualBlock;
		onCompleted?: (visual: V3VisualBlock) => void | Promise<void>;
		onRegenerated?: () => void | Promise<void>;
	} = $props();

	let open = $state(false);
	let teacherHint = $state('');
	let pending = $state(false);
	let error = $state<string | null>(null);
	let initializedVisualId = $state<string | null>(null);

	$effect(() => {
		const visualId = visual?.visual_id ?? null;
		if (visualId === initializedVisualId) return;
		initializedVisualId = visualId;
		teacherHint = visual?.qc_correction_hint ?? '';
		error = null;
	});

	async function regenerate(): Promise<void> {
		if (!generationId || !visual || pending) return;
		pending = true;
		error = null;
		try {
			const regenerated = await regenerateV3Visual({
				generation_id: generationId,
				visual_id: visual.visual_id,
				teacher_hint: teacherHint.trim()
			});
			await onCompleted(regenerated);
			await onRegenerated();
			if (presentation === 'popover') open = false;
		} catch (reason) {
			error = reason instanceof Error ? reason.message : 'Could not regenerate this image.';
		} finally {
			pending = false;
		}
	}
</script>

{#snippet controls()}
	{#if visual && generationId}
		<label class="block text-xs font-medium" for={`visual-regenerate-hint-${presentation}-${visual.visual_id}`}>
			Regeneration note
		</label>
		<textarea
			id={`visual-regenerate-hint-${presentation}-${visual.visual_id}`}
			class="mt-1 w-full rounded border border-slate-300 bg-white p-2 text-xs"
			rows="2"
			placeholder="Optional correction note"
			bind:value={teacherHint}
		></textarea>
		<button
			type="button"
			class="mt-2 rounded border border-slate-300 bg-white px-2 py-1 text-xs disabled:opacity-60"
			disabled={pending}
			onclick={() => void regenerate()}
		>
			{pending ? 'Regenerating…' : 'Regenerate image'}
		</button>
	{:else}
		<p class="text-xs text-slate-600">This image will be generated on the next lesson build</p>
		<button
			type="button"
			class="mt-2 rounded border border-slate-300 bg-white px-2 py-1 text-xs opacity-60"
			disabled
		>
			Regenerate image
		</button>
	{/if}
	{#if error}<p class="mt-2 text-xs text-red-700" role="alert">{error}</p>{/if}
{/snippet}

{#if presentation === 'inline'}
	<div class="mt-2 w-full">
		{@render controls()}
	</div>
{:else}
	<div class="relative" data-visual-regenerate-root>
		<button
			type="button"
			class="rounded-md p-1.5 text-violet-600 hover:bg-violet-50"
			title="Regenerate image"
			aria-label="Regenerate image"
			onclick={(event) => {
				event.stopPropagation();
				open = !open;
			}}
		>
			<RefreshCw size={16} aria-hidden="true" />
		</button>
		{#if open}
			<div
				class="absolute right-0 top-full z-30 mt-1 w-72 rounded-lg border border-slate-200 bg-white p-3 text-left shadow-lg"
				role="dialog"
				aria-label="Regenerate image"
				tabindex="-1"
			>
				{@render controls()}
			</div>
		{/if}
	</div>
{/if}
