<script lang="ts">
	import DocsMobileNav from '$lib/navigation/DocsMobileNav.svelte';

	let { children } = $props();
</script>

<div class="page-frame">
	<DocsMobileNav />
	<div class="lesson-shell rh-pad-shell lg:p-10">
		<div class="relative z-10 doc-prose">
			{@render children()}
		</div>
	</div>
</div>
