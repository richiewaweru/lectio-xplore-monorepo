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
const outDir = join(root, 'out');
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
			env: process.env
		}
	);
	child.stderr?.on('data', (chunk) => process.stderr.write(chunk));
	await waitForServer(`${BASE}/`);
	return child;
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
	edition: 'teacher' | 'student'
): Promise<{ pages: number; files: string[] }> {
	const url = `${BASE}/fixtures/photosynthesis-ref?print=1&edition=${edition}`;
	console.log(`Navigating to ${url}`);
	await page.goto(url, { waitUntil: 'networkidle' });

	const hasDocument = await page.locator('.lectio-document').count();
	if (hasDocument < 1) {
		fail('Fixture route did not render .lectio-document from LectioDocumentView');
	}

	await assertObjectCoverage(page, edition === 'teacher');

	const reviewChrome = await page.locator('.lectio-review-chrome').count();
	if (reviewChrome > 0) {
		fail('Print route must not include review chrome');
	}

	const targets =
		edition === 'teacher'
			? [
					{ background: true, name: 'photosynthesis-ref-bg-on.pdf' },
					{ background: false, name: 'photosynthesis-ref-bg-off.pdf' }
				]
			: [{ background: true, name: 'photosynthesis-ref-student.pdf' }];

	const pageCounts: number[] = [];
	const files: string[] = [];

	for (const target of targets) {
		const outPath = join(outDir, target.name);
		await page.pdf({
			path: outPath,
			format: 'A4',
			printBackground: target.background,
			preferCSSPageSize: true
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
		const teacher = await writeEditionPdfs(page, 'teacher');
		const student = await writeEditionPdfs(page, 'student');

		const report = {
			teacher_pages: teacher.pages,
			student_pages: student.pages,
			teacher_files: teacher.files,
			student_files: student.files,
			bg_on_off_page_counts_equal: true,
			ten_objects_in_teacher_dom: true,
			answer_key_teacher_only: true
		};
		writeFileSync(join(outDir, 'pdf-fixture-report.json'), JSON.stringify(report, null, 2));
		console.log('PDF gate OK — teacher (bg on/off) + student; AnswerKeyView on teacher only');
		console.log(JSON.stringify(report));
	} finally {
		await browser.close();
		preview.kill('SIGTERM');
	}
}

main().catch((err) => {
	console.error(err);
	process.exit(1);
});
