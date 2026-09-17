async (page) => {
  const result = await page.evaluate(async () => {
    const token = localStorage.getItem("textbook_agent_token");
    const h = {
      Authorization: "Bearer " + token,
      "Content-Type": "application/json",
    };
    const releaseId = "41a2e657-203f-4e29-b948-a8ca97cef7eb";
    const lessonId = "c0fc1c46-812f-4a59-abd6-879c11e87d2d";
    const out = { releaseId, lessonId };

    // Learner attempt against published release
    const attemptPaths = [
      "/api/v1/learn/releases/" + releaseId + "/attempts",
      "/api/v1/learn/lessons/" + lessonId + "/attempts",
      "/api/v1/learner/attempts",
    ];
    out.attempts = [];
    for (const p of attemptPaths) {
      const r = await fetch(p, {
        method: "POST",
        headers: h,
        body: JSON.stringify({ release_id: releaseId, lesson_id: lessonId }),
      });
      out.attempts.push({
        p,
        status: r.status,
        body: (await r.text()).slice(0, 280),
      });
    }

    // Print sibling: generate or open existing PDF path
    const uid = "907b1dab-11fd-49fc-ac23-060d45b446b8";
    const lid = "fc9e4f92-7a3e-495e-b4e7-d83052da222e";
    const path = await (await fetch("/api/v1/units/" + uid + "/path", { headers: h })).json();
    const lesson = path.lessons.find((l) => l.id === lid);
    const status = await (
      await fetch("/api/v1/units/" + uid + "/path/lessons/" + lid + "/status", {
        headers: h,
      })
    ).json();
    out.prepStatus = {
      print_output_id: status.print_output_id,
      learn_output_id: status.learn_output_id,
      print_open_href: status.print_open_href,
    };

    // Prefer generating fresh Print from new teaching prep if needed
    const printGen = await fetch(
      "/api/v1/units/" +
        uid +
        "/path/lessons/" +
        lid +
        "/realizations:generate-print",
      {
        method: "POST",
        headers: { ...h, "Idempotency-Key": "corr-t12-print-" + Date.now() },
        body: JSON.stringify({
          path_version_id: path.id,
          path_revision: path.revision,
          lesson_revision: lesson.revision,
        }),
      }
    );
    const printText = await printGen.text();
    let printJson = null;
    try {
      printJson = JSON.parse(printText);
    } catch {}
    out.printGenerate = {
      status: printGen.status,
      body: printJson || printText.slice(0, 400),
    };

    const printId =
      (printJson && (printJson.output_id || printJson.generation_id)) ||
      status.print_output_id;
    out.printId = printId;
    if (printId) {
      const pdf = await fetch("/api/v1/v3/generations/" + printId + "/pdf", {
        headers: h,
      });
      out.pdf = {
        status: pdf.status,
        contentType: pdf.headers.get("content-type"),
        bytes: (await pdf.arrayBuffer()).byteLength,
      };
      // Lightweight text probe via document
      const doc = await fetch("/api/v1/v3/generations/" + printId + "/document", {
        headers: h,
      });
      const docText = await doc.text();
      out.document = {
        status: doc.status,
        hasMarker: docText.includes("T12-CORR-MARKER"),
        snippet: docText.slice(0, 180),
      };
    }

    // Recovery: reconnect-style status reread
    const status2 = await (
      await fetch("/api/v1/units/" + uid + "/path/lessons/" + lid + "/status", {
        headers: h,
      })
    ).json();
    out.reconnect = {
      learn_output_id: status2.learn_output_id,
      print_output_id: status2.print_output_id,
      learn_open_href: status2.learn_open_href,
      print_open_href: status2.print_open_href,
    };
    return out;
  });
  console.log(JSON.stringify(result));
  return result;
}
