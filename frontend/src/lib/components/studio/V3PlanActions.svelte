<script lang="ts">
	interface Props {
		isRunning?: boolean;
		recoveryAction?: 'retry_failed_sections' | 'resume_stage2' | null;
		onApprove: () => void;
		onRegenerate: (note: string) => void;
		onRecovery: () => void;
	}

	let {
		isRunning = false,
		recoveryAction = null,
		onApprove,
		onRegenerate,
		onRecovery
	}: Props = $props();

	let note = $state('');
	let showAdjust = $state(false);
	let showRegenerate = $state(false);

	function submitAdjust() {
		onRegenerate(note.trim());
		note = '';
		showAdjust = false;
	}

	function submitRegenerate() {
		onRegenerate(note.trim());
		note = '';
		showRegenerate = false;
	}
</script>

<div class="mx-auto max-w-3xl space-y-4 px-4 pb-10">
{#if recoveryAction}
	<div class="rounded-xl border border-destructive/30 bg-destructive/5 p-4">
		<p class="text-sm font-semibold text-destructive">
			{recoveryAction === 'retry_failed_sections'
				? "Some sections didn't complete. You can retry them."
				: 'Generation was interrupted. You can resume from where it left off.'}
		</p>
		<button
			type="button"
			class="mt-3 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
			disabled={isRunning}
			onclick={onRecovery}
		>
			{recoveryAction === 'retry_failed_sections' ? 'Retry failed sections' : 'Resume generation'}
		</button>
	</div>
{:else}
	<div class="flex flex-wrap gap-3">
		<button
			type="button"
			class="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
			disabled={isRunning}
			onclick={onApprove}
		>
			Approve
		</button>
		<button
			type="button"
			class="rounded-md border border-input px-4 py-2 text-sm font-semibold"
			onclick={() => {
				showAdjust = !showAdjust;
				showRegenerate = false;
			}}
		>
			Adjust (regenerate with note)
		</button>
		<button
			type="button"
			class="rounded-md border border-input px-4 py-2 text-sm font-semibold"
			onclick={() => {
				showRegenerate = !showRegenerate;
				showAdjust = false;
			}}
		>
			Regenerate
		</button>
	</div>

	{#if showAdjust || showRegenerate}
		<div class="space-y-3 rounded-xl border border-border/60 bg-card p-4">
			<p class="text-sm text-muted-foreground">
				{showAdjust
					? 'Describe what to adjust; this will regenerate the structural plan with your note.'
					: 'Optional note for regeneration.'}
			</p>
			<textarea
				class="min-h-[90px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
				bind:value={note}
				placeholder="e.g. Keep section 2 shorter and add more warm practice."
			></textarea>
			<button
				type="button"
				class="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
				onclick={showAdjust ? submitAdjust : submitRegenerate}
			>
				Submit
			</button>
		</div>
	{/if}

{/if}
</div>
