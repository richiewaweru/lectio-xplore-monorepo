<script lang="ts">
	import { onMount } from 'svelte';
	import { PanelRightClose, PanelRightOpen } from 'lucide-svelte';
	import {
		Dialog,
		DialogClose,
		DialogContent,
		DialogDescription,
		DialogOverlay,
		DialogPortal,
		DialogTitle,
	} from '$lib/components/ui/dialog';
	import type { TemplateContract, TemplatePresetDefinition } from '$lib/templates/types';
	import TemplateContractPanel from '$lib/templates/TemplateContractPanel.svelte';

	const DESKTOP_MEDIA_QUERY = '(min-width: 768px)';
	const STORAGE_KEY = 'template-contract-drawer-open';

	let {
		contract,
		presets,
		desktopOpen = $bindable(false),
		isDesktop = $bindable(false)
	}: {
		contract: TemplateContract;
		presets: TemplatePresetDefinition[];
		desktopOpen?: boolean;
		isDesktop?: boolean;
	} = $props();

	let mobileOpen = $state(false);

	function readDesktopPreference() {
		try {
			return window.localStorage.getItem(STORAGE_KEY) === 'true';
		} catch {
			return false;
		}
	}

	function writeDesktopPreference(value: boolean) {
		try {
			window.localStorage.setItem(STORAGE_KEY, String(value));
		} catch {
			// Ignore storage access failures during SSR/privacy-restricted sessions.
		}
	}

	function syncViewportState(matches: boolean) {
		isDesktop = matches;

		if (matches) {
			desktopOpen = readDesktopPreference();
			mobileOpen = false;
			return;
		}

		desktopOpen = false;
	}

	function handleToggle() {
		if (isDesktop) {
			const next = !desktopOpen;
			desktopOpen = next;
			writeDesktopPreference(next);
			return;
		}

		mobileOpen = true;
	}

	onMount(() => {
		const mediaQuery = window.matchMedia(DESKTOP_MEDIA_QUERY);
		const handleMediaChange = (event: MediaQueryListEvent) => {
			syncViewportState(event.matches);
		};

		syncViewportState(mediaQuery.matches);

		if (typeof mediaQuery.addEventListener === 'function') {
			mediaQuery.addEventListener('change', handleMediaChange);

			return () => {
				mediaQuery.removeEventListener('change', handleMediaChange);
			};
		}

		mediaQuery.addListener(handleMediaChange);

		return () => {
			mediaQuery.removeListener(handleMediaChange);
		};
	});
</script>

<button
	type="button"
	class="inline-flex items-center gap-2 rounded-xl border border-input bg-background px-4 py-2.5 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground"
	aria-expanded={isDesktop ? desktopOpen : mobileOpen}
	onclick={handleToggle}
>
	{#if isDesktop && desktopOpen}
		<PanelRightClose class="h-4 w-4" />
		Hide contract
	{:else}
		<PanelRightOpen class="h-4 w-4" />
		Show contract
	{/if}
</button>

{#if !isDesktop}
	<Dialog bind:open={mobileOpen}>
		<DialogPortal>
			<DialogOverlay class="fixed inset-0 z-40 bg-slate-950/45 backdrop-blur-sm" />
			<DialogContent
				preventScroll={false}
				class="glass-panel fixed inset-y-0 left-0 z-50 h-full w-[min(92vw,32rem)] overflow-y-auto rounded-none rounded-r-[1.75rem] rh-pad-card sm:w-[min(80vw,36rem)]"
			>
				<DialogTitle class="sr-only">Template contract drawer</DialogTitle>
				<DialogDescription class="sr-only">
					Review the template contract on smaller screens.
				</DialogDescription>

				<div class="relative z-10 pr-10">
					<TemplateContractPanel {contract} {presets} />
				</div>

				<DialogClose
					class="absolute right-4 top-4 inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/70 bg-white/72 text-muted-foreground shadow-sm backdrop-blur transition-colors hover:text-foreground"
					aria-label="Close contract"
				>
					<span aria-hidden="true" class="text-sm font-semibold">X</span>
				</DialogClose>
			</DialogContent>
		</DialogPortal>
	</Dialog>
{/if}
