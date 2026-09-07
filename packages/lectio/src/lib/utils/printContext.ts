import { getContext, setContext } from 'svelte';

const KEY = Symbol('printMode');

/**
 * Provide print mode to child components via context.
 * Pass a getter so the value stays reactive.
 * Called by consuming application or the component showcase.
 */
export function providePrintMode(getter: () => boolean): void {
	setContext(KEY, getter);
}

/**
 * Read print mode from context.
 * Returns a getter — use inside $derived() for reactivity:
 *   const getPrintMode = usePrintMode();
 *   const printMode = $derived(getPrintMode());
 */
export function usePrintMode(): () => boolean {
	return getContext<() => boolean>(KEY) ?? (() => false);
}
