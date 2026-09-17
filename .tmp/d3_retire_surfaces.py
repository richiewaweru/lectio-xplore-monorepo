"""D3: unmount unsupported operational surfaces (keep Unit Print v3 hop)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(r"C:\Projects\lectio")
SRC = ROOT / "apps/textbook-agent/backend/src"
FE = ROOT / "apps/textbook-agent/frontend/src"
APP = SRC / "app.py"


def patch_app() -> None:
    text = APP.read_text(encoding="utf-8")
    # Remove imports for retired mounts
    removals = [
        "from generation.skeleton_routes import router as skeleton_router\n",
        "from learn.routes import router as learning_router\n",
        "from curriculum.compatibility import router as compatibility_router\n",
    ]
    for line in removals:
        text = text.replace(line, "")
    text = text.replace(
        "    app.include_router(learning_router)\n",
        "    # D3: /api/v1/packs retired (non-Unit)\n",
    )
    text = text.replace(
        "    app.include_router(skeleton_router)\n",
        "    # D3: /api/v1/skeletons* retired (non-Unit HTTP)\n",
    )
    text = text.replace(
        "    app.include_router(compatibility_router)\n",
        "    # D3: /api/v1/legacy-units retired\n",
    )
    APP.write_text(text, encoding="utf-8")
    print("patched app.py mounts")


def patch_generation_routes() -> None:
    path = SRC / "generation" / "routes.py"
    path.write_text(
        '''from __future__ import annotations

from fastapi import APIRouter

from print.http.v3_studio.router import v3_studio_router

# D3: block_generate_router retired (non-Unit). Unit Print hops remain on v3_studio.
router = APIRouter(prefix="/api/v1", tags=["generation"])
router.include_router(v3_studio_router)
''',
        encoding="utf-8",
    )
    print("patched generation.routes")


def write_redirect_page(path: Path, target: str = "/units") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'''<script lang="ts">
	import {{ browser }} from '$app/environment';
	import {{ goto }} from '$app/navigation';
	import {{ onMount }} from 'svelte';

	onMount(() => {{
		if (browser) {{
			void goto('{target}', {{ replaceState: true }});
		}}
	}});
</script>

<p>This legacy surface was retired. Redirecting to Units…</p>
''',
        encoding="utf-8",
    )
    print("redirect", path.relative_to(FE))


def patch_studio_landing() -> None:
    """Bare /studio without generation_id redirects to /units; with id keep Unit Print UX."""
    path = FE / "routes" / "studio" / "+page.svelte"
    text = path.read_text(encoding="utf-8")
    # Inject early redirect for unsupported standalone entry if not already present
    marker = "D3_STANDALONE_STUDIO_RETIRED"
    if marker in text:
        print("studio already patched")
        return
    inject = f'''
	// {marker}: standalone studio creation is unsupported; Unit Print review keeps generation_id.
	onMount(() => {{
		if (!browser) return;
		const params = new URLSearchParams(window.location.search);
		if (!params.get('generation_id')) {{
			void goto('/units', {{ replaceState: true }});
		}}
	}});
'''
    # studio already imports onMount/browser/goto - insert after imports block
    if "onMount(() => {" in text:
        # prepend our check by wrapping - insert right after script start imports
        needle = "\tonMount(() => {"
        # Find first onMount - add another early one after imports
        idx = text.find("<script lang=\"ts\">")
        end_imports = text.find("\n\n", idx)
        if end_imports == -1:
            end_imports = text.find("\n\t", idx + 20)
        text = text[: end_imports] + "\n" + inject + text[end_imports:]
    else:
        text = text.replace(
            "import { onDestroy, onMount } from 'svelte';",
            "import { onDestroy, onMount } from 'svelte';\n" + inject,
        )
    path.write_text(text, encoding="utf-8")
    print("patched studio landing gate")


def patch_builder_pack_link() -> None:
    path = FE / "routes" / "builder" / "[id]" / "+page.svelte"
    text = path.read_text(encoding="utf-8")
    # Remove packs items href - replace with units home note or hide
    if "/packs/" in text:
        text = text.replace(
            "href={`/packs/${encodeURIComponent(generationId)}/items`}",
            "href={`/units`}",
        )
        path.write_text(text, encoding="utf-8")
        print("patched builder pack link")


def patch_ai_client() -> None:
    path = FE / "lib" / "learn" / "authoring" / "builder" / "api" / "ai-client.ts"
    path.write_text(
        '''import type { GradeBand } from '@lectio/learn';

export type BlockGenerateModelTier = 'FAST' | 'STANDARD';

export interface BlockGenerateContextBlock {
	component_id: string;
	content: Record<string, unknown>;
}

export interface BlockGenerateRequest {
	lesson_id?: string;
	section_id?: string;
	component_id: string;
	mode?: 'fill' | 'improve' | 'custom';
	subject: string;
	focus: string;
	grade_band: GradeBand;
	context_blocks?: BlockGenerateContextBlock[];
	teacher_note?: string;
	existing_content?: Record<string, unknown>;
	model_tier?: BlockGenerateModelTier;
}

export interface BlockGenerateResponse {
	content: Record<string, unknown>;
}

/** D3: /api/v1/blocks/generate retired. */
export async function generateBlock(
	_request: BlockGenerateRequest,
	_token: string
): Promise<BlockGenerateResponse> {
	throw new Error('Block AI assist was retired with the non-Unit blocks/generate API (D3).');
}
''',
        encoding="utf-8",
    )
    print("retired ai-client blocks/generate")


def patch_units_api() -> None:
    import re

    path = FE / "lib" / "api" / "units.ts"
    text = path.read_text(encoding="utf-8")
    text2 = re.sub(
        r"export function listLegacyUnitWrappers\(\)[\s\S]*?\n\}",
        "export function listLegacyUnitWrappers(): Promise<LegacyUnitWrapper[]> {\n"
        "\treturn Promise.reject(new Error('legacy-units API retired (D3)'));\n}",
        text,
        count=1,
    )
    text2 = re.sub(
        r"export function getLegacyUnitWrapper\(packId: string\)[\s\S]*?\n\}",
        "export function getLegacyUnitWrapper(_packId: string): Promise<LegacyUnitWrapper> {\n"
        "\treturn Promise.reject(new Error('legacy-units API retired (D3)'));\n}",
        text2,
        count=1,
    )
    text2 = re.sub(
        r"export function previewSkeleton\([\s\S]*?\n\}",
        "export function previewSkeleton(_objective: string, _lessonMode: LessonMode): Promise<SkeletonPreview> {\n"
        "\treturn Promise.reject(new Error('skeletons:preview API retired (D3)'));\n}",
        text2,
        count=1,
    )
    path.write_text(text2, encoding="utf-8")
    print("patched units.ts retired helpers")


def patch_learning_pack_api() -> None:
    path = FE / "lib" / "api" / "learning-pack.ts"
    if not path.exists():
        return
    original = path.read_text(encoding="utf-8")
    # Keep type imports if present; replace callable implementations.
    path.write_text(
        '''/** D3: /api/v1/packs retired. */

export async function getPackStatus(_packId: string): Promise<never> {
	throw new Error('packs API retired (D3)');
}

export async function listPacks(): Promise<never> {
	throw new Error('packs API retired (D3)');
}

export async function getPack(_packId: string): Promise<never> {
	throw new Error('packs API retired (D3)');
}
'''
        + ("\n/* original exports retired; see git history for pre-D3 client */\n" if original else ""),
        encoding="utf-8",
    )
    print("retired learning-pack.ts")


def main() -> None:
    patch_app()
    patch_generation_routes()
    write_redirect_page(FE / "routes" / "packs" / "[pack_id]" / "+page.svelte")
    write_redirect_page(FE / "routes" / "packs" / "[pack_id]" / "items" / "+page.svelte")
    write_redirect_page(FE / "routes" / "packs" / "[pack_id]" / "print" / "+page.svelte")
    write_redirect_page(FE / "routes" / "units" / "legacy" / "[pack_id]" / "+page.svelte")
    write_redirect_page(FE / "routes" / "builder" / "new" / "+page.svelte")
    # studio/+page already gates blank studio; keep generation_id Unit Print hop
    patch_builder_pack_link()
    patch_ai_client()
    patch_units_api()
    patch_learning_pack_api()


if __name__ == "__main__":
    main()
