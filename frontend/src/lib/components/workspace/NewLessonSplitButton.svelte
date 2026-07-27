<script lang="ts">
	import { onMount } from 'svelte';

	let open = $state(false);
	let root: HTMLDivElement | undefined;
	let menuButton: HTMLButtonElement | undefined;

	onMount(() => {
		function closeFromOutside(event: PointerEvent): void {
			if (root && !root.contains(event.target as Node)) open = false;
		}

		function closeFromKeyboard(event: KeyboardEvent): void {
			if (event.key !== 'Escape' || !open) return;
			open = false;
			menuButton?.focus();
		}

		document.addEventListener('pointerdown', closeFromOutside);
		document.addEventListener('keydown', closeFromKeyboard);
		return () => {
			document.removeEventListener('pointerdown', closeFromOutside);
			document.removeEventListener('keydown', closeFromKeyboard);
		};
	});
</script>

<div class="split-button" bind:this={root}>
	<a class="primary" href="/studio">+ New lesson</a>
	<button
		bind:this={menuButton}
		type="button"
		class="menu-trigger"
		aria-label="More new lesson options"
		aria-expanded={open}
		aria-controls="new-lesson-menu"
		onclick={() => (open = !open)}
	>
		<span aria-hidden="true">⌄</span>
	</button>
	{#if open}
		<div id="new-lesson-menu" class="menu" role="menu">
			<a href="/builder/new" role="menuitem" onclick={() => (open = false)}>Start from blank</a>
		</div>
	{/if}
</div>

<style>
	.split-button {
		position: relative;
		display: inline-flex;
		flex: 0 0 auto;
	}

	.primary,
	.menu-trigger {
		border: 1px solid #1c5d45;
		background: #1c5d45;
		color: #fff;
		font: 600 13px Inter, sans-serif;
	}

	.primary {
		border-radius: 7px 0 0 7px;
		padding: 9px 13px;
		text-decoration: none;
	}

	.menu-trigger {
		display: grid;
		width: 34px;
		place-items: center;
		border-left-color: rgba(255, 255, 255, 0.3);
		border-radius: 0 7px 7px 0;
		cursor: pointer;
		padding: 0;
	}

	.primary:hover,
	.menu-trigger:hover {
		background: #174f3b;
	}

	.primary:focus-visible,
	.menu-trigger:focus-visible,
	.menu a:focus-visible {
		position: relative;
		z-index: 1;
		outline: 2px solid #1c5d45;
		outline-offset: 3px;
	}

	.menu {
		position: absolute;
		top: calc(100% + 7px);
		right: 0;
		z-index: 30;
		min-width: 156px;
		border: 1px solid #d9ded9;
		border-radius: 7px;
		background: #fff;
		box-shadow: 0 12px 28px rgba(24, 35, 29, 0.14);
		padding: 5px;
	}

	.menu a {
		display: block;
		border-radius: 5px;
		color: #24312a;
		font: 500 13px Inter, sans-serif;
		padding: 8px 10px;
		text-decoration: none;
		white-space: nowrap;
	}

	.menu a:hover {
		background: #f1f4f1;
	}

	@media (prefers-reduced-motion: reduce) {
		.primary,
		.menu-trigger {
			transition: none;
		}
	}

	@media (max-width: 640px) {
		.split-button {
			width: 100%;
		}

		.primary {
			flex: 1;
			text-align: center;
		}
	}
</style>
