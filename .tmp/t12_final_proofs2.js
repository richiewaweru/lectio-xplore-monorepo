async (page) => {
  const result = await page.evaluate(async () => {
    const token = localStorage.getItem("textbook_agent_token");
    const h = {
      Authorization: "Bearer " + token,
      "Content-Type": "application/json",
    };
    const out = {};
    const instanceId = "9faa7898-546a-4eac-8b4c-2cb0070b9e78";
    const printId = "7d2e4b2b-04bd-49f5-a860-2fe0d70c5ea9";

    const attempt = await fetch(
      "/api/v1/learn/instances/" + instanceId + "/attempts",
      {
        method: "POST",
        headers: h,
        body: JSON.stringify({
          interaction_id: "learn-node:check-b1:choice:13",
          client_submission_id: "corr-t12-" + Date.now(),
          response_json: { selected_option_id: "a" },
        }),
      }
    );
    out.attempt = {
      status: attempt.status,
      body: (await attempt.text()).slice(0, 400),
    };

    const getDoc = await fetch(
      "/api/v1/v3/generations/" + printId + "/lectio-document",
      { headers: h }
    );
    const wrap = await getDoc.json();
    const rev =
      wrap.document_revision ||
      wrap.revision ||
      (wrap.document && wrap.document.revision) ||
      8;
    const document = wrap.document || wrap.lectio_document || wrap;
    const blob = JSON.stringify(document);
    const editedDoc = blob.includes("T12-PRINT-MARKER")
      ? document
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
        body: JSON.stringify({
          expected_document_revision: rev,
          document: editedDoc,
        }),
      }
    );
    const putBody = await put.text();
    out.printEdit = {
      status: put.status,
      rev,
      body: putBody.slice(0, 240),
      markerInRequest: JSON.stringify(editedDoc).includes("T12-PRINT-MARKER"),
    };

    const pdf = await fetch(
      "/api/v1/v3/generations/" + printId + "/export/pdf",
      {
        method: "POST",
        headers: h,
        body: JSON.stringify({ allow_placeholders: true }),
      }
    );
    const pdfBuf = await pdf.arrayBuffer();
    let pdfErr = null;
    if (pdf.status !== 200) {
      try {
        pdfErr = new TextDecoder().decode(pdfBuf).slice(0, 300);
      } catch {}
    }
    out.pdf = {
      status: pdf.status,
      bytes: pdfBuf.byteLength,
      ct: pdf.headers.get("content-type"),
      err: pdfErr,
    };

    // Confirm Learn marker still only on Learn side
    const learn = await fetch(
      "/api/v1/builder/lessons/c0fc1c46-812f-4a59-abd6-879c11e87d2d",
      { headers: h }
    );
    const learnBody = await learn.text();
    out.learnMarker = learnBody.includes("T12-CORR-MARKER");
    out.printHasLearnMarker = putBody.includes("T12-CORR-MARKER");
    return out;
  });
  console.log(JSON.stringify(result));
  return result;
}
