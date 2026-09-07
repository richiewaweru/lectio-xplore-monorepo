<script lang="ts">
  import { cn } from '$lib/utils';

  interface Props {
    orientation?: 'horizontal' | 'vertical';
    class?: string;
  }

  let { orientation = 'horizontal', class: className, ...restProps }: Props = $props();
</script>

<div
  role="separator"
  aria-orientation={orientation}
  class={cn(
    'shrink-0 bg-border',
    orientation === 'horizontal' ? 'h-[1px] w-full' : 'h-full w-[1px]',
    className
  )}
  {...restProps}
></div>
