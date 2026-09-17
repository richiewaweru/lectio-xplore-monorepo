async (page) => {
  const result = await page.evaluate(async () => {
    const token = localStorage.getItem("textbook_agent_token");
    const h = {
      Authorization: "Bearer " + token,
      "Content-Type": "application/json",
    };
    const releaseId = "41a2e657-203f-4e29-b948-a8ca97cef7eb";
    const instanceId = "9faa7898-546a-4eac-8b4c-2cb0070b9e78";
    const release = await (
      await fetch("/api/v1/learn/releases/" + releaseId, { headers: h })
    ).json();
    const nodes = (release.document && release.document.nodes) || [];
    const interaction = nodes.find((n) => n.kind === "interaction");
    const options =
      (interaction && (interaction.options || interaction.choices)) || [];
    const optionId =
      (options[0] && (options[0].id || options[0].option_id)) || null;
    const attempt = await fetch(
      "/api/v1/learn/instances/" + instanceId + "/attempts",
      {
        method: "POST",
        headers: h,
        body: JSON.stringify({
          interaction_id: interaction.id,
          client_submission_id: "corr-t12-ok-" + Date.now(),
          response_json: { selected_option_id: optionId },
        }),
      }
    );
    const body = await attempt.text();
    return {
      interactionId: interaction && interaction.id,
      optionId,
      optionKeys: options[0] && Object.keys(options[0]),
      status: attempt.status,
      body: body.slice(0, 500),
    };
  });
  console.log(JSON.stringify(result));
  return result;
}
