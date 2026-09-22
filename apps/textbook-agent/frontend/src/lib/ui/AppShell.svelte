<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { User } from '$lib/types';

	interface Props {
		user: User | null;
		pathname: string;
		children?: Snippet;
	}

	let { user, pathname, children }: Props = $props();

	const links = [
		{ href: '/units', label: 'Home', match: (p: string) => p === '/units' || p.startsWith('/units/') },
		{ href: '/classes', label: 'Classes', match: (p: string) => p.startsWith('/classes') || p.startsWith('/learn/classes') },
		{ href: '/resources', label: 'Resources', match: (p: string) => p.startsWith('/resources') },
		{ href: '/insights', label: 'Insights', match: (p: string) => p.startsWith('/insights') },
		{ href: '/settings', label: 'Settings', match: (p: string) => p.startsWith('/settings') }
	];

	let mobileOpen = $state(false);

	$effect(() => {
		pathname;
		mobileOpen = false;
	});
</script>

<div class="shell">
	<button
		type="button"
		class="menu-toggle"
		aria-label={mobileOpen ? 'Close navigation' : 'Open navigation'}
		aria-expanded={mobileOpen}
		onclick={() => (mobileOpen = !mobileOpen)}
	>
		<span></span><span></span><span></span>
	</button>

	{#if mobileOpen}
		<button type="button" class="scrim" aria-label="Close navigation" onclick={() => (mobileOpen = false)}
		></button>
	{/if}

	<aside class="sidebar" class:open={mobileOpen}>
		<a href="/units" class="brand">Lect<span>i</span>o</a>
		<nav aria-label="Primary">
			{#each links as link}
				<a
					href={link.href}
					class="nav-link"
					aria-current={link.match(pathname) ? 'page' : undefined}
				>
					{link.label}
				</a>
			{/each}
		</nav>
		{#if user}
			<div class="profile">
				<a href="/settings" class="avatar-link" aria-label="Open account settings">
					{#if user.picture_url}
						<img src={user.picture_url} alt="" class="avatar" />
					{:else}
						<span class="avatar initials">
							{(user.name ?? user.email).slice(0, 2).toUpperCase()}
						</span>
					{/if}
					<span class="meta">
						<span class="name">{user.name ?? 'Teacher'}</span>
						<span class="role">Teacher</span>
					</span>
				</a>
			</div>
		{/if}
	</aside>

	<div class="content">
		{#if children}{@render children()}{/if}
	</div>
</div>

<style>
	.shell {
		display: grid;
		grid-template-columns: var(--sidebar-width) 1fr;
		min-height: 100vh;
		background: var(--paper);
	}
	.sidebar {
		position: sticky;
		top: 0;
		align-self: start;
		height: 100vh;
		display: flex;
		flex-direction: column;
		padding: var(--space-5) var(--space-4);
		border-right: 1px solid var(--rule);
		background: color-mix(in srgb, var(--surface) 88%, var(--paper));
		z-index: 40;
	}
	.brand {
		display: inline-block;
		margin: 0.15rem 0.5rem 1.5rem;
		color: var(--ink);
		font-family: var(--font-serif);
		font-size: 1.35rem;
		font-weight: 600;
		letter-spacing: -0.03em;
		text-decoration: none;
	}
	.brand span {
		color: var(--accent);
	}
	nav {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		flex: 1;
	}
	.nav-link {
		padding: 0.55rem 0.75rem;
		border-radius: var(--radius-md);
		color: var(--ink-2);
		font-size: 0.875rem;
		font-weight: 500;
		text-decoration: none;
	}
	.nav-link:hover {
		background: var(--accent-soft);
		color: var(--accent);
	}
	.nav-link[aria-current='page'] {
		background: var(--accent-soft);
		color: var(--accent);
	}
	.profile {
		margin-top: auto;
		padding-top: var(--space-4);
		border-top: 1px solid var(--rule);
	}
	.avatar-link {
		display: flex;
		align-items: center;
		gap: 0.65rem;
		padding: 0.4rem;
		border-radius: var(--radius-md);
		text-decoration: none;
		color: inherit;
	}
	.avatar-link:hover {
		background: var(--surface-2);
	}
	.avatar {
		width: 32px;
		height: 32px;
		border-radius: 50%;
		object-fit: cover;
		flex-shrink: 0;
	}
	.initials {
		display: grid;
		place-items: center;
		background: var(--accent);
		color: #fff;
		font: 600 11px var(--font-sans);
	}
	.meta {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
	.name {
		font-size: 0.8125rem;
		font-weight: 600;
		color: var(--ink);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.role {
		font-size: 0.7rem;
		color: var(--ink-3);
	}
	.content {
		min-width: 0;
		min-height: 100vh;
	}
	.menu-toggle,
	.scrim {
		display: none;
	}

	@media (max-width: 860px) {
		.shell {
			grid-template-columns: 1fr;
		}
		.menu-toggle {
			display: flex;
			flex-direction: column;
			justify-content: center;
			gap: 4px;
			position: fixed;
			top: 0.85rem;
			left: 0.85rem;
			z-index: 50;
			width: 2.4rem;
			height: 2.4rem;
			padding: 0.55rem;
			border: 1px solid var(--rule);
			border-radius: var(--radius-md);
			background: var(--surface);
			cursor: pointer;
		}
		.menu-toggle span {
			display: block;
			height: 2px;
			background: var(--ink);
			border-radius: 1px;
		}
		.sidebar {
			position: fixed;
			left: 0;
			top: 0;
			width: min(280px, 86vw);
			transform: translateX(-105%);
			transition: transform 0.18s ease;
			box-shadow: var(--shadow-md);
		}
		.sidebar.open {
			transform: translateX(0);
		}
		.scrim {
			display: block;
			position: fixed;
			inset: 0;
			z-index: 35;
			border: none;
			background: rgba(22, 33, 28, 0.3);
			cursor: pointer;
		}
		.content {
			padding-top: 3.5rem;
		}
	}
</style>
