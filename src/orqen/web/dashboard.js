"use strict";
const byId = id => document.getElementById(id);
let token = "", tasks = [], pending = null;
async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {...options.headers, Authorization: `Bearer ${token}`}});
  const data = await response.json();
  if (!response.ok) { const error = new Error(data.error || `Request failed (${response.status})`); error.status = response.status; throw error; }
  return data;
}
function message(text) { byId("message").textContent = text; }
function selected() {
  const task = tasks.find(t => t.name === byId("task").value);
  byId("description").textContent = task?.description || "No tasks available for this account.";
  byId("schema").textContent = JSON.stringify(task?.input_schema || {}, null, 2);
  byId("run").disabled = !task;
}
async function refresh() {
  const rows = await api("/v1/runs");
  byId("total").textContent = rows.length;
  byId("verified").textContent = rows.filter(r => r.trace?.verified).length;
  byId("uncertain").textContent = rows.filter(r => r.requires_reconciliation).length;
  byId("empty").hidden = rows.length > 0;
  byId("history").replaceChildren();
  for (const row of rows) {
    const button = document.createElement("button");
    button.className = `run-row ${row.status}`;
    button.textContent = `${row.task} · ${row.status}`;
    const meta = document.createElement("span");
    meta.textContent = `${new Date(row.created).toLocaleString()} · ${row.trace?.calls ?? "—"} tool calls · ${row.trace?.planner_calls ?? "—"} planning calls`;
    button.append(meta);
    button.onclick = () => { byId("detail-panel").hidden = false; byId("detail").textContent = JSON.stringify(row, null, 2); };
    byId("history").append(button);
  }
}
byId("connect").onsubmit = async event => {
  event.preventDefault(); token = byId("token").value; byId("token").value = "";
  try {
    tasks = await api("/v1/tasks");
    byId("task").replaceChildren();
    for (const task of tasks) { const option = document.createElement("option"); option.value = task.name; option.textContent = task.name; byId("task").append(option); }
    selected(); await refresh(); byId("login").hidden = true; byId("workspace").hidden = false; message("");
  } catch (error) { token = ""; message(error.message); }
};
byId("task").onchange = selected;
byId("refresh").onclick = () => refresh().catch(error => message(error.message));
byId("logout").onclick = () => { token = ""; pending = null; tasks = []; byId("workspace").hidden = true; byId("login").hidden = false; byId("history").replaceChildren(); byId("detail").textContent = ""; message("Disconnected."); };
byId("execute").onsubmit = async event => {
  event.preventDefault(); byId("run").disabled = true;
  try {
    const body = JSON.stringify({task: byId("task").value, inputs: JSON.parse(byId("inputs").value)});
    if (pending && pending.body !== body) throw new Error("The previous request has an uncertain response. Refresh history and disconnect/reconnect before submitting a different request.");
    pending ||= {body, key: crypto.randomUUID()};
    const result = await api("/v1/runs", {method: "POST", body, headers: {"Content-Type": "application/json", "Idempotency-Key": pending.key}});
    if (result.status !== "running" && !result.requires_reconciliation) pending = null;
    message(`Execution ${result.status}.${result.requires_reconciliation ? " Resolve this run before starting another." : ""}`); await refresh();
    byId("detail-panel").hidden = false; byId("detail").textContent = JSON.stringify(result, null, 2);
  } catch (error) {
    if ([400, 404, 413, 415].includes(error.status)) pending = null;
    message(`${error.message}${pending ? " Retry unchanged inputs to reuse the same request key." : ""}`);
  }
  finally { byId("run").disabled = false; }
};
