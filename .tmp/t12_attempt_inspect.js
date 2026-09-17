async (page) => {
  const result = await page.evaluate(async () => {
    const token = localStorage.getItem("textbook_agent_token");
    const h = { Authorization: "Bearer " + token };
    const release = await (
      await fetch(
        "/api/v1/learn/releases/41a2e657-203f-4e29-b948-a8ca97cef7eb",
        { headers: h }
      )
    ).json();
    const nodes = (release.document && release.document.nodes) || [];
    const interaction = nodes.find((n) => n.kind === "interaction");
    const keys = interaction ? Object.keys(interaction) : [];
    const payload = interaction
      ? {
          id: interaction.id,
          keys,
          options: interaction.options,
          choices: interaction.choices,
          items: interaction.items,
          config: interaction.config,
          prompt: String(interaction.prompt || "").slice(0, 80),
        }
      : null;
    let optionId = null;
    const pool =
      interaction?.options ||
      interaction?.choices ||
      interaction?.config?.options ||
      interaction?.items ||
      [];
    if (Array.isArray(pool) && pool[0]) {
      optionId =
        pool[0].id ||
        pool[0].option_id ||
        pool[0].value ||
        (typeof pool[0] === "string" ? pool[0] : null);
    }
    const attempt = await fetch(
      "/api/v1/learn/instances/9faa7898-546a-4eac-8b4c-2cb0070b9e78/attempts",
      {
        method: "POST",
        headers: {
          Authorization: "Bearer " + token,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          interaction_id: interaction.id,
          client_submission_id: "corr-t12-final-" + Date.now(),
          response_json: { selected_option_id: optionId },
        }),
      }
    );
    return {
      payload,
      optionId,
      attemptStatus: attempt.status,
      attemptBody: (await attempt.text()).slice(0, 500),
    };
  });
  console.log(JSON.stringify(result));
  return result;
}
