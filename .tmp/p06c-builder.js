async () => {
  const t = localStorage.getItem('textbook_agent_token');
  const h = {
    Authorization: 'Bearer ' + t,
    'Content-Type': 'application/json',
  };
  const lid = '065b0325-8e73-41d6-9cf0-8d9ccfa5ff6f';
  const get = await fetch('/api/v1/builder/lessons/' + lid, { headers: h });
  const doc = await get.json();
  const rev =
    doc.document_revision || doc.revision || doc.expected_revision || 1;
  const marker = 'P06C-BUILDER-EDIT-' + Date.now();
  const body = doc.document || doc;
  let edited = false;
  const walk = (n) => {
    if (!n || edited) return;
    if (Array.isArray(n)) {
      n.forEach(walk);
      return;
    }
    if (typeof n === 'object') {
      if (typeof n.text === 'string' && n.text.length > 20) {
        n.text = n.text + ' [' + marker + ']';
        edited = true;
        return;
      }
      Object.values(n).forEach(walk);
    }
  };
  walk(body);
  const putPayload = {
    expected_revision: rev,
    document: body.document || body,
  };
  const put = await fetch('/api/v1/builder/lessons/' + lid, {
    method: 'PUT',
    headers: h,
    body: JSON.stringify(putPayload),
  });
  const putj = await put.json().catch(() => ({}));
  const pub = await fetch('/api/v1/learn/lessons/' + lid + '/releases', {
    method: 'POST',
    headers: {
      ...h,
      'Idempotency-Key': 'p06c-pub-' + Date.now(),
    },
    body: JSON.stringify({}),
  });
  const pubj = await pub.json().catch(() => ({}));
  return {
    get: get.status,
    put: put.status,
    put_detail: putj.detail || null,
    put_rev: putj.document_revision || putj.revision || null,
    pub: pub.status,
    release_id: pubj.release_id || pubj.id || null,
    instance_id: pubj.instance_id || null,
    marker,
    edited,
    pub_keys: Object.keys(pubj).slice(0, 25),
    pub_detail: pubj.detail || null,
  };
}
