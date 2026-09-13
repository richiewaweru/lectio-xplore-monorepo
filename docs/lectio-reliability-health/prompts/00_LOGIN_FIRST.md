# Casa by Grok: do this first, before lengthy implementation
The user wants to authenticate while awake so you can later verify without waiting. Use the browser that YOU will use for final verification, in YOUR execution environment.
1. Inspect local AGENTS.md, working tree, project startup documentation and already-open browser tabs. Preserve existing work and existing authenticated context.
2. Use the repository-documented Docker configuration to start the local services. Discover the local application URL from compose configuration, published ports and startup output; verify the actual served revision. Launch local Chromium through Playwright. This is the verification environment specified by the user; do not ask for a staging URL or use an old public deployment.
3. Start documented dependencies/application if available and authorized. Navigate to the intended login page. Use the supported secure authentication handoff. Never request credentials in chat, print/export cookies, weaken auth or install an auth bypass.
4. Verify login via an authorized page and harmless read. Record non-secret browser/context reference and target origin. Keep the context/profile alive through ordinary supported session reuse; do not close/reset it during testing. Sessions are not transferable by assumption and may expire.
5. Attempt the fresh baseline live journey early; record failures. Then proceed with the remaining phases. Final verification must still be rerun against final code.
6. If login needs the user's action, surface that NOW. Do not wait until the end. If unavailable/expired, mark live readiness BLOCKED, continue offline implementation as dependencies permit and never claim live PASS.
This prompt establishes a session; it does not authorize security changes or public deployment.

## Confirmed user environment
Casa by Grok is the implementing agent. It starts local services with Docker and uses local Chromium via Playwright. Establish login in that local browser before long implementation work. Reuse the same context or a supported persistent local profile; keep authentication data local, out of git and evidence bundles. Ask for interactive login immediately if required. Do not assume this ChatGPT cloud browser supplies authentication. If Docker/Chromium configuration cannot be resolved, report the concrete local blocker.
