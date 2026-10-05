/**
 * Render the photosynthesis fixture to A4 PDFs via the real Svelte components.
 *
 * Preferred path (PATCH v1.3 P0/P7): build → preview → Playwright drives
 * `/fixtures/photosynthesis-ref?print=1` which mounts LectioDocumentView.
 *
 * Usage: pnpm pdf:fixture
 */
import { spawn, type ChildProcess } from 'node:child_process';
import { mkdirSync, statSync, existsSync, writeFileSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium, type Browser, type Page } from 'playwright';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const outDir = process.env.PDF_OUT_DIR
	? process.env.PDF_OUT_DIR.startsWith('/') || /^[A-Za-z]:[\\/]/.test(process.env.PDF_OUT_DIR)
		? process.env.PDF_OUT_DIR
		: join(root, process.env.PDF_OUT_DIR)
	: join(root, 'out');
mkdirSync(outDir, { recursive: true });

const PREVIEW_PORT = Number(process.env.PDF_PREVIEW_PORT ?? 4173);
const BASE = process.env.DEV_URL ?? `http://127.0.0.1:${PREVIEW_PORT}`;

const OBJECT_SELECTORS: Record<string, string> = {
	heading: '.lectio-heading-binding',
	prose: '.lectio-main p',
	list: '.lectio-list',
	table: '.lectio-table',
	figure: '.lectio-figure',
	aside: '.lectio-aside',
	equation: '.lectio-equation',
	quote: '.lectio-quote',
	compare: '.lectio-compare',
	'worked-example': '.lectio-worked-example',
	questions: '.lectio-question',
	choices: '.lectio-choices',
	'answer-key': '.lectio-answer-key'
};

function fail(message: string): never {
	console.error(message);
	process.exit(1);
}

async function ensureChromium(): Promise<Browser> {
	try {
		return await chromium.launch();
	} catch (err) {
		fail(
			`Playwright Chromium is not available.\n` +
				`On a clean clone run: pnpm install  (postinstall installs Chromium)\n` +
				`Or manually: pnpm exec playwright install chromium\n` +
				`Original error: ${err instanceof Error ? err.message : String(err)}`
		);
	}
}

function run(cmd: string, args: string[]): Promise<void> {
	return new Promise((resolve, reject) => {
		const child = spawn(cmd, args, {
			cwd: root,
			stdio: 'inherit',
			shell: true,
			env: process.env
		});
		child.on('exit', (code) => {
			if (code === 0) resolve();
			else reject(new Error(`${cmd} ${args.join(' ')} exited ${code}`));
		});
	});
}

async function waitForServer(url: string, timeoutMs = 60_000): Promise<void> {
	const start = Date.now();
	while (Date.now() - start < timeoutMs) {
		try {
			const res = await fetch(url);
			if (res.ok || res.status === 404) return;
		} catch {
			/* retry */
		}
		await new Promise((r) => setTimeout(r, 400));
	}
	fail(`Timed out waiting for preview server at ${url}`);
}

async function startPreview(): Promise<ChildProcess> {
	const child = spawn(
		'pnpm',
		['exec', 'vite', 'preview', '--host', '127.0.0.1', '--port', String(PREVIEW_PORT)],
		{
			cwd: root,
			stdio: 'pipe',
			shell: true,
			detached: process.platform !== 'win32',
			env: process.env
		}
	);
	child.stderr?.on('data', (chunk) => process.stderr.write(chunk));
	try {
		await waitForServer(`${BASE}/`);
		return child;
	} catch (error) {
		await stopPreview(child);
		throw error;
	}
}

async function stopPreview(preview: ChildProcess): Promise<void> {
	if (preview.pid === undefined || preview.exitCode !== null) return;

	if (process.platform === 'win32') {
		// `shell: true` runs pnpm.cmd via cmd.exe; killing only the pnpm wrapper
		// leaves Vite serving on the preview port. Terminate just this spawned
		// process tree so no unrelated preview or dev server is touched.
		await new Promise<void>((resolve) => {
			const killer = spawn('taskkill', ['/PID', String(preview.pid), '/T', '/F'], {
				stdio: 'ignore',
				windowsHide: true
			});
			killer.once('error', () => resolve());
			killer.once('exit', () => resolve());
		});
		return;
	}

	try {
		process.kill(-preview.pid, 'SIGTERM');
	} catch {
		preview.kill('SIGTERM');
	}
}

function pdfPageCount(pdfPath: string): number {
	const buf = readFileSync(pdfPath);
	const text = buf.toString('latin1');
	const matches = text.match(/\/Type\s*\/Page(?![s])/g);
	return matches?.length ?? 0;
}

async function assertObjectCoverage(page: Page, requireAnswerKey: boolean): Promise<void> {
	const missing: string[] = [];
	for (const [object, selector] of Object.entries(OBJECT_SELECTORS)) {
		if (object === 'answer-key' && !requireAnswerKey) continue;
		const count = await page.locator(selector).count();
		if (count < 1) missing.push(`${object} (${selector})`);
	}
	if (missing.length) {
		fail(`Fixture DOM missing page objects: ${missing.join(', ')}`);
	}
	if (requireAnswerKey) {
		const ak = await page.locator('.lectio-answer-key').count();
		if (ak < 1) fail('Teacher edition must render AnswerKeyView (.lectio-answer-key)');
	} else {
		const ak = await page.locator('.lectio-answer-key').count();
		if (ak > 0) fail('Student edition must not render answer-key');
	}
}

async function writeEditionPdfs(
	page: Page,
	fixtureId: string,
	edition: 'teacher' | 'student',
	requireFullCoverage: boolean
): Promise<{ pages: number; files: string[] }> {
	const url = `${BASE}/fixtures/${fixtureId}?print=1&edition=${edition}`;
	console.log(`Navigating to ${url}`);
	await page.goto(url, { waitUntil: 'networkidle' });

	const hasDocument = await page.locator('.lectio-document').count();
	if (hasDocument < 1) {
		fail('Fixture route did not render .lectio-document from LectioDocumentView');
	}

	if (requireFullCoverage) {
		await assertObjectCoverage(page, edition === 'teacher');
	}

	const reviewChrome = await page.locator('.lectio-review-chrome').count();
	if (reviewChrome > 0) {
		fail('Print route must not include review chrome');
	}
	// Chromium's PDF engine supplies reliable pageNumber/totalPages tokens;
	// remove the screen-only fixed footer before emitting the PDF.
	await page.locator('.lectio-page-footer').evaluateAll((nodes) => nodes.forEach((node) => node.remove()));
	const runningHeadText = await page.locator('.lectio-running-head').innerText();
	await page.locator('.lectio-running-head').evaluateAll((nodes) => nodes.forEach((node) => node.remove()));
	const safeRunningHead = runningHeadText.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');

	const targets =
		edition === 'teacher'
			? [
					{ background: true, name: `${fixtureId}-bg-on.pdf` },
					{ background: false, name: `${fixtureId}-bg-off.pdf` }
				]
			: [{ background: true, name: `${fixtureId}-student.pdf` }];

	const pageCounts: number[] = [];
	const files: string[] = [];

	for (const target of targets) {
		const outPath = join(outDir, target.name);
		await page.pdf({
			path: outPath,
			format: 'A4',
			printBackground: target.background,
			preferCSSPageSize: true,
			displayHeaderFooter: true,
			headerTemplate: '<span></span>',
			footerTemplate:
				`<div style="width:100%;padding:0 16mm;box-sizing:border-box;"><div style="display:flex;justify-content:space-between;border-top:1px solid #767676;padding-top:2pt;color:#767676;font:9pt Atkinson Hyperlegible,sans-serif;"><span>${safeRunningHead}</span><span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div></div>`
		});

		if (!existsSync(outPath) || statSync(outPath).size === 0) {
			fail(`PDF missing or empty: ${outPath}`);
		}

		const pages = pdfPageCount(outPath);
		if (pages < 1) {
			fail(`PDF has zero pages: ${outPath}`);
		}
		pageCounts.push(pages);
		files.push(target.name);
		console.log(`Wrote ${target.name} (${statSync(outPath).size} bytes, ${pages} pages)`);
	}

	if (edition === 'teacher' && pageCounts[0] !== pageCounts[1]) {
		fail(
			`Page count mismatch with printBackground on/off: ${pageCounts[0]} vs ${pageCounts[1]}.`
		);
	}

	return { pages: pageCounts[0], files };
}

// photosynthesis-ref is the full-catalogue gate: it must exercise all ten page
// objects and the teacher-only answer key. margin-stress is a geometry-only
// fixture (adjacent asides, an aside near a page break) and does not carry an
// answer_key or every object type, so it skips that coverage assertion.
const FIXTURES: Array<{ id: string; requireFullCoverage: boolean; editions: Array<'teacher' | 'student'> }> = [
	{ id: 'photosynthesis-ref', requireFullCoverage: true, editions: ['teacher', 'student'] },
	{ id: 'margin-stress', requireFullCoverage: false, editions: ['teacher'] },
	{ id: 'shared-lesson-legacy', requireFullCoverage: false, editions: ['student'] },
	{ id: 'shared-lesson-golden', requireFullCoverage: false, editions: ['student', 'teacher'] },
	{ id: 'oversized-stress', requireFullCoverage: true, editions: ['student', 'teacher'] },
	{ id: 'shared-lesson-overlong', requireFullCoverage: false, editions: ['student', 'teacher'] }
	,
	{ id: 'track-c-photosynthesis-print', requireFullCoverage: false, editions: ['student'] },
	{ id: 'track-c-formula-print', requireFullCoverage: false, editions: ['student'] },
	{ id: 'track-c-comparison-print', requireFullCoverage: false, editions: ['student'] }
];

const selectedFixtureIds = process.env.PDF_FIXTURES
	?.split(',')
	.map((id) => id.trim())
	.filter(Boolean);

async function main(): Promise<void> {
	// Fail fast before the expensive build if Chromium is missing.
	const probe = await ensureChromium();
	await probe.close();

	console.log('Building app (real LectioDocumentView path)…');
	await run('pnpm', ['build']);

	console.log('Starting preview…');
	const preview = await startPreview();
	const browser = await ensureChromium();

	try {
		const page = await browser.newPage();
		const report: Record<string, unknown> = {};

		const fixtures = selectedFixtureIds
			? FIXTURES.filter((fixture) => selectedFixtureIds.includes(fixture.id))
			: FIXTURES;
		if (fixtures.length === 0) {
			fail(`No configured fixtures match PDF_FIXTURES=${process.env.PDF_FIXTURES}`);
		}

		for (const fixture of fixtures) {
			for (const edition of fixture.editions) {
				const result = await writeEditionPdfs(page, fixture.id, edition, fixture.requireFullCoverage);
				report[`${fixture.id}_${edition}_pages`] = result.pages;
				report[`${fixture.id}_${edition}_files`] = result.files;
			}
		}

		writeFileSync(join(outDir, 'pdf-fixture-report.json'), JSON.stringify(report, null, 2));
		console.log('PDF gate OK — all fixtures rendered');
		console.log(JSON.stringify(report));
	} finally {
		try {
			await browser.close();
		} finally {
			await stopPreview(preview);
		}
	}
}

main().catch((err) => {
	console.error(err);
	process.exit(1);
});
