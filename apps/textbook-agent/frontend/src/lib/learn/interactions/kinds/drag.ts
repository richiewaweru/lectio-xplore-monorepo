/** Minimal pointer-drag helper (no library). Tap/click keeps working; drag is an extra. */

export interface DragParams {
	disabled?: boolean;
	/** Ignore touch pointers so a finger can still scroll the page (tap-to-place covers touch). */
	mouseOnly?: boolean;
	/** Pixels the pointer must travel before a press counts as a drag. */
	threshold?: number;
	onStart?: () => void;
	onMove?: (x: number, y: number) => void;
	onDrop?: (x: number, y: number) => void;
	onCancel?: () => void;
}

/** The element under a screen point matching `selector` (null where unsupported, e.g. jsdom). */
export function targetAt(x: number, y: number, selector: string): HTMLElement | null {
	if (typeof document === 'undefined' || typeof document.elementFromPoint !== 'function') {
		return null;
	}
	return (document.elementFromPoint(x, y)?.closest(selector) as HTMLElement | null) ?? null;
}

export function pointerDrag(node: HTMLElement, initial: DragParams) {
	let params = initial;
	let pointerId: number | null = null;
	let startX = 0;
	let startY = 0;
	let dragging = false;

	function swallowNextClick() {
		const stop = (e: Event) => {
			e.stopPropagation();
			e.preventDefault();
		};
		node.addEventListener('click', stop, { capture: true, once: true });
		setTimeout(() => node.removeEventListener('click', stop, { capture: true }), 0);
	}

	function finish() {
		window.removeEventListener('pointermove', move);
		window.removeEventListener('pointerup', up);
		window.removeEventListener('pointercancel', cancel);
		node.removeAttribute('data-dragging');
		pointerId = null;
		dragging = false;
	}

	function move(e: PointerEvent) {
		if (e.pointerId !== pointerId) return;
		if (!dragging) {
			const far = Math.hypot(e.clientX - startX, e.clientY - startY) >= (params.threshold ?? 6);
			if (!far) return;
			dragging = true;
			node.setAttribute('data-dragging', 'true');
			params.onStart?.();
		}
		params.onMove?.(e.clientX, e.clientY);
	}

	function up(e: PointerEvent) {
		if (e.pointerId !== pointerId) return;
		const wasDragging = dragging;
		finish();
		if (wasDragging) {
			swallowNextClick();
			params.onDrop?.(e.clientX, e.clientY);
		}
	}

	function cancel(e: PointerEvent) {
		if (e.pointerId !== pointerId) return;
		const wasDragging = dragging;
		finish();
		if (wasDragging) params.onCancel?.();
	}

	function down(e: PointerEvent) {
		if (params.disabled || e.button !== 0 || pointerId !== null) return;
		if (params.mouseOnly && e.pointerType === 'touch') return;
		pointerId = e.pointerId;
		startX = e.clientX;
		startY = e.clientY;
		window.addEventListener('pointermove', move);
		window.addEventListener('pointerup', up);
		window.addEventListener('pointercancel', cancel);
	}

	node.addEventListener('pointerdown', down);
	return {
		update(next: DragParams) {
			params = next;
		},
		destroy() {
			finish();
			node.removeEventListener('pointerdown', down);
		}
	};
}
