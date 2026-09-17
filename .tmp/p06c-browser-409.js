(async () => {
  const token = localStorage.getItem('textbook_agent_token');
  const gid = '7206057e-5b25-4af8-9a77-40742213efac';
  const rid = '28724db0-b983-4463-a729-97e051db21ed';
  const base = 'http://127.0.0.1:8000';
  const h = { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' };
  const got = await fetch(base + '/api/v1/v3/generations/' + gid + '/lectio-document', { headers: h });
  const body = await got.json();
  const rev = body.document_revision;
  const clone = () => JSON.parse(JSON.stringify(body.document));
  const inject = (doc, m) => {
    const s = JSON.stringify(doc);
    return JSON.parse(s.replace(/\[P06C-PRINT-MARKER-20260913B\]/g, '[P06C-PRINT-MARKER-20260913B] ' + m));
  };
  const a = inject(clone(), 'TAB-A');
  const b = inject(clone(), 'TAB-B');
  const r1 = await fetch(base + '/api/v1/v3/generations/' + gid + '/lectio-document', {
    method: 'PUT', headers: h, body: JSON.stringify({ document: a, expected_document_revision: rev })
  });
  const j1 = await r1.json().catch(() => ({}));
  const r2 = await fetch(base + '/api/v1/v3/generations/' + gid + '/lectio-document', {
    method: 'PUT', headers: h, body: JSON.stringify({ document: b, expected_document_revision: rev })
  });
  const j2 = await r2.json().catch(() => ({}));
  location.reload();
  await new Promise((res) => setTimeout(res, 1500));
  const events = await fetch(base + '/api/v1/realizations/' + rid + '/events?after_seq=0', { headers: h }).then((r) => r.json());
  const status = await fetch(base + '/api/v1/v3/chunked/' + gid + '/status', { headers: h }).then((r) => r.json());
  return {
    rev_before: rev,
    tabA: r1.status,
    tabB: r2.status,
    tabA_rev: j1.document_revision,
    tabB_detail: j2.detail || j2,
    local_tabB_kept: JSON.stringify(b).includes('TAB-B'),
    after_reload_stage: status.stage,
    events_latest: events.latest_seq,
    events_mode: events.mode
  };
})()
