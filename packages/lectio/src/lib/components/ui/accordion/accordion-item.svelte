<script lang="ts">
  import { Accordion as AccordionPrimitive } from 'bits-ui';
  import { cn } from '$lib/utils';
  import type { Snippet } from 'svelte';

  interface Props {
    value: string;
    children?: Snippet;
    class?: string;
  }

  let { value, children, class: className, ...restProps }: Props = $props();
</script>

<AccordionPrimitive.Item {value} class={cn('border-b', className)} {...restProps}>
  {#if children}{@render children()}{/if}
</AccordionPrimitive.Item>
