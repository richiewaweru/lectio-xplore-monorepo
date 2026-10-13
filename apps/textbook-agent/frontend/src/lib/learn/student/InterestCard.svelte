<script lang="ts">
	import { learnerFetch } from '$lib/learn/student/api/learner-fetch';

	interface Props {
		source: 'home' | 'topic';
		/** Draw the bordered card and heading. Off when hosted inside a dialog. */
		framed?: boolean;
		onSent?: () => void;
	}

	let { source, framed = true, onSent }: Props = $props();

	const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
	const PHONE_RE = /^[0-9+()\-.\s]{6,30}$/;

	let message = $state('');
	let email = $state('');
	let phone = $state('');
	let website = $state(''); // honeypot, hidden from people
	let sending = $state(false);
	let sent = $state(false);
	let error = $state<string | null>(null);

	function validate(): string | null {
		if (!message.trim()) return 'Tell me a little about what you are curious about.';
		const e = email.trim();
		const p = phone.trim();
		if (!e && !p) return 'Add an email or a phone number so I can reply.';
		if (e && !EMAIL_RE.test(e)) return 'That email does not look right.';
		if (p && (!PHONE_RE.test(p) || p.replace(/\D/g, '').length < 6))
			return 'That phone number does not look right.';
		return null;
	}

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (sending) return;
		error = validate();
		if (error) return;
		sending = true;
		try {
			const response = await learnerFetch('/api/v1/learn/interest', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					message: message.trim(),
					email: email.trim() || null,
					phone: phone.trim() || null,
					source,
					website
				})
			});
			if (response.status === 429) {
				error = 'That is a lot of messages in a short time. Please try again in a little while.';
			} else if (!response.ok) {
				error = 'Something went wrong sending that. Please try again.';
			} else {
				sent = true;
				onSent?.();
			}
		} catch {
			error = 'Could not reach the server. Check your connection and try again.';
		} finally {
			sending = false;
		}
	}
</script>

<section class="interest" class:framed data-testid="interest-card">
	{#if sent}
		<div class="thanks" role="status">
			<h3>Thank you</h3>
			<p>Got it. I will get back to you soon.</p>
		</div>
	{:else}
		{#if framed}
			<h3>Want this for your own topic?</h3>
		{/if}
		<p class="copy">Want this for your own topic, or curious about something? Tell me.</p>
		<form onsubmit={submit} novalidate>
			<label class="field">
				<span>Tell me what you're curious about</span>
				<textarea bind:value={message} rows="5" maxlength="2000"></textarea>
			</label>
			<div class="contact">
				<label class="field">
					<span>Email</span>
					<input type="email" bind:value={email} autocomplete="email" maxlength="254" />
				</label>
				<label class="field">
					<span>Phone</span>
					<input type="tel" bind:value={phone} autocomplete="tel" maxlength="40" />
				</label>
			</div>
			<p class="hint">Email or phone, one is enough</p>
			<div class="trap" aria-hidden="true">
				<label>
					Website
					<input type="text" bind:value={website} tabindex="-1" autocomplete="off" />
				</label>
			</div>
			{#if error}
				<p class="error" role="alert">{error}</p>
			{/if}
			<button type="submit" class="send" disabled={sending}>
				{sending ? 'Sending…' : 'Send'}
			</button>
		</form>
	{/if}
</section>

<style>
	.interest {
		display: grid;
		gap: 10px;
		min-width: 0;
		color: var(--ink);
	}
	.interest.framed {
		border: 1px solid var(--rule);
		border-radius: 12px;
		background: var(--surface);
		padding: 18px;
	}
	h3 {
		margin: 0;
		font: 500 22px/1.2 Fraunces, Georgia, serif;
	}
	.copy {
		margin: 0;
		color: var(--ink-2);
		font-size: 14px;
	}
	form {
		display: grid;
		gap: 12px;
		min-width: 0;
	}
	.field {
		display: grid;
		gap: 4px;
		min-width: 0;
	}
	.field span {
		color: var(--ink-2);
		font-size: 13px;
	}
	textarea,
	input {
		width: 100%;
		box-sizing: border-box;
		border: 1px solid var(--rule);
		border-radius: 8px;
		background: var(--paper);
		color: var(--ink);
		padding: 10px 12px;
		font: inherit;
		font-size: 16px;
	}
	textarea {
		resize: vertical;
		min-height: 120px;
	}
	textarea:focus-visible,
	input:focus-visible,
	.send:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 1px;
	}
	.contact {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 12px;
	}
	.hint {
		margin: -4px 0 0;
		color: var(--ink-3);
		font-size: 12px;
	}
	.trap {
		position: absolute;
		left: -10000px;
		width: 1px;
		height: 1px;
		overflow: hidden;
	}
	.error {
		margin: 0;
		color: var(--amber, #b45309);
		font-size: 14px;
	}
	.send {
		justify-self: start;
		border: 0;
		border-radius: 8px;
		background: var(--accent);
		color: var(--paper);
		padding: 10px 20px;
		font-family: inherit;
		font-size: 14px;
		font-weight: 550;
		cursor: pointer;
	}
	.send:disabled {
		opacity: 0.6;
		cursor: default;
	}
	.thanks p {
		margin: 6px 0 0;
		color: var(--ink-2);
	}
</style>
