/** True when the focused element is a text field or contenteditable — global shortcuts should not steal keys. */
export function isTextEditingTarget(el: EventTarget | null): boolean {
	if (!(el instanceof HTMLElement)) return false;
	const tag = el.tagName;
	if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
	const ceAttr = el.getAttribute('contenteditable');
	if (ceAttr != null && ceAttr !== 'false') return true;
	// DOM property is the empty string when not set; browsers use "true" / "false" / "inherit"
	if (el.contentEditable === 'true') return true;
	if (el.isContentEditable) return true;
	if (el.closest('[contenteditable="true"]')) return true;
	return false;
}

export function isModifierZ(e: KeyboardEvent): boolean {
	return (e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === 'z';
}

export function isModifierShiftZ(e: KeyboardEvent): boolean {
	return (e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'z';
}

export function isModifierS(e: KeyboardEvent): boolean {
	return (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's';
}

export function isModifierD(e: KeyboardEvent): boolean {
	return (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'd';
}

export function isDeleteOrBackspace(e: KeyboardEvent): boolean {
	return e.key === 'Delete' || e.key === 'Backspace';
}
