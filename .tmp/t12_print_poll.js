async (page) => {
  const result = await page.evaluate(async () => {
    const token = localStorage.getItem("textbook_agent_token");
    const h = { Authorization: "Bearer " + token };
    const printId = "7fc2a387-b963-42ed-8fa7-b7a40a71cf0f";
    const polls = [];
    let ready = false;
    for (let i = 0; i < 60; i++) {
      const st = await fetch("/api/v1/v3/chunked/" + printId + "/status", {
        headers: h,
      });
      const body = await st.json();
      polls.push({ n: i, stage: body.stage, status: body.status, error: body.error });
      if (
        ["ready", "completed", "done"].includes(String(body.stage || "")) ||
        body.document_exists === true && Number(body.sections_ready || 0) > 0 &&
          String(body.stage || "") === "ready"
      ) {
        ready = true;
        break;
      }
      if (String(body.stage || "").includes("fail")) break;
      await new Promise((r) => setTimeout(r, 5000));
    }
    const pdf = await fetch("/api/v1/v3/generations/" + printId + "/pdf", {
      headers: h,
    });
    const pdfBuf = await pdf.arrayBuffer();
    const doc = await fetch("/api/v1/v3/generations/" + printId + "/document", {
      headers: h,
    });
    const docText = await doc.text();
    // Edit print document text if editable API exists
    let edit = null;
    try {
      const d = JSON.parse(docText);
      const blob = JSON.stringify(d);
      const edited = blob.includes("T12-PRINT-MARKER")
        ? d
        : JSON.parse(
            blob.replace(
              /("text"\s*:\s*")([^"]{20,80})"/,
              '$1$2 [T12-PRINT-MARKER]"'
            )
          );
      const put = await fetch("/api/v1/v3/generations/" + printId + "/document", {
        method: "PUT",
        headers: { ...h, "Content-Type": "application/json" },
        body: JSON.stringify(edited),
      });
      edit = { status: put.status, body: (await put.text()).slice(0, 200) };
    } catch (e) {
      edit = { error: String(e) };
    }
    return {
      ready,
      polls: polls.slice(-6),
      pdf: {
        status: pdf.status,
        contentType: pdf.headers.get("content-type"),
        bytes: pdfBuf.byteLength,
      },
      document: {
        status: doc.status,
        hasPrintMarker: docText.includes("T12-PRINT-MARKER"),
        hasLearnMarker: docText.includes("T12-CORR-MARKER"),
        len: docText.length,
      },
      edit,
      siblingIndependent: !docText.includes("T12-CORR-MARKER"),
    };
  });
  console.log(JSON.stringify(result));
  return result;
}
