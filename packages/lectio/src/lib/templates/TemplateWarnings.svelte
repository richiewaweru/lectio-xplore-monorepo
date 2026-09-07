<script lang="ts">
	import { AlertTriangle } from 'lucide-svelte';

	import { Card } from '$lib/components/ui/card';
	import { validateSection } from '$lib/schema/validate';
	import type { SectionContent } from '$lib/schema/types';

	let { section }: { section: SectionContent } = $props();

	const warnings = $derived(validateSection(section));
</script>

{#if warnings.length}
	<Card class="border-amber-300 bg-amber-50/90" data-schema-warning="true">
		<div class="flex rh-gap-cluster p-4">
			<AlertTriangle class="mt-1 h-5 w-5 text-amber-700" />
			<div>
				<p class="font-semibold text-amber-900">Schema capacity warnings</p>
				<ul class="mt-2 space-y-1 text-sm text-amber-950/80">
					{#each warnings as warning}
						<li>{warning}</li>
					{/each}
				</ul>
			</div>
		</div>
	</Card>
{/if}
