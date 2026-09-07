<script lang="ts">
	import { Badge } from '$lib/components/ui/badge';
	import { getDocsNavigation } from '$lib/navigation/docs-navigation';
	import { getSidebarNavigation } from '$lib/navigation/sidebar-navigation';

	let { frameworkLabel }: { frameworkLabel: string } = $props();

	const navigation = getSidebarNavigation();
	const docsNav = getDocsNavigation();
</script>

<aside class="hidden w-72 shrink-0 xl:sticky xl:top-3 xl:block xl:self-start">
	<div class="lesson-shell max-h-[calc(100vh-1.5rem)] p-5">
		<div class="relative z-10 flex max-h-[calc(100vh-3rem)] flex-col">
			<a href="/" class="block shrink-0 space-y-2">
				<div class="flex items-center gap-2">
					<Badge class="bg-primary text-primary-foreground hover:bg-primary">Lectio</Badge>
					<Badge variant="outline">{frameworkLabel}</Badge>
				</div>
				<div>
					<h1 class="text-2xl font-semibold tracking-tight font-serif text-primary">
						Educational components
					</h1>
					<p class="mt-2 text-sm leading-6 text-muted-foreground">
						A component system for teaching moves, not just interface widgets.
					</p>
				</div>
			</a>

			<nav class="mt-6 flex-1 space-y-6 overflow-y-auto pr-1 text-sm scrollbar-styled" aria-label="Primary navigation">
				<div>
					<p class="eyebrow">Documentation</p>
					<ul class="mt-3 space-y-3">
						{#each docsNav as group}
							<li>
								<p class="text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
									{group.eyebrow}
								</p>
								<ul class="mt-2 space-y-1.5">
									{#each group.items as item}
										<li>
											<a
												href={item.href}
												class="block rounded-xl px-3 py-2 text-foreground/80 transition-colors hover:bg-primary/5 hover:text-primary"
											>
												<span class="font-medium">{item.label}</span>
												<span class="mt-1 block text-xs text-muted-foreground">{item.meta}</span>
											</a>
										</li>
									{/each}
								</ul>
							</li>
						{/each}
					</ul>
				</div>

				<div>
					<p class="eyebrow">Components</p>
					<ul class="mt-3 space-y-1.5">
						{#each navigation.components as item}
							<li>
								<a
									href={item.href}
									class="block rounded-xl px-3 py-2 text-foreground/80 transition-colors hover:bg-primary/5 hover:text-primary"
								>
									<span class="font-medium">{item.label}</span>
									<span class="mt-1 block text-xs text-muted-foreground">{item.meta}</span>
								</a>
							</li>
						{/each}
					</ul>
				</div>

				<div>
					<p class="eyebrow">Templates</p>
					<ul class="mt-3 space-y-1.5">
						{#each navigation.templates as item}
							<li>
								<a
									href={item.href}
									class="block rounded-xl px-3 py-2 text-foreground/80 transition-colors hover:bg-primary/5 hover:text-primary"
								>
									<span class="font-medium">{item.label}</span>
									<span class="mt-1 block text-xs text-muted-foreground">{item.meta}</span>
								</a>
							</li>
						{/each}
					</ul>
				</div>
			</nav>
		</div>
	</div>
</aside>
