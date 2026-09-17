async (page) => {
  const result = await page.evaluate(async () => {
    const token = localStorage.getItem("textbook_agent_token");
    const h = {
      Authorization: "Bearer " + token,
      "Content-Type": "application/json",
    };
    const out = {};
    const releaseId = "41a2e657-203f-4e29-b948-a8ca97cef7eb";
    const instanceId = "9faa7898-546a-4eac-8b4c-2cb0070b9e78";
    const printId = "7d2e4b2b-04bd-49f5-a860-2fe0d70c5ea9";

    const release = await (
      await fetch("/api/v1/learn/releases/" + releaseId, { headers: h })
    ).json();
    const nodes =
      (release.document && release.document.nodes) ||
      (release.lesson_document && release.lesson_document.nodes) ||
      [];
    const interaction = nodes.find((n) => n.kind === "interaction");
    out.interaction = interaction && {
      id: interaction.id,
      type: interaction.interaction_type || interaction.type,
    };

    if (interaction) {
      const attempt = await fetch(
        "/api/v1/learn/instances/" + instanceId + "/attempts",
        {
          method: "POST",
          headers: h,
          body: JSON.stringify({
            interaction_id: interaction.id,
            client_submission_id: "corr-t12-" + Date.now(),
            response_json: { selected_option_id: "a" },
          }),
        }
      );
      out.attempt = {
        status: attempt.status,
        body: (await attempt.text()).slice(0, 400),
      };
    }

    const pdf = await fetch(
      "/api/v1/v3/generations/" + printId + "/export/pdf",
      {
        method: "POST",
        headers: h,
        body: JSON.stringify({
          school_name: "Correction Pass School",
          teacher_name: "T12 Teacher",
          allow_placeholders: true,
          include_toc: true,
          include_answers: true,
        }),
      }
    );
    const pdfBuf = await pdf.arrayBuffer();
    let pdfErr = null;
    if (pdf.status !== 200) {
      try {
        pdfErr = new TextDecoder().decode(pdfBuf).slice(0, 350);
      } catch {}
    }
    out.pdf = {
      status: pdf.status,
      bytes: pdfBuf.byteLength,
      ct: pdf.headers.get("content-type"),
      err: pdfErr,
      looksLikePdf:
        pdf.status === 200 &&
        pdfBuf.byteLength > 1000 &&
        new Uint8Array(pdfBuf).slice(0, 4).toString() === "37,80,68,70",
    };

    // Verify edited print document still has marker
    const doc = await (
      await fetch("/api/v1/v3/generations/" + printId + "/lectio-document", {
        headers: h,
      })
    ).text();
    out.printMarkerPersisted = doc.includes("T12-PRINT-MARKER");
    out.printIndependentOfLearn = !doc.includes("T12-CORR-MARKER");
    return out;
  });
  console.log(JSON.stringify(result));
  return result;
}
