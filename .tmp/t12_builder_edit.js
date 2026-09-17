async () => {
  const token = localStorage.getItem("textbook_agent_token");
  const meResp = await fetch("/api/v1/auth/me", {
    headers: token ? { Authorization: "Bearer " + token } : {},
  });
  const me = await meResp.json();
  if (!me.id) return { auth: false, status: meResp.status, me };
  const h = {
    Authorization: "Bearer " + token,
    "Content-Type": "application/json",
  };
  const id = "c0fc1c46-812f-4a59-abd6-879c11e87d2d";
  const get = await fetch("/api/v1/builder/lessons/" + id, { headers: h });
  const lesson = await get.json();
  const doc = lesson.document || {};
  const nodes = doc.nodes || [];
  const paras = nodes.filter((n) => n.kind === "paragraph");
  const target = paras[1] || paras[0];
  const before = target ? String(target.text || "") : null;
  if (target && !String(target.text || "").includes("T12-CORR-MARKER")) {
    target.text = String(target.text || "") + " [T12-CORR-MARKER]";
  }
  const save = await fetch("/api/v1/builder/lessons/" + id, {
    method: "PUT",
    headers: h,
    body: JSON.stringify({ ...lesson, document: doc }),
  });
  const saveBody = (await save.text()).slice(0, 300);
  const pubPaths = [
    "/api/v1/builder/lessons/" + id + "/publish",
    "/api/v1/builder/lessons/" + id + ":publish",
    "/api/v1/learn/releases",
  ];
  const pubs = [];
  for (const p of pubPaths) {
    const r = await fetch(p, {
      method: "POST",
      headers: h,
      body: JSON.stringify({ lesson_id: id }),
    });
    pubs.push({ p, status: r.status, body: (await r.text()).slice(0, 220) });
  }
  return {
    auth: true,
    get: get.status,
    nodes: nodes.length,
    uniqueIds: new Set(nodes.map((n) => n.id)).size,
    targetId: target && target.id,
    markerPresent: target
      ? String(target.text || "").includes("T12-CORR-MARKER")
      : false,
    beforeSlice: (before || "").slice(0, 80),
    save: save.status,
    saveBody,
    pubs,
  };
}
