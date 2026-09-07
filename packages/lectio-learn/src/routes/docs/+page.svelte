<script lang="ts">
	import { getDocsNavigation } from '$lib/navigation/docs-navigation';

	const groups = getDocsNavigation();
</script>

<svelte:head>
	<title>Documentation Ã¢â‚¬â€ Lectio</title>
</svelte:head>

<p class="eyebrow">Documentation</p>
<h1>Lectio documentation</h1>
<p class="lead">
	Guides for using the educational component library in your own Svelte app, wiring multi-section
	lessons, and feeding external pipelines with exported JSON contracts.
</p>

<div class="not-prose mt-10 grid gap-6 sm:grid-cols-2">
	{#each groups as group}
		<section class="rh-radius-card border border-border/70 bg-white/75 p-5 shadow-sm">
			<p class="eyebrow text-xs">{group.eyebrow}</p>
			<ul class="mt-4 rh-gap-component-tight">
				{#each group.items as item}
					<li>
						<a
							href={item.href}
							class="block rounded-xl px-2 py-1.5 transition-colors hover:bg-primary/5"
						>
							<span class="font-semibold text-primary">{item.label}</span>
							<span class="mt-0.5 block text-sm text-muted-foreground">{item.meta}</span>
						</a>
					</li>
				{/each}
			</ul>
		</section>
	{/each}
</div>

<p class="mt-10 text-sm text-muted-foreground">
	Live demos live under
	<a href="/components">Components</a>
	and
	<a href="/templates">Templates</a>
	Ã¢â‚¬â€ this section focuses on consumption, patterns, and contracts.
</p>
