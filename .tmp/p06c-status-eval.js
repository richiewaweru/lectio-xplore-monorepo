async () => {
  const token = localStorage.getItem('textbook_agent_token');
  const gid = '8a890460-7324-4927-8a90-33aa7da5baa3';
  const headers = { Authorization: 'Bearer ' + token };
  const r = await fetch('/api/v1/v3/generations/' + gid, { headers });
  const j = await r.json().catch(() => ({}));
  const pick = (obj, keys) => Object.fromEntries(keys.filter(k => k in (obj||{})).map(k => [k, obj[k]]));
  return {
    http: r.status,
    pick: pick(j, ['id','status','stage','current_stage','next_action','error_summary','error','failure_reason','work_kind','updated_at','created_at','teaching_review_status','teaching_review_revision','lesson_approach_revision','chunked_stage']),
    top_keys: Object.keys(j).slice(0,40),
    chunked: j.chunked_state_json ? Object.keys(j.chunked_state_json).slice(0,20) : null,
    stage_hint: (j.chunked_state_json && (j.chunked_state_json.stage || j.chunked_state_json.current_stage)) || null
  };
}
