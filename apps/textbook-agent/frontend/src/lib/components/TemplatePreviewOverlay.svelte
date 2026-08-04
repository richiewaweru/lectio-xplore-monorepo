<script lang="ts">
	import { TemplatePreviewSurface } from 'lectio';

	interface Props {
		open: boolean;
		templateId: string | null;
		templateName: string | null;
		presetId: string | null;
		onclose: () => void;
		onuse: () => void;
	}

	let { open, templateId, templateName, presetId, onclose, onuse }: Props = $props();

	function close() {
		onclose();
	}

	function useTemplate() {
		onuse();
	}

	function handleBackdropClick(event: MouseEvent) {
		if (event.target === event.currentTarget) {
			close();
		}
	}
</script>

{#if open && templateId}
	<div class="overlay-backdrop" role="presentation" onclick={handleBackdropClick}>
		<div
			class="overlay-shell"
			role="dialog"
			aria-modal="true"
			aria-label={`${templateName ?? templateId} preview`}
		>
			<div class="overlay-header">
				<button type="button" class="ghost-button" onclick={close}>Close</button>
			</div>

			<div class="preview-scroll">
				<TemplatePreviewSurface {templateId} presetId={presetId ?? undefined} />
			</div>

			<footer class="overlay-actions">
				<button type="button" class="ghost-button" onclick={close}>Close</button>
				<button type="button" class="primary-button" onclick={useTemplate}>Use Template</button>
			</footer>
		</div>
	</div>
{/if}

<style>
	.overlay-backdrop {
		position: fixed;
		inset: 0;
		z-index: 50;
		display: grid;
		place-items: center;
		padding: 1.25rem;
		background: rgba(17, 30, 45, 0.52);
		backdrop-filter: blur(14px);
	}

	.overlay-shell {
		width: min(1180px, 100%);
		max-height: calc(100vh - 2.5rem);
		display: grid;
		grid-template-rows: auto minmax(0, 1fr) auto;
		gap: 1rem;
		padding: 1rem;
		border-radius: 30px;
		border: 1px solid rgba(205, 220, 236, 0.48);
		background:
			linear-gradient(180deg, rgba(251, 253, 255, 0.92), rgba(235, 244, 252, 0.88)),
			rgba(247, 250, 253, 0.9);
		box-shadow: 0 28px 100px rgba(9, 25, 44, 0.28);
		overflow: hidden;
	}

	.overlay-header,
	.overlay-actions {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
	}

	.preview-scroll {
		min-height: 0;
		overflow: auto;
		border-radius: 24px;
		background: rgba(255, 255, 255, 0.4);
	}

	.ghost-button,
	.primary-button {
		border-radius: 999px;
		padding: 0.75rem 1rem;
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}

	.ghost-button {
		border: 1px solid rgba(36, 67, 106, 0.14);
		background: rgba(36, 67, 106, 0.05);
		color: #24436a;
	}

	.primary-button {
		border: none;
		background: linear-gradient(135deg, #15395f, #1f5f8a);
		color: #fff;
	}

	@media (max-width: 720px) {
		.overlay-backdrop {
			padding: 0.75rem;
		}

		.overlay-shell {
			max-height: calc(100vh - 1.5rem);
			padding: 0.75rem;
		}

		.overlay-header,
		.overlay-actions {
			flex-direction: column;
			align-items: stretch;
		}
	}
</style>
