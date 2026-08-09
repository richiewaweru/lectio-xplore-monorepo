(() => {
  localStorage.setItem(
    "textbook_agent_token",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzaW1wbGlmaWVkLXBhdGgtYWNjZXB0YW5jZSIsImVtYWlsIjoic2ltcGxpZmllZC1wYXRoQGxlY3Rpby5sb2NhbCIsImV4cCI6MTc4NjY5NTg1M30.GhSli7HbjyRmkZPy0QaEo9-UGGBmYU_KYNVj6Te9tOI"
  );
  localStorage.setItem(
    "textbook_agent_user",
    JSON.stringify({
      id: "simplified-path-acceptance",
      email: "simplified-path@lectio.local",
      name: "Simplified Path Acceptance",
      created_at: "2026-08-01T00:00:00+00:00",
      updated_at: "2026-08-01T00:00:00+00:00",
    })
  );
  return "ok";
})()
