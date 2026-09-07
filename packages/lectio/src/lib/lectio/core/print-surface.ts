/**
 * Assumed print surface for pipeline sizing and preflight.
 * Values are approximate for A4 at ~96dpi content area after typical margins.
 */
export const LECTIO_PRINT_SURFACE = {
	assumed_page: 'A4',
	assumed_margins_mm: { top: 16, right: 14, bottom: 18, left: 14 },
	usable_height_px: 970,
	usable_width_px: 680
} as const;

export type LectioPrintSurface = typeof LECTIO_PRINT_SURFACE;
