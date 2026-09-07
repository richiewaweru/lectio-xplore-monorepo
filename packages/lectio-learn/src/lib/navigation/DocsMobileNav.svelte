<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { flattenDocsNavItems } from '$lib/navigation/docs-navigation';

	const items = flattenDocsNavItems();

	function onJump(e: Event) {
		const el = e.currentTarget as HTMLSelectElement;
		const v = el.value;
		if (v) goto(v);
	}
</script>

<nav
	class="xl:hidden mb-4 rounded-[1.25rem] border border-border/80 bg-white/85 p-3 shadow-sm backdrop-blur-sm"
	aria-label="Documentation pages"
>
	<label class="sr-only" for="docs-jump">Jump to documentation page</label>
	<select
		id="docs-jump"
		class="w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm font-medium text-foreground"
		value={page.url.pathname}
		onchange={onJump}
	>
		{#each items as item}
			<option value={item.href}>{item.label}</option>
		{/each}
	</select>
</nav>
