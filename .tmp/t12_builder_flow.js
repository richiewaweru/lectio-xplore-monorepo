async (page) => {
  await page.goto("http://127.0.0.1:5173/units");
  const result = await page.evaluate(async () => {
    const token = localStorage.getItem("textbook_agent_token");
    const meResp = await fetch("/api/v1/auth/me", {
      headers: token ? { Authorization: "Bearer " + token } : {},
    });
    const me = await meResp.json();
    if (!me.id) return { auth: false, status: meResp.status };
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
    if (target && !String(target.text || "").includes("T12-CORR-MARKER")) {
      target.text = String(target.text || "") + " [T12-CORR-MARKER]";
    }
    const save = await fetch("/api/v1/builder/lessons/" + id, {
      method: "PUT",
      headers: h,
      body: JSON.stringify({ ...lesson, document: doc }),
    });
    const saveBody = (await save.text()).slice(0, 240);
    const pub = await fetch("/api/v1/learn/lessons/" + id + "/releases", {
      method: "POST",
      headers: h,
      body: JSON.stringify({}),
    });
    const pubBody = (await pub.text()).slice(0, 400);
    let pubJson = null;
    try {
      pubJson = JSON.parse(pubBody);
    } catch {}
    return {
      auth: true,
      get: get.status,
      nodes: nodes.length,
      uniqueIds: new Set(nodes.map((n) => n.id)).size,
      targetId: target && target.id,
      marker: target
        ? String(target.text || "").includes("T12-CORR-MARKER")
        : false,
      save: save.status,
      saveBody,
      publish: pub.status,
      releaseId: pubJson && (pubJson.id || pubJson.release_id),
      releaseNumber: pubJson && pubJson.release_number,
      pubBody,
    };
  });
  console.log(JSON.stringify(result));
  return result;
}
