async (page) => {
  const result = await page.evaluate(async () => {
    const token = localStorage.getItem("textbook_agent_token");
    const h = {
      Authorization: "Bearer " + token,
      "Content-Type": "application/json",
    };
    const out = {};

    // Attempt: create instance then submit
    const releaseId = "41a2e657-203f-4e29-b948-a8ca97cef7eb";
    const inst = await fetch("/api/v1/learn/instances", {
      method: "POST",
      headers: h,
      body: JSON.stringify({ release_id: releaseId }),
    });
    const instBody = await inst.text();
    let instJson = null;
    try {
      instJson = JSON.parse(instBody);
    } catch {}
    out.instance = {
      status: inst.status,
      id: instJson && (instJson.id || instJson.instance_id),
      body: instBody.slice(0, 300),
    };
    if (out.instance.id) {
      const attempt = await fetch(
        "/api/v1/learn/instances/" + out.instance.id + "/attempts",
        {
          method: "POST",
          headers: h,
          body: JSON.stringify({
            responses: {},
            submission_id: "corr-t12-" + Date.now(),
          }),
        }
      );
      out.attempt = {
        status: attempt.status,
        body: (await attempt.text()).slice(0, 300),
      };
    }

    // Print PDF: try legacy ready print and new queued print endpoints
    const printIds = [
      "7d2e4b2b-04bd-49f5-a860-2fe0d70c5ea9",
      "7fc2a387-b963-42ed-8fa7-b7a40a71cf0f",
    ];
    out.pdfs = [];
    for (const id of printIds) {
      const paths = [
        "/api/v1/v3/generations/" + id + "/pdf",
        "/api/v1/v3/generations/" + id + "/lectio-document.pdf",
        "/api/v1/print/generations/" + id + "/pdf",
        "/api/v1/studio/print/" + id + "/pdf",
      ];
      for (const p of paths) {
        const r = await fetch(p, { headers: h });
        const buf = await r.arrayBuffer();
        out.pdfs.push({
          id,
          p,
          status: r.status,
          bytes: buf.byteLength,
          ct: r.headers.get("content-type"),
        });
      }
      const st = await (
        await fetch("/api/v1/v3/chunked/" + id + "/status", { headers: h })
      ).json();
      out["status_" + id.slice(0, 8)] = {
        stage: st.stage,
        sections_ready: st.sections_ready,
        document_exists: st.document_exists,
      };
    }

    // Edit existing ready print via page document if available
    const readyPrint = "7d2e4b2b-04bd-49f5-a860-2fe0d70c5ea9";
    const doc = await fetch("/api/v1/v3/generations/" + readyPrint + "/document", {
      headers: h,
    });
    const docText = await doc.text();
    out.readyPrintDoc = {
      status: doc.status,
      hasLearnMarker: docText.includes("T12-CORR-MARKER"),
      len: docText.length,
      snippet: docText.slice(0, 160),
    };
    return out;
  });
  console.log(JSON.stringify(result));
  return result;
}
