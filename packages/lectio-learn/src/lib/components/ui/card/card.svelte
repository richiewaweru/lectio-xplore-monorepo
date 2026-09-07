<script lang="ts">
  import { cn } from '$lib/utils';
  import type { Snippet } from 'svelte';
  import type { HTMLAttributes } from 'svelte/elements';

  interface Props extends HTMLAttributes<HTMLDivElement> {
    children?: Snippet;
    class?: string;
  }

  let { children, class: className, ...restProps }: Props = $props();
</script>

<div class={cn('rounded-2xl border bg-card text-card-foreground shadow-warm-sm', className)} {...restProps}>
  {#if children}{@render children()}{/if}
</div>
