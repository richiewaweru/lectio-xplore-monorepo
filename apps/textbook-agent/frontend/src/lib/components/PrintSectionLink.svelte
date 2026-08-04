<script lang="ts">
	import qrcode from 'qrcode-generator';
	import type { SectionContent } from 'lectio';

	interface Props {
		generationId: string;
		section: SectionContent;
	}

	let { generationId, section }: Props = $props();

	const isInteractive = $derived(!!section.simulation);
	const sectionTitle = $derived(section.header?.title ?? 'Interactive section');
	const sectionUrl = $derived.by(() => {
		if (typeof window === 'undefined') {
			return '';
		}
		return `${window.location.origin}/studio/generations/${generationId}#section-${section.section_id}`;
	});
	const qrSvg = $derived.by(() => {
		if (!isInteractive || !sectionUrl) {
			return '';
		}
		const code = qrcode(0, 'M');
		code.addData(sectionUrl);
		code.make();
		return code.createSvgTag({ scalable: true, margin: 0 });
	});
</script>

{#if isInteractive && qrSvg}
	<aside class="print-section-link" data-print-only="true">
		<div class="qr-wrap">
			{@html qrSvg}
		</div>
		<div class="qr-copy">
			<p class="qr-label">Interactive simulation</p>
			<h4>{sectionTitle}</h4>
			<p>Scan to open and interact with this simulation in your browser.</p>
			<p class="qr-url">{sectionUrl}</p>
		</div>
	</aside>
{/if}

<style>
	.print-section-link {
		display: grid;
		grid-template-columns: 112px 1fr;
		gap: var(--rh-gap-component, 1rem);
		align-items: center;
		padding: var(--rh-pad-card-tight, 1rem);
		border: 1px dashed rgba(31, 43, 52, 0.25);
		border-radius: var(--rh-radius-card, 18px);
		background: rgba(255, 251, 244, 0.82);
	}

	.qr-wrap :global(svg) {
		display: block;
		width: 112px;
		height: 112px;
	}

	.qr-copy h4,
	.qr-copy p {
		margin: 0;
	}

	.qr-copy {
		display: grid;
		gap: var(--space-1, 0.35rem);
	}

	.qr-label,
	.qr-url {
		font-size: var(--rh-eyebrow-size, 0.78rem);
		letter-spacing: var(--rh-eyebrow-tracking, 0.08em);
		text-transform: uppercase;
		color: #5f574d;
		word-break: break-word;
	}
	@media not print {
		.print-section-link {
			display: none;
		}
	}
</style>
