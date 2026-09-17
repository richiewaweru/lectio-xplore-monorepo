async (page) => {
  const result = await page.evaluate(async () => {
    const token = localStorage.getItem("textbook_agent_token");
    const h = {
      Authorization: "Bearer " + token,
      "Content-Type": "application/json",
    };
    const out = {};
    const me = await (await fetch("/api/v1/auth/me", { headers: h })).json();

    // Create learner + instance + attempt
    const learner = await fetch("/api/v1/learn/learners", {
      method: "POST",
      headers: h,
      body: JSON.stringify({ display_name: "T12 Corr Learner" }),
    });
    const learnerBody = await learner.text();
    let learnerJson = null;
    try {
      learnerJson = JSON.parse(learnerBody);
    } catch {}
    out.learner = {
      status: learner.status,
      id: learnerJson && learnerJson.id,
      body: learnerBody.slice(0, 200),
    };

    const releaseId = "41a2e657-203f-4e29-b948-a8ca97cef7eb";
    if (out.learner.id) {
      const inst = await fetch("/api/v1/learn/instances", {
        method: "POST",
        headers: h,
        body: JSON.stringify({
          learner_id: out.learner.id,
          learn_release_id: releaseId,
        }),
      });
      const instBody = await inst.text();
      let instJson = null;
      try {
        instJson = JSON.parse(instBody);
      } catch {}
      out.instance = {
        status: inst.status,
        id: instJson && instJson.id,
        body: instBody.slice(0, 240),
      };
      if (out.instance.id) {
        // Fetch instance to find an interaction id
        const getInst = await fetch(
          "/api/v1/learn/instances/" + out.instance.id,
          { headers: h }
        );
        const instDetail = await getInst.json();
        const interactionId =
          (instDetail.document &&
            (instDetail.document.nodes || []).find(
              (n) => n.kind === "interaction"
            )?.id) ||
          "learn-node:check-b1:choice:13";
        const attempt = await fetch(
          "/api/v1/learn/instances/" + out.instance.id + "/attempts",
          {
            method: "POST",
            headers: h,
            body: JSON.stringify({
              interaction_id: interactionId,
              response: { selected_option_id: "a" },
              submission_id: "corr-t12-" + Date.now(),
            }),
          }
        );
        out.attempt = {
          status: attempt.status,
          body: (await attempt.text()).slice(0, 300),
          interactionId,
        };
      }
    }

    // Print PDF export (POST)
    const printId = "7d2e4b2b-04bd-49f5-a860-2fe0d70c5ea9";
    const pdf = await fetch(
      "/api/v1/v3/generations/" + printId + "/export/pdf",
      { method: "POST", headers: h, body: "{}" }
    );
    const pdfBuf = await pdf.arrayBuffer();
    out.pdf = {
      status: pdf.status,
      bytes: pdfBuf.byteLength,
      ct: pdf.headers.get("content-type"),
    };

    // Lectio document edit via PUT lectio-document
    const getDoc = await fetch(
      "/api/v1/v3/generations/" + printId + "/lectio-document",
      { headers: h }
    );
    const docText = await getDoc.text();
    let docJson = null;
    try {
      docJson = JSON.parse(docText);
    } catch {}
    out.lectioDoc = {
      status: getDoc.status,
      len: docText.length,
      hasLearnMarker: docText.includes("T12-CORR-MARKER"),
    };
    if (docJson) {
      const blob = JSON.stringify(docJson);
      const edited = blob.includes("T12-PRINT-MARKER")
        ? docJson
        : JSON.parse(
            blob.replace(
              /("text"\s*:\s*")([^"]{12,60})"/,
              '$1$2 [T12-PRINT-MARKER]"'
            )
          );
      const put = await fetch(
        "/api/v1/v3/generations/" + printId + "/lectio-document",
        {
          method: "PUT",
          headers: h,
          body: JSON.stringify(edited),
        }
      );
      const putBody = await put.text();
      out.printEdit = {
        status: put.status,
        body: putBody.slice(0, 200),
        marker: putBody.includes("T12-PRINT-MARKER") || JSON.stringify(edited).includes("T12-PRINT-MARKER"),
      };
      const pdf2 = await fetch(
        "/api/v1/v3/generations/" + printId + "/export/pdf",
        { method: "POST", headers: h, body: "{}" }
      );
      const pdf2Buf = await pdf2.arrayBuffer();
      out.pdfAfterEdit = {
        status: pdf2.status,
        bytes: pdf2Buf.byteLength,
        ct: pdf2.headers.get("content-type"),
      };
    }

    out.userId = me.id;
    out.siblingIndependent = !docText.includes("T12-CORR-MARKER");
    return out;
  });
  console.log(JSON.stringify(result));
  return result;
}
