<script lang="ts">
  import { Accordion as AccordionPrimitive, type AccordionRootProps } from 'bits-ui';
  import { cn } from '$lib/utils';
  import type { Snippet } from 'svelte';

  let { children, class: className, ...restProps }: AccordionRootProps & { children?: Snippet; class?: string } = $props();
</script>

<AccordionPrimitive.Root class={cn(className)} {...restProps}>
  {#if children}{@render children()}{/if}
</AccordionPrimitive.Root>
