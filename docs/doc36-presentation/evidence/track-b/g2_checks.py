"""G2 mechanical checks over the rendered Track B PDFs (stdlib + poppler only).

Run:  python g2_checks.py   -> writes g2-checks.json and prints it.
"""
from pathlib import Path
import json, re, subprocess, tempfile, xml.etree.ElementTree as ET

import os
POPPLER = os.environ.get('POPPLER_BIN', '')
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PDF = HERE / 'pdf'
FIX = ROOT / 'packages/lectio-page/fixtures'


def sh(*a):
    a = (os.path.join(POPPLER, a[0]),) + a[1:] if POPPLER else a
    return subprocess.check_output(list(a), text=True, encoding='utf8')


def text(p, *flags):
    return sh('pdftotext', *flags, str(p), '-')


CASES = {
    'golden': ('shared-lesson-golden', 'shared-lesson-golden-student.pdf', 'shared-lesson-golden-bg-on.pdf'),
    'overlong': ('shared-lesson-overlong', 'shared-lesson-overlong-student.pdf', 'shared-lesson-overlong-bg-on.pdf'),
    'legacy': ('shared-lesson-legacy', 'shared-lesson-legacy-student.pdf', None),
    'stress': ('oversized-stress', 'oversized-stress-student.pdf', 'oversized-stress-bg-on.pdf'),
}
res = {}


def pages(p):
    return int(re.search(r'Pages:\s+(\d+)', sh('pdfinfo', str(p))).group(1))


def plain(v):
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return ''.join(plain(x) for x in v)
    if isinstance(v, dict):
        if 'value' in v:
            return str(v['value'])
        return plain(v.get('children', []))
    return ''


def load(fx):
    return json.loads((FIX / (fx + '.json')).read_text(encoding='utf8'))


def answer_entries(doc):
    return [e for g in doc.get('answer_key', {}).get('content', {}).get('groups', []) for e in g['entries']]


# 1. page counts
res['page_counts'] = {k: {'student': pages(PDF / s), 'teacher': pages(PDF / t) if t else None} for k, (_, s, t) in CASES.items()}
res['overlong_more_pages_than_golden'] = res['page_counts']['overlong']['student'] > res['page_counts']['golden']['student']


# 2. forbidden strings
def fixture_ids(doc):
    ids = set()

    def walk(v):
        if isinstance(v, dict):
            for k, x in v.items():
                if k in ('id', 'question_id') and isinstance(x, str):
                    ids.add(x)
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(doc.get('sections', []))
    return ids


forb = {}
for k, (fx, s, t) in CASES.items():
    doc = load(fx)
    ids = {i for i in fixture_ids(doc) if not re.fullmatch(r'Q\d+', i)}
    for name in [s] + ([t] if t else []):
        low = text(PDF / name).lower()
        hits = [n for n in ['choice-', 'shared-node-', 'task-'] if n in low]
        for i in sorted(ids):
            # single plain words (e.g. an intent such as 'explain') are indistinguishable from prose; only machine-shaped ids are flagged
            if re.search(r'[-_0-9]', i) and len(i) > 3 and re.search(r'(?<![a-z0-9])' + re.escape(i.lower()) + r'(?![a-z0-9])', low):
                hits.append('section/block id literal: ' + i)
        forb[name] = hits
res['forbidden_string_hits'] = forb

# 3. learner pages carry no answer / feedback / option note; teacher page markers
leak, teach = {}, {}
norm = lambda x: re.sub(r'\W+', ' ', x.lower()).strip()
for k, (fx, s, t) in CASES.items():
    doc = load(fx)
    entries = answer_entries(doc)
    secrets = []
    for e in entries:
        for key in ('feedback', 'rubric', 'working'):
            if e.get(key):
                secrets.append(plain(e[key]))
        for note in (e.get('option_notes') or {}).values():
            secrets.append(plain(note))
    raw = text(PDF / s)
    stu = norm(raw)
    low = raw.lower()
    leak[k] = {
        'secret_snippets_checked': len(secrets),
        'snippets_found_on_learner_pages': [x[:60] for x in secrets if x and norm(x) in stu],
        'teacher_markers_on_learner_pages': [m for m in ['teacher copy', 'answer key', 'feedback:', 'teacher note', 'not marked'] if m in low],
    }
    if t:
        tt = text(PDF / t)
        tl = tt.lower()
        n = len(entries)
        teach[k] = {
            'teacher_copy_label': 'teacher copy' in tl,
            'questions_in_answer_key': n,
            'all_Q1_to_Qn_present': all(re.search(r'\bQ%d\b' % i, tt) for i in range(1, n + 1)),
            'prediction_not_marked_text': 'not marked' in tl,
            'option_note_keys': sorted({kk for e in entries for kk in (e.get('option_notes') or {})}),
        }
res['learner_leakage'] = leak
res['teacher_page'] = teach

# 3b. answer-key entries per question compared to learner Q numbers
qn = {}
for k, (fx, s, t) in CASES.items():
    if not t:
        continue
    st = sorted(set(re.findall(r'QUESTION (\d+)', text(PDF / s))), key=int)  # task header strips
    tc = text(PDF / t)
    tq = sorted(set(re.findall(r'\bQ(\d+)\b', tc.split('Teacher copy', 1)[-1])), key=int)
    qn[k] = {'learner_pages': st, 'teacher_answer_page': tq, 'match': st == tq}
res['q_numbers'] = qn

# 4. legacy paragraphs and ordered list
lay = text(PDF / 'shared-lesson-legacy-student.pdf', '-layout')
p1 = lay.split('\f')[0]
paras = [x for x in re.split(r'\n\s*\n', p1) if len(x.split()) > 12]
nums = re.findall(r'^\s*(\d)\s{2,}\S', lay, re.M)  # outlined numeral circle, then the item text
res['legacy'] = {
    'page1_paragraph_blocks_over_12_words': len(paras),
    'source_paragraph_count_block0': len(load('shared-lesson-legacy')['sections'][0]['blocks'][0]['content']['paragraphs']),
    'ordered_list_numbers_seen': nums,
    'numbered_1_to_5': all(str(i) in nums for i in range(1, 6)),
}


# 4b. no hyphenation at line ends (a line ending letter+hyphen in layout text)
res['line_end_hyphenation'] = {
    name: [l.strip()[-40:] for l in text(PDF / name, '-layout').splitlines() if re.search(r'[A-Za-z]-\s*$', l)]
    for name in sorted({s for _, s, _ in CASES.values()} | {t for _, _, t in CASES.values() if t})
}


# 4c. task header strips and section badges present in learner PDFs
def _tasks(name):
    low = text(PDF / name)
    found = re.findall(r'QUESTION \d+(?:[^\w\n]+[A-Z]+)?', low)
    return [re.sub(r'[^\x20-\x7e]+', '.', m) for m in found]  # middle dot shown as "."


res['task_header_text'] = {
    'shared-lesson-golden-student.pdf': _tasks('shared-lesson-golden-student.pdf'),
    'shared-lesson-legacy-student.pdf': _tasks('shared-lesson-legacy-student.pdf'),
}

# 5. geometry
def bbox_report(pdf):
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / 'b.html'
        subprocess.check_call([os.path.join(POPPLER, 'pdftotext'), '-bbox', str(pdf), str(out)])
        src = out.read_text(encoding='utf8')
    src = re.sub(r'<!DOCTYPE[^>]*>', '', src).replace('xmlns="http://www.w3.org/1999/xhtml"', '')
    root = ET.fromstring(src)
    bad_edge, overlaps, nwords = [], 0, 0
    mm = 72 / 25.4
    for pi, page in enumerate(root.iter('page'), 1):
        W, H = float(page.get('width')), float(page.get('height'))
        ws = [(float(w.get('xMin')), float(w.get('yMin')), float(w.get('xMax')), float(w.get('yMax')), w.text) for w in page.iter('word')]
        nwords += len(ws)
        for x0, y0, x1, y1, t in ws:
            if x0 < 15 * mm or x1 > W - 15 * mm or y0 < 0 or y1 > H:
                bad_edge.append((pi, t))
        ws.sort()
        for i, a in enumerate(ws):
            for b in ws[i + 1:]:
                if b[0] >= a[2]:
                    break
                ix = min(a[2], b[2]) - max(a[0], b[0])
                iy = min(a[3], b[3]) - max(a[1], b[1])
                if ix > 1.5 and iy > 0.4 * min(a[3] - a[1], b[3] - b[1]):
                    overlaps += 1
    return {'words': nwords, 'outside_count': len(bad_edge), 'outside_sample': bad_edge[:8], 'overlapping_word_pairs': overlaps}


res['geometry_16mm_margins_and_overlap'] = {p.name: bbox_report(p) for p in sorted(PDF.glob('*.pdf')) if 'bg-off' not in p.name}


# 6. colourless render
def colour_pixels(pdf, tol=2):
    with tempfile.TemporaryDirectory() as d:
        subprocess.check_call([os.path.join(POPPLER, 'pdftoppm'), '-r', '40', str(pdf), str(Path(d) / 'p')])
        n = 0
        for f in Path(d).glob('p*.ppm'):
            b = f.read_bytes()
            m = re.match(rb'P6\s+(\d+)\s+(\d+)\s+(\d+)\s', b)
            data = b[m.end():]
            for i in range(0, len(data) - 2, 3):
                if max(data[i:i + 3]) - min(data[i:i + 3]) > tol:
                    n += 1
        return n


res['colour_pixels_in_colour_render_tol2'] = {p.name: colour_pixels(p) for p in sorted(PDF.glob('*golden*.pdf'))}

(HERE / 'g2-checks.json').write_text(json.dumps(res, indent=2, ensure_ascii=False) + '\n', encoding='utf8')
print(json.dumps(res, indent=1, ensure_ascii=False))
