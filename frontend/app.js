/* SupportCommander Dashboard */

const API = "/api/v1";
let workflows = [];
let selected = null;
const API_KEY = window.API_KEY || "";

// ── Utilities ──────────────────────────────────────────────────────────────

async function api(path, opts = {}) {
  if (API_KEY) opts.headers = { ...(opts.headers || {}), "X-API-Key": API_KEY };
  const r = await fetch(API + path, opts);
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(e.detail || `HTTP ${r.status}`);
  }
  return r.json();
}

function toast(msg, duration = 3500) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), duration);
}

function esc(s) {
  if (s == null || s === "") return "—";
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function fmt(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function pct(v) {
  if (v == null) return "—";
  return (v * 100).toFixed(0) + "%";
}

function badge(text, cls) {
  return `<span class="badge ${cls}">${esc(text)}</span>`;
}

function decisionBadge(d) {
  const map = {
    allow: "b-green", reject: "b-red",
    require_approval: "b-amber", escalate: "b-purple",
    approved: "b-green", rejected: "b-red",
    pending: "b-amber", resolved: "b-green",
    failed: "b-red", escalated: "b-purple",
    pending_customer: "b-cyan", pending_approval: "b-amber",
    low: "b-green", medium: "b-amber", high: "b-red", critical: "b-red",
    response_drafting: "b-green", completed: "b-green",
    action_execution: "b-blue", verification: "b-blue",
    approval: "b-amber", policy_gate: "b-gray", planning: "b-gray",
  };
  const key = String(d || "").toLowerCase().replace(/\s/g, "_");
  return badge(d, map[key] || "b-gray");
}

function actionIcon(t) {
  return { refund: "💰", replacement: "📦", cancel_order: "❌", escalate: "🚨", provide_information: "ℹ️" }[t] || "⚙️";
}

// ── Smart Queue: segment workflows ────────────────────────────────────────

const SEGMENT_ORDER = ["action", "running", "done", "failed"];
const SEGMENT_META = {
  action:  { label: "⚡ Needs Action", cls: "seg-action"  },
  running: { label: "🔵 In Progress",  cls: "seg-running" },
  done:    { label: "✅ Done",          cls: "seg-done"    },
  failed:  { label: "❌ Failed",        cls: "seg-failed"  },
};
const _collapsedSegs = new Set();

function _segmentOf(w) {
  const stage = w.current_stage || "";
  const apprStatus = (w.approval || {}).status;
  const respStatus = (w.final_response || {}).resolution_status;
  if (stage === "approval" && apprStatus === "pending") return "action";
  if (stage === "failed" || respStatus === "failed")    return "failed";
  if (respStatus || stage === "completed")               return "done";
  return "running";
}

function _segmentedWorkflows() {
  const groups = { action: [], running: [], done: [], failed: [] };
  for (const w of workflows) groups[_segmentOf(w)].push(w);
  return groups;
}

function _flatOrderedWorkflows() {
  const g = _segmentedWorkflows();
  return SEGMENT_ORDER.flatMap(s => g[s]);
}

// ── Sidebar ────────────────────────────────────────────────────────────────

function renderSidebar() {
  const el = document.getElementById("workflow-list");
  if (!workflows.length) {
    el.innerHTML = `<div class="empty-list"><span class="empty-list-icon">🔄</span>Enter a ticket ID above and click <strong>Run</strong>.<br/>Results appear here.</div>`;
    return;
  }

  const groups = _segmentedWorkflows();
  let html = "";

  for (const seg of SEGMENT_ORDER) {
    const items = groups[seg];
    if (!items.length) continue;
    const { label, cls } = SEGMENT_META[seg];
    const collapsed = _collapsedSegs.has(seg);
    html += `
      <div class="seg-header ${cls}" onclick="toggleSegment('${seg}')">
        <span class="seg-label">${label}</span>
        <span class="seg-count">${items.length}</span>
        <span class="seg-arrow">${collapsed ? "▶" : "▼"}</span>
      </div>`;
    if (!collapsed) {
      html += items.map(w => {
        const status = w.final_response?.resolution_status || w.current_stage || "unknown";
        const active = selected?.workflow_id === w.workflow_id;
        return `
          <div class="wf-item ${active ? "active" : ""}" onclick="pickWorkflow('${w.workflow_id}')">
            <div class="wf-item-id">${esc((w.workflow_id || "").slice(0, 22))}…</div>
            <div class="wf-item-title">Ticket #${w.ticket_id || "?"}</div>
            <div class="wf-item-meta">
              ${decisionBadge(status)}
              ${badge(w.current_stage, "b-gray")}
            </div>
          </div>`;
      }).join("");
    }
  }

  el.innerHTML = html;
}

function toggleSegment(seg) {
  if (_collapsedSegs.has(seg)) _collapsedSegs.delete(seg);
  else _collapsedSegs.add(seg);
  renderSidebar();
}

// ── Stage pipeline ─────────────────────────────────────────────────────────

const STAGES = [
  { key: "triage",           label: "Triage"     },
  { key: "parallel_analysis",label: "Analysis"   },
  { key: "planning",         label: "Planning"   },
  { key: "policy_gate",      label: "Policy Gate"},
  { key: "approval",         label: "Approval"   },
  { key: "action_execution", label: "Execution"  },
  { key: "verification",     label: "Verify"     },
  { key: "response_drafting",label: "Response"   },
  { key: "completed",        label: "Done"       },
];
const STAGE_ORDER = STAGES.map(s => s.key);

function stageClass(key, current, w) {
  const ci = STAGE_ORDER.indexOf(current);
  const ki = STAGE_ORDER.indexOf(key);
  if (w.current_stage === "failed" && ki <= ci) return "failed";
  if (key === current) return w.current_stage === "approval" ? "paused" : "active";
  if (ki < ci) return "done";
  return "";
}

function renderPipeline(w) {
  const current = w.current_stage || "";
  return STAGES.map((s, i) => `
    <div class="stage-step">
      <span class="stage-label ${stageClass(s.key, current, w)}">${s.label}</span>
      ${i < STAGES.length - 1 ? `<div class="stage-arrow"></div>` : ""}
    </div>`).join("");
}

// ── Welcome empty state ────────────────────────────────────────────────────

function renderWelcome() {
  return `
    <div class="welcome-state">
      <div class="welcome-hero">
        <div class="welcome-hero-icon">🤖</div>
        <h1>Autonomous Customer Support</h1>
        <p>SupportCommander resolves support tickets end-to-end using a coordinated multi-agent AI pipeline — from triage to customer response — with human oversight built in.</p>
      </div>

      <div class="welcome-section-title">What this system can do</div>
      <div class="feature-grid">
        <div class="feature-card">
          <div class="feature-icon">🔍</div>
          <h4>Intent &amp; Triage</h4>
          <p>Classifies tickets by intent (refund, replacement, information) and urgency using a fine-tuned AI agent.</p>
        </div>
        <div class="feature-card">
          <div class="feature-icon">⚠️</div>
          <h4>Risk Assessment</h4>
          <p>Scores each ticket by fraud signals, order value, refund history, and customer profile before taking action.</p>
        </div>
        <div class="feature-card">
          <div class="feature-icon">📝</div>
          <h4>Resolution Planning</h4>
          <p>Generates a structured action plan — refund, replacement, escalation — with confidence scores and policy justification.</p>
        </div>
        <div class="feature-card">
          <div class="feature-icon">🛡️</div>
          <h4>Policy Enforcement</h4>
          <p>Runs every planned action through a policy gate that enforces business rules before any money moves.</p>
        </div>
        <div class="feature-card">
          <div class="feature-icon">👤</div>
          <h4>Human-in-the-Loop</h4>
          <p>High-risk actions pause for human approval. Approve or reject directly in this UI to resume the workflow.</p>
        </div>
        <div class="feature-card">
          <div class="feature-icon">💬</div>
          <h4>Customer Response</h4>
          <p>Drafts a personalized, empathetic reply to the customer after resolution, ready to send.</p>
        </div>
      </div>

      <div class="welcome-cta">
        <div style="font-size:28px">👈</div>
        <div class="welcome-cta-text">
          <strong>Get started — enter a Ticket ID in the sidebar</strong>
          <span>Type any number from 1 to 8469 and click <strong>Run</strong> to watch the full pipeline execute in real time.</span>
        </div>
      </div>
    </div>`;
}

// ── Main panel ─────────────────────────────────────────────────────────────

function renderMain() {
  const panel = document.getElementById("main-panel");
  if (!selected) { panel.innerHTML = renderWelcome(); return; }

  const w      = selected;
  const triage = w.triage || {};
  const risk   = w.risk_assessment || {};
  const plan   = w.resolution_plan || {};
  const gate   = w.policy_gate_result || {};
  const appr   = w.approval || {};
  const txns   = w.tool_results || [];
  const resp   = w.final_response || {};
  const events = w.audit_events || [];
  const ticket = w.ticket || {};

  const responseDraftedEvent = [...events].reverse().find(e => e.event_type === "response_drafted");
  const knowledgeSource = responseDraftedEvent?.metadata?.knowledge_source || null;
  const kbDocsCited = responseDraftedEvent?.metadata?.kb_docs_cited || [];

  const isPending  = appr.status === "pending" || w.current_stage === "approval";
  const isRejected = appr.status === "rejected";
  const needsAppr  = !!(appr.status || w.current_stage === "approval");

  // Customer context vars — hoisted so they're available in all sections
  const _ctx      = w.customer_context || {};
  const _cust     = _ctx.customer  || {};
  const _order    = _ctx.order     || {};
  const _pay      = _ctx.payment   || {};
  const _ship     = _ctx.shipment  || {};
  const custName  = _cust.name   || ticket.customer_name  || null;
  const custEmail = _cust.email  || ticket.customer_email || ticket.customer_identifier || null;
  const custPhone = _cust.phone  || ticket.customer_phone || null;
  const custTier  = _cust.customer_tier  || null;
  const custStatus= _cust.account_status || null;
  const custRisk  = _cust.risk_level     || null;
  const custAge   = _cust.age    || ticket.customer_age   || null;
  const custGender= _cust.gender || ticket.customer_gender|| null;

  const triggerLabels = { frustration: "😤 Frustration", security_concern: "🔒 Security Concern", personal_data_change: "🪪 Personal Data Change", high_value_transaction: "💵 High-Value Transaction" };

  // ── Header bar ──
  let html = `
    <div class="wf-hero">
      <div class="wf-hero-info">
        <h2>Ticket #${w.ticket_id || "?"}</h2>
        <div class="wf-hero-meta">
          <span class="wf-id-chip" onclick="copyId('${w.workflow_id}')" title="Click to copy ID">${esc((w.workflow_id || "").slice(0, 30))}…</span>
          ${decisionBadge(w.current_stage)}
          ${resp.resolution_status ? decisionBadge(resp.resolution_status) : ""}
          <span style="font-size:11px;color:var(--text-xs)">Updated ${fmt(w.updated_at)}</span>
        </div>
        ${w.error ? `<div class="error-bar" style="margin-top:8px">⚠️ ${esc(w.error)}</div>` : ""}
      </div>
      <div class="wf-hero-actions">
        <button class="btn btn-ghost btn-sm" onclick="refreshWorkflow()">↻ Refresh</button>
      </div>
    </div>
    <div class="pipeline">${renderPipeline(w)}</div>
    <div class="thread">`;

  // ══ STEP 1 — Customer Message ══════════════════════════════════════════════
  if (ticket.ticket_text || ticket.ticket_subject) {
    const order = _order;
    const pay   = _pay;
    const ship  = _ship;

    const tierColor = { premium:"b-purple", gold:"b-amber", standard:"b-gray", basic:"b-gray" }[custTier] || "b-gray";
    const riskColor = { high:"b-red", medium:"b-amber", low:"b-green" }[custRisk] || "b-gray";

    const hasProfile = custName || custEmail || custTier || order.product;

    html += `
      <div class="thread-row">
        <div class="thread-avatar thread-av-customer">👤</div>
        <div class="thread-content">
          <div class="thread-label">
            Customer Message
            ${ticket.ticket_type     ? badge(ticket.ticket_type,    "b-gray") : ""}
            ${ticket.ticket_channel  ? badge(ticket.ticket_channel, "b-gray") : ""}
            ${ticket.ticket_priority ? decisionBadge(ticket.ticket_priority)  : ""}
            ${ticket.ticket_date     ? `<span style="font-size:11px;color:var(--text-xs)">${esc(ticket.ticket_date)}</span>` : ""}
          </div>
          <div class="thread-card">
            ${hasProfile ? `
            <div class="cust-profile">
              <div class="cust-profile-top">
                <div class="cust-avatar-sm">${(custName||custEmail||"?")[0].toUpperCase()}</div>
                <div class="cust-profile-info">
                  ${custName  ? `<div class="cust-name">${esc(custName)}</div>` : ""}
                  ${custEmail ? `<div class="cust-email">✉ ${esc(custEmail)}</div>` : ""}
                  ${custPhone ? `<div class="cust-email">📞 ${esc(custPhone)}</div>` : ""}
                </div>
                <div class="cust-profile-badges">
                  ${custTier   ? badge(custTier,   tierColor) : ""}
                  ${custStatus ? badge(custStatus, custStatus==="active"?"b-green":"b-red") : ""}
                  ${custRisk   ? badge("risk: "+custRisk, riskColor) : ""}
                  ${custAge    ? `<span class="cust-detail-chip">${custAge}${custGender ? " · "+esc(custGender) : ""}</span>` : ""}
                </div>
              </div>
              ${(order.product || order.order_id || pay.payment_method || ship.shipment_status) ? `
              <div class="cust-profile-grid">
                ${order.product ? `<div class="cust-detail-block"><div class="cust-detail-label">Product</div><div class="cust-detail-val">${esc(order.product)}</div></div>` : ""}
                ${order.order_amount!=null ? `<div class="cust-detail-block"><div class="cust-detail-label">Order Value</div><div class="cust-detail-val">$${order.order_amount.toFixed(2)} ${esc(order.currency||"")}</div></div>` : ""}
                ${order.order_status ? `<div class="cust-detail-block"><div class="cust-detail-label">Order Status</div><div class="cust-detail-val">${badge(order.order_status, order.order_status==="delivered"?"b-green":"b-amber")}</div></div>` : ""}
                ${pay.payment_method ? `<div class="cust-detail-block"><div class="cust-detail-label">Payment</div><div class="cust-detail-val">${esc(pay.payment_method)} · ${badge(pay.payment_status||"", pay.payment_status==="paid"?"b-green":"b-amber")}</div></div>` : ""}
                ${ship.shipment_status ? `<div class="cust-detail-block"><div class="cust-detail-label">Shipment</div><div class="cust-detail-val">${badge(ship.shipment_status, ship.shipment_status==="delivered"?"b-green":"b-amber")} via ${esc(ship.carrier||"")} · ${esc(ship.tracking_number||"")}</div></div>` : ""}
                ${order.purchase_date ? `<div class="cust-detail-block"><div class="cust-detail-label">Purchase Date</div><div class="cust-detail-val">${esc(order.purchase_date)}</div></div>` : ""}
              </div>` : ""}
            </div>` : ""}
            ${ticket.ticket_subject ? `<div class="thread-subject">${esc(ticket.ticket_subject)}</div>` : ""}
            ${ticket.ticket_text    ? `<div class="thread-body">${esc(ticket.ticket_text)}</div>` : ""}
            <div class="thread-meta-row">
              ${ticket.customer_id ? `<span>👤 ${esc(ticket.customer_id)}</span><span class="thread-meta-sep">·</span>` : ""}
              ${ticket.order_id    ? `<span>🛒 ${esc(ticket.order_id)}</span><span class="thread-meta-sep">·</span>` : ""}
              ${ticket.ticket_channel ? `<span>${esc(ticket.ticket_channel)}</span>` : ""}
            </div>
          </div>
        </div>
      </div>`;
  }

  // ══ STEP 2 — Agent Analysis (triage + risk) ════════════════════════════════
  if (triage.intent || risk.risk_level) {
    const triggers = triage.human_triggers || [];
    const signals  = risk.risk_signals || [];
    const riskColor = { high: "var(--red)", critical: "var(--red)", medium: "var(--amber)", low: "var(--green)" }[risk.risk_level] || "var(--text-muted)";

    html += `
      <div class="thread-row">
        <div class="thread-avatar thread-av-agent">🤖</div>
        <div class="thread-content">
          <div class="thread-label">Agent Analysis</div>
          <div class="thread-card">
            ${triage.intent ? `
              <div class="analysis-row">
                <div class="analysis-section-label">Triage</div>
                <div class="analysis-badges">
                  ${decisionBadge(triage.intent)} ${decisionBadge(triage.urgency)}
                  <span class="analysis-conf">Confidence ${pct(triage.confidence)}</span>
                </div>
                ${triage.summary ? `<div class="analysis-summary">${esc(triage.summary)}</div>` : ""}
                ${triggers.length ? `<div class="trigger-list" style="margin-top:6px">${triggers.map(t => `<span class="trigger-chip">${triggerLabels[t] || esc(t)}</span>`).join("")}</div>` : ""}
                ${w.escalated ? `<div class="error-bar" style="margin-top:8px">🚨 Escalated: ${esc(w.escalation_reason)}</div>` : ""}
              </div>` : ""}
            ${risk.risk_level ? `
              <div class="analysis-row" style="${triage.intent ? "border-top:1px solid var(--border-light);" : ""}">
                <div class="analysis-section-label">Risk</div>
                <div class="analysis-badges">
                  ${decisionBadge(risk.risk_level)}
                  <span class="analysis-conf" style="color:${riskColor}">Score ${risk.risk_score != null ? risk.risk_score.toFixed(2) : "—"}</span>
                </div>
                ${signals.length ? `<div class="signal-list" style="margin-top:6px">${signals.map(s => `<div class="signal-item">${esc(s)}</div>`).join("")}</div>` : ""}
              </div>` : ""}
          </div>
        </div>
      </div>`;
  }

  // ══ STEP 3 — Agent Suggestion (plan + policy gate) ═════════════════════════
  if (plan.summary || gate.decision) {
    const actions  = plan.actions || [];
    const decisions = gate.action_decisions || [];

    html += `
      <div class="thread-row">
        <div class="thread-avatar thread-av-suggest">📝</div>
        <div class="thread-content">
          <div class="thread-label">
            Agent Suggestion
            ${plan.confidence != null ? `<span class="analysis-conf">Confidence ${pct(plan.confidence)}</span>` : ""}
          </div>
          <div class="thread-card">
            ${plan.summary ? `<div class="thread-body" style="font-size:13px">${esc(plan.summary)}</div>` : ""}
            ${actions.length ? `
              <div class="action-list" style="padding:12px 14px;background:var(--surface-2);border-top:1px solid var(--border-light)">
                ${actions.map(a => `
                  <div class="action-item">
                    <div class="action-icon">${actionIcon(a.action_type)}</div>
                    <div class="action-body">
                      <div class="action-type">${esc(a.action_type)}</div>
                      <div class="action-reason">${esc(a.reason)}</div>
                      <div class="action-meta">
                        ${a.order_id ? badge("Order: " + a.order_id, "b-gray") : ""}
                        ${a.amount != null ? badge("$" + a.amount.toFixed(2), "b-blue") : ""}
                      </div>
                    </div>
                  </div>`).join("")}
              </div>` : ""}
            ${(plan.policy_basis || []).length ? `
              <div style="padding:8px 14px;border-top:1px solid var(--border-light);font-size:11px;color:var(--text-xs)">
                Policy basis: ${plan.policy_basis.map(p => `<code style="background:var(--surface-3);padding:1px 4px;border-radius:3px">${esc(p)}</code>`).join(", ")}
              </div>` : ""}
            ${gate.decision ? `
              <div class="gate-strip gate-${gate.decision}">
                <span>🛡️ Policy Gate:</span>
                ${decisionBadge(gate.decision)}
                ${gate.requires_human_approval ? badge("⚑ Approval Required", "b-amber") : ""}
                ${(gate.reasons || []).map(r => `<span class="gate-reason">${esc(r)}</span>`).join("")}
              </div>
              ${decisions.length ? `
                <div class="decision-list" style="padding:10px 14px;border-top:1px solid var(--border-light)">
                  ${decisions.map(d => `
                    <div class="decision-item ${d.decision}">
                      <span>${actionIcon(d.action_type)}</span>
                      <div class="decision-item-text"><strong>${esc(d.action_type)}</strong> — ${esc(d.reason)}</div>
                      ${decisionBadge(d.decision)}
                    </div>`).join("")}
                </div>` : ""}` : ""}
          </div>
        </div>
      </div>`;
  }

  // ══ STEP 4 — Human in the Loop ════════════════════════════════════════════
  if (needsAppr) {
    // Customer info chips for the review card
    const reviewCustLine = [custName, custEmail, custPhone].filter(Boolean).map(esc).join("  ·  ");

    html += `
      <div class="thread-row">
        <div class="thread-avatar thread-av-human ${isPending ? "thread-av-pulse" : ""}">⚑</div>
        <div class="thread-content">
          <div class="thread-label">
            Human Review
            ${appr.status ? decisionBadge(appr.status) : badge("⏳ Awaiting Decision", "b-amber")}
            ${appr.decided_by && appr.decided_by !== "—" ? `<span style="font-size:11px;color:var(--text-muted);font-weight:400">by ${esc(appr.decided_by)}</span>` : ""}
          </div>
          <div class="thread-card">
            ${reviewCustLine ? `
              <div style="padding:10px 14px 8px;border-bottom:1px solid var(--border-light);display:flex;align-items:center;gap:10px">
                <div class="cust-avatar-sm" style="flex-shrink:0;width:30px;height:30px;font-size:12px">${(custName||custEmail||"?")[0].toUpperCase()}</div>
                <div>
                  ${custName  ? `<div style="font-weight:600;font-size:13px;color:var(--text-primary)">${esc(custName)}</div>` : ""}
                  <div style="font-size:11px;color:var(--text-xs);margin-top:1px">${[custEmail,custPhone].filter(Boolean).map(esc).join("  ·  ")}</div>
                </div>
              </div>` : ""}
            ${appr.agent_recommendation ? `
              <div class="agent-rec-block">
                <div class="agent-rec-label">🤖 Agent Briefing — Internal</div>
                <pre class="agent-rec-pre" style="font-size:11.5px;line-height:1.55">${esc(appr.agent_recommendation)}</pre>
              </div>` : appr.requested_reason ? `
              <div class="thread-body"><strong>Why review was needed:</strong> ${esc(appr.requested_reason)}</div>` : ""}
            ${appr.decision_reason && !isPending ? `
              <div class="thread-body" style="border-top:1px solid var(--border-light);padding-top:10px">
                <strong>${isRejected ? "✗ Rejection reason" : "✓ Decision note"}:</strong> ${esc(appr.decision_reason)}
              </div>` : ""}
            ${appr.commitments && appr.commitments.length ? `
              <div style="padding:10px 14px;border-top:1px solid var(--border-light)">
                <div class="analysis-section-label" style="margin-bottom:5px">Authorized commitments</div>
                ${appr.commitments.map(c => `<div style="font-size:12px;color:var(--text);padding:2px 0">✓ ${esc(c)}</div>`).join("")}
              </div>` : ""}
            ${isRejected ? `
              <div style="margin:10px 14px 14px;padding:10px 12px;background:var(--surface-red,rgba(239,68,68,.06));border-radius:var(--radius-sm);border-left:3px solid var(--red)">
                <div style="font-size:11px;font-weight:600;color:var(--red);margin-bottom:5px">🚨 What happens next</div>
                <div style="font-size:12px;color:var(--text-muted)">Customer will be notified — no automated action was taken.</div>
              </div>` : ""}
            ${isPending ? `<div style="padding:0 14px 14px">${renderApprovalForm(w.workflow_id, custName, custEmail)}</div>` : ""}
          </div>
        </div>
      </div>`;
  }

  // ══ STEP 5 — Final Plan / Executed Actions ═════════════════════════════════
  if (txns.length) {
    const allOk = txns.every(t => t.success && t.verification_passed);
    html += `
      <div class="thread-row">
        <div class="thread-avatar thread-av-exec">⚙️</div>
        <div class="thread-content">
          <div class="thread-label">
            Actions Taken
            ${badge(txns.length + " action" + (txns.length !== 1 ? "s" : ""), "b-gray")}
            ${allOk ? badge("✓ all verified", "b-green") : badge("⚠ check results", "b-amber")}
          </div>
          <div class="thread-card">
            <div class="txn-list" style="padding:10px 14px">
              ${txns.map(t => `
                <div class="txn-item">
                  <div class="txn-head">
                    <span class="action-icon">${actionIcon(t.action_type)}</span>
                    <span class="action-name">${esc(t.action_type)}</span>
                    ${badge(t.success ? "✓ success" : "✗ failed", t.success ? "b-green" : "b-red")}
                    ${t.verification_passed ? badge("verified ✓", "b-green") : badge("unverified", "b-gray")}
                  </div>
                  ${t.error ? `<div class="txn-body"><div class="error-bar" style="margin-top:0">${esc(t.error)}</div></div>` : ""}
                  ${t.data  ? `<div class="txn-body"><pre>${esc(JSON.stringify(t.data, null, 2))}</pre></div>` : ""}
                </div>`).join("")}
            </div>
          </div>
        </div>
      </div>`;
  }

  // ══ STEP 6 — Response to Customer ══════════════════════════════════════════
  if (resp.message) {
    const sourceLabel = { policy_db: "📋 Policy DB", company_doc: "📄 Company Docs", general: "🧠 General Knowledge" }[knowledgeSource];
    const sourceCls   = { policy_db: "b-blue", company_doc: "b-cyan", general: "b-gray" }[knowledgeSource];

    html += `
      <div class="thread-row ${resp.agent_handoff ? "" : "thread-row-last"}">
        <div class="thread-avatar thread-av-response">💬</div>
        <div class="thread-content">
          <div class="thread-label">
            Response to Customer
            ${decisionBadge(resp.resolution_status)}
            ${resp.requires_follow_up ? badge("⚑ Follow-up Required", "b-amber") : ""}
            ${sourceLabel ? badge(sourceLabel, sourceCls) : ""}
          </div>
          <div class="thread-card thread-card-response">
            ${knowledgeSource === "company_doc" && kbDocsCited.length ? `<div class="source-citation" style="margin:12px 14px 0;border-radius:var(--radius-sm)">📄 Based on: ${kbDocsCited.map(d => `<em>${esc(d)}</em>`).join(", ")}</div>` : ""}
            ${knowledgeSource === "general" ? `<div class="source-disclaimer" style="margin:12px 14px 0;border-radius:var(--radius-sm)">ℹ️ Based on general knowledge — no specific company policy matched.</div>` : ""}
            <div class="response-box" style="margin:12px 14px;border-radius:var(--radius-sm)">${esc(resp.message)}</div>
            ${resp.action_summary ? `<div style="padding:10px 14px;border-top:1px solid var(--border-light);font-size:12px;color:var(--text-muted)"><strong>Summary:</strong> ${esc(resp.action_summary)}</div>` : ""}
            ${resp.internal_notes ? `<div style="padding:8px 14px 12px;font-size:11px;color:var(--text-xs)"><strong>Internal:</strong> ${esc(resp.internal_notes)}</div>` : ""}
          </div>
        </div>
      </div>`;

    if (resp.agent_handoff) {
      const followUpNeeded = resp.requires_follow_up || resp.resolution_status === "escalated" || resp.resolution_status === "pending_approval";

      // Build customer info chips — only show fields that actually have a value
      const handoffCustChips = [
        custName   ? `<span class="cust-detail-chip">👤 ${esc(custName)}</span>`   : "",
        custEmail  ? `<span class="cust-detail-chip">✉ ${esc(custEmail)}</span>`   : "",
        custPhone  ? `<span class="cust-detail-chip">📞 ${esc(custPhone)}</span>`  : "",
        custTier   ? `<span class="cust-detail-chip">⭐ ${esc(custTier)}</span>`   : "",
        custStatus ? `<span class="cust-detail-chip">◉ ${esc(custStatus)}</span>`  : "",
        custAge    ? `<span class="cust-detail-chip">🎂 Age ${esc(String(custAge))}</span>` : "",
        custGender ? `<span class="cust-detail-chip">⚧ ${esc(custGender)}</span>`  : "",
      ].filter(Boolean).join("");

      html += `
      <div class="thread-row thread-row-last">
        <div class="thread-avatar thread-av-agent">🤖</div>
        <div class="thread-content">
          <div class="thread-label">
            Agent Handoff Note
            ${followUpNeeded ? badge("⚑ Action Required", "b-amber") : badge("✓ No Action Needed", "b-green")}
          </div>
          <div class="thread-card">
            <div class="agent-rec-block" style="border-bottom:none">
              <div class="agent-rec-label">Internal · Not shown to customer</div>
              ${handoffCustChips ? `<div class="cust-profile-badges" style="margin:6px 0 10px">${handoffCustChips}</div>` : ""}
              <pre class="agent-rec-pre">${esc(resp.agent_handoff)}</pre>
            </div>
          </div>
        </div>
      </div>`;
    }
  }

  html += `</div><div class="cards" style="padding-top:0">`;

  // ══ Audit Trail (collapsible) ═══════════════════════════════════════════════
  if (events.length) {
    html += `
      <div class="card" id="audit-card">
        <div class="card-head collapsible-head" onclick="toggleSection('audit-body','audit-arrow')">
          <h3>📜 Audit Trail</h3>
          <span class="badge b-gray" style="margin-left:auto">${events.length} event${events.length !== 1 ? "s" : ""}</span>
          <span class="collapse-arrow" id="audit-arrow">▼</span>
        </div>
        <div class="card-body" id="audit-body" style="display:none">
          <div class="audit-list">
            ${[...events].reverse().map(e => `
              <div class="audit-item">
                <div class="audit-dot"></div>
                <div class="audit-content">
                  <div class="audit-type">${esc(e.event_type)}</div>
                  <div class="audit-msg">${esc(e.message)}</div>
                  <div class="audit-meta">${esc(e.actor)} · ${fmt(e.timestamp)}</div>
                </div>
              </div>`).join("")}
          </div>
        </div>
      </div>`;
  }

  // ══ Cost & Tokens (collapsible) ════════════════════════════════════════════
  html += `
    <div class="card" id="cost-card">
      <div class="card-head collapsible-head" onclick="toggleSection('cost-body','cost-arrow')">
        <h3>💰 Cost &amp; Tokens</h3>
        <span class="collapse-arrow" id="cost-arrow">▶</span>
      </div>
      <div class="card-body" id="cost-body" style="display:none">
        <div id="cost-content"><span style="font-size:12px;color:var(--text-xs)">Loading…</span></div>
      </div>
    </div>`;

  html += "</div>";
  panel.innerHTML = html;
  loadCostLog(w.workflow_id);
}

function renderApprovalForm(workflowId, custName, custEmail) {
  const savedName = (() => { try { return localStorage.getItem("sc_approver_name") || ""; } catch { return ""; } })();
  const custLabel = custName ? esc(custName) + (custEmail ? ` (${esc(custEmail)})` : "") : custEmail ? esc(custEmail) : "";
  return `
    <div class="appr-card" id="approval-form">
      <div class="appr-header">
        <div>
          <div class="appr-label">⚡ Decision Required</div>
          ${custLabel ? `<div style="font-size:11px;color:var(--text-xs);margin-top:2px">For: ${custLabel}</div>` : ""}
        </div>
        <input type="text" id="approver-name" class="appr-name-input" placeholder="Your name…" value="${esc(savedName)}" oninput="try{localStorage.setItem('sc_approver_name',this.value)}catch{}" />
      </div>

      <div class="appr-mode-btns">
        <button class="appr-mode-btn appr-mode-approve active" id="amode-approved" onclick="switchApprMode('approved')">
          ✓ Approve
        </button>
        <button class="appr-mode-btn appr-mode-modify" id="amode-modified" onclick="switchApprMode('modified')">
          ✎ Modify
        </button>
        <button class="appr-mode-btn appr-mode-reject" id="amode-rejected" onclick="switchApprMode('rejected')">
          ✗ Reject
        </button>
      </div>

      <!-- Approve panel -->
      <div class="appr-mode-panel" id="amode-panel-approved">
        <textarea id="approval-commitments" rows="2" placeholder="What you're authorizing (optional)… e.g. Full refund of $89.99 approved for ${custName || 'customer'}"></textarea>
        <textarea id="approval-reason-approved" rows="1" placeholder="Internal notes (optional)…"></textarea>
        <button class="btn btn-success appr-submit-btn" onclick="submitStructuredApproval('${workflowId}','approved')">✓ Confirm Approval</button>
      </div>

      <!-- Modify panel -->
      <div class="appr-mode-panel hidden" id="amode-panel-modified">
        <textarea id="approval-reason-modified" rows="2" placeholder="Describe modification… e.g. Approve partial refund of $45 instead of full amount for ${custName || 'customer'}"></textarea>
        <textarea id="approval-modified-actions" rows="2" placeholder='Action overrides JSON (optional): [{"action_index":0,"amount":45.00}]' style="font-family:ui-monospace,monospace;font-size:11px"></textarea>
        <button class="btn btn-primary appr-submit-btn" onclick="submitStructuredApproval('${workflowId}','modified')">✎ Approve with Modifications</button>
      </div>

      <!-- Reject panel -->
      <div class="appr-mode-panel hidden" id="amode-panel-rejected">
        <textarea id="approval-reason-rejected" rows="2" placeholder="Reason for rejection…"></textarea>
        <textarea id="approval-next-step" rows="2" placeholder="Next step for ${custName || 'customer'} (optional)… e.g. A senior specialist will follow up within 48 hours."></textarea>
        <button class="btn btn-danger appr-submit-btn" onclick="submitStructuredApproval('${workflowId}','rejected')">✗ Reject Request</button>
      </div>
    </div>`;
}

function switchApprMode(mode) {
  ["approved", "modified", "rejected"].forEach(m => {
    document.getElementById(`amode-${m}`)?.classList.toggle("active", m === mode);
    document.getElementById(`amode-panel-${m}`)?.classList.toggle("hidden", m !== mode);
  });
}

function switchApprTab(tab) { switchApprMode(tab); }

// ── Collapsible sections ───────────────────────────────────────────────────

function toggleSection(bodyId, arrowId) {
  const body = document.getElementById(bodyId);
  const arrow = document.getElementById(arrowId);
  if (!body) return;
  const collapsed = body.style.display === "none";
  body.style.display = collapsed ? "" : "none";
  if (arrow) arrow.textContent = collapsed ? "▼" : "▶";
}

// ── Cost log loader ────────────────────────────────────────────────────────

async function loadCostLog(workflowId) {
  const el = document.getElementById("cost-content");
  if (!el) return;
  try {
    const log = await api(`/cost-logs/by-workflow/${workflowId}`);
    const s = log.summary || {};
    const calls = log.llm_calls || [];
    el.innerHTML = `
      <div class="cost-summary">
        <div class="cost-stat"><span class="cost-label">Total Cost</span><span class="cost-val cost-val-primary">$${(s.total_cost_usd || 0).toFixed(6)}</span></div>
        <div class="cost-stat"><span class="cost-label">Total Tokens</span><span class="cost-val">${(s.total_tokens || 0).toLocaleString()}</span></div>
        <div class="cost-stat"><span class="cost-label">Input Tokens</span><span class="cost-val">${(s.total_input_tokens || 0).toLocaleString()}</span></div>
        <div class="cost-stat"><span class="cost-label">Output Tokens</span><span class="cost-val">${(s.total_output_tokens || 0).toLocaleString()}</span></div>
        <div class="cost-stat"><span class="cost-label">Wall Time</span><span class="cost-val">${(log.total_wall_ms || 0).toFixed(0)} ms</span></div>
        <div class="cost-stat"><span class="cost-label">LLM Latency</span><span class="cost-val">${(log.total_llm_latency_ms || 0).toFixed(0)} ms</span></div>
        <div class="cost-stat"><span class="cost-label">Overhead</span><span class="cost-val">${(log.overhead_ms || 0).toFixed(0)} ms</span></div>
        <div class="cost-stat"><span class="cost-label">LLM Calls</span><span class="cost-val">${log.llm_calls_count || 0}</span></div>
        <div class="cost-stat"><span class="cost-label">Model(s)</span><span class="cost-val">${(log.models_used || []).join(", ") || "—"}</span></div>
      </div>
      ${calls.length ? `
        <div class="section-label" style="margin-top:14px">Per-Agent Breakdown</div>
        <table class="cost-table">
          <thead><tr><th>Agent</th><th>Model</th><th>In Tokens</th><th>Out Tokens</th><th>Latency</th><th>Cost</th></tr></thead>
          <tbody>
            ${calls.map(c => `
              <tr>
                <td><strong>${esc(c.agent)}</strong></td>
                <td><span class="badge b-gray">${esc(c.model)}</span></td>
                <td>${c.input_tokens.toLocaleString()}</td>
                <td>${c.output_tokens.toLocaleString()}</td>
                <td>${c.latency_ms.toFixed(0)} ms</td>
                <td>$${c.call_cost_usd.toFixed(6)}</td>
              </tr>`).join("")}
          </tbody>
        </table>` : ""}`;
  } catch {
    el.innerHTML = `<span style="font-size:12px;color:var(--text-xs)">No cost log available for this workflow.</span>`;
  }
}

// ── Actions ────────────────────────────────────────────────────────────────

function copyId(id) {
  navigator.clipboard.writeText(id).then(() => toast("Workflow ID copied!"));
}

async function pickWorkflow(id) {
  try {
    const doc = await api(`/workflows/${id}`);
    const idx = workflows.findIndex(w => w.workflow_id === id);
    if (idx >= 0) workflows[idx] = doc; else workflows.unshift(doc);
    selected = doc;
  } catch {
    selected = workflows.find(w => w.workflow_id === id) || null;
  }
  renderSidebar();
  renderMain();
}

async function refreshWorkflow() {
  if (!selected) return;
  await pickWorkflow(selected.workflow_id);
  toast("↻ Refreshed");
}

async function loadWFDatasets() {
  const userId = document.getElementById("wf-user-id-input").value.trim();
  if (!userId) { toast("Enter a user ID first"); return; }
  try {
    const list = await api(`/datasets?user_id=${encodeURIComponent(userId)}`);
    const ready = list.filter(d => d.status === "ready");
    const sel = document.getElementById("wf-dataset-select");
    sel.innerHTML = `<option value="">— All tickets (default DB) —</option>`;
    ready.forEach(d => {
      const opt = document.createElement("option");
      opt.value = d.dataset_id;
      opt.textContent = `${d.original_filename || d.dataset_id} (${d.ingested_count ?? "?"} rows)`;
      opt.dataset.count = d.ingested_count ?? 0;
      sel.appendChild(opt);
    });
    sel.style.display = "block";
    if (ready.length === 0) toast("No ready datasets found for this user");
    else toast(`${ready.length} dataset${ready.length !== 1 ? "s" : ""} loaded`);
    onWFDatasetChange();
  } catch (e) {
    toast("Error: " + e.message);
  }
}

function onWFDatasetChange() {
  const sel = document.getElementById("wf-dataset-select");
  const hint = document.getElementById("ticket-hint");
  const input = document.getElementById("ticket-input");
  const opt = sel.options[sel.selectedIndex];
  if (sel.value) {
    const count = parseInt(opt.dataset.count || "0", 10);
    hint.textContent = count > 0 ? `Row IDs 0–${count - 1} are available` : "Enter a row ID";
    input.placeholder = "Row ID (e.g. 0)";
    input.min = "0";
  } else {
    hint.textContent = "Ticket IDs 1–8469 are available";
    input.placeholder = "Ticket ID (e.g. 42)";
    input.min = "1";
  }
}

async function runWorkflow(ticketId) {
  const btn = document.getElementById("run-btn");
  const datasetId = document.getElementById("wf-dataset-select")?.value || "";
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Running…`;
  try {
    let result;
    if (datasetId) {
      result = await api(`/workflows/datasets/${encodeURIComponent(datasetId)}/tickets/${ticketId}`, { method: "POST" });
      toast(`✓ Workflow started — Dataset row #${ticketId}`);
    } else {
      result = await api(`/workflows/tickets/${ticketId}`, { method: "POST" });
      toast(`✓ Workflow started — Ticket #${ticketId}`);
    }
    workflows.unshift(result);
    selected = result;
    renderSidebar();
    renderMain();
  } catch (e) {
    toast("Error: " + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Run";
  }
}

async function searchWorkflow(id) {
  if (!id) return;
  try {
    const doc = await api(`/workflows/${id.trim()}`);
    const exists = workflows.find(w => w.workflow_id === doc.workflow_id);
    if (!exists) workflows.unshift(doc);
    selected = doc;
    renderSidebar();
    renderMain();
  } catch (e) {
    toast("Not found: " + e.message);
  }
}

async function submitStructuredApproval(workflowId, decision) {
  const name = (document.getElementById("approver-name")?.value || "").trim() || "reviewer";

  let reason = "", commitments = [], next_step = null, modified_actions = [];

  if (decision === "approved") {
    reason = (document.getElementById("approval-reason-approved")?.value || "").trim() || "Approved.";
    const c = (document.getElementById("approval-commitments")?.value || "").trim();
    if (c) commitments = c.split("\n").map(s => s.trim()).filter(Boolean);
  } else if (decision === "modified") {
    reason = (document.getElementById("approval-reason-modified")?.value || "").trim() || "Approved with modifications.";
    try {
      const raw = (document.getElementById("approval-modified-actions")?.value || "").trim();
      if (raw) modified_actions = JSON.parse(raw);
    } catch { toast("Invalid JSON in action overrides — ignored."); }
  } else {
    reason = (document.getElementById("approval-reason-rejected")?.value || "").trim() || "Rejected.";
    next_step = (document.getElementById("approval-next-step")?.value || "").trim() || null;
  }

  // Replace main panel with a full-panel loading state immediately
  const main = document.getElementById("main-panel");
  if (main) {
    main.innerHTML = `
      <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:16px;padding:40px">
        <span class="spinner" style="width:32px;height:32px;border-width:3px;border-color:rgba(0,0,0,.1);border-top-color:var(--amber)"></span>
        <div style="font-size:15px;font-weight:600;color:var(--text-primary)">Processing decision…</div>
        <div style="font-size:12px;color:var(--text-xs)">Running actions &amp; drafting response — this takes 30–60 seconds</div>
      </div>`;
  }

  try {
    await api(`/approvals/${workflowId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, decided_by: name, reason, commitments, next_step, modified_actions }),
    });
  } catch (e) {
    toast("Error recording decision: " + e.message);
    await pickWorkflow(workflowId);
    return;
  }

  try {
    // Await resume — it returns the full completed state directly
    const result = await api(`/approvals/${workflowId}/resume`, { method: "POST" });
    const idx = workflows.findIndex(w => w.workflow_id === workflowId);
    if (idx >= 0) workflows[idx] = result; else workflows.unshift(result);
    selected = result;
    renderSidebar();
    renderMain();
    const stage = result.current_stage || "";
    const labels = { completed: "✓ Workflow complete", escalated: "⚑ Escalated", failed: "✗ Workflow failed" };
    toast(labels[stage] || "✓ Done");
  } catch (e) {
    toast("Resume error: " + e.message);
    // Try fetching the saved state as fallback
    await pickWorkflow(workflowId);
  }
}

// Legacy shim kept for any stale references
async function submitApproval(workflowId, approved) {
  await submitStructuredApproval(workflowId, approved ? "approved" : "rejected");
}

// ════════════════════════════════════════════════════════════════════════════
// KNOWLEDGE BASE (Phase 6)
// ════════════════════════════════════════════════════════════════════════════

let kbDocs = [];

function onKBFileSelected() {
  const input = document.getElementById("kb-file-input");
  const chip = document.getElementById("kb-file-chip");
  if (!input.files.length) { chip.classList.add("hidden"); return; }
  chip.textContent = `${input.files.length} file${input.files.length > 1 ? "s" : ""} selected`;
  chip.classList.remove("hidden");
}

async function loadKBDocs() {
  const listEl = document.getElementById("kb-list");
  const statsEl = document.getElementById("kb-stats");
  if (listEl) listEl.innerHTML = `<div style="padding:12px;text-align:center;color:var(--text-xs);font-size:12px">Loading…</div>`;
  try {
    const [docs, stats] = await Promise.all([
      api("/knowledge-base/documents"),
      api("/knowledge-base/stats"),
    ]);
    kbDocs = docs;
    if (statsEl) {
      statsEl.textContent = `${stats.documents} document${stats.documents !== 1 ? "s" : ""} · ${stats.chunks} chunks`;
    }
    renderKBList(listEl);
  } catch (e) {
    if (listEl) listEl.innerHTML = `<div style="padding:12px;color:var(--red);font-size:12px">Error: ${esc(e.message)}</div>`;
  }
}

function renderKBList(listEl) {
  listEl = listEl || document.getElementById("kb-list");
  if (!listEl) return;
  if (!kbDocs.length) {
    listEl.innerHTML = `<div class="empty-list"><span class="empty-list-icon">📚</span>No documents yet.<br/>Upload a PDF above.</div>`;
    return;
  }
  listEl.innerHTML = kbDocs.map(doc => {
    const statusCls = doc.status === "ready" ? "b-green" : "b-amber";
    return `
      <div class="kb-doc-item">
        <div class="kb-doc-head">
          <span class="kb-doc-icon">📄</span>
          <span class="kb-doc-name" title="${esc(doc.filename)}">${esc(doc.filename)}</span>
          ${badge(doc.status, statusCls)}
        </div>
        <div class="kb-doc-meta">
          <span>${doc.page_count || 0} page${doc.page_count !== 1 ? "s" : ""}</span>
          <span>·</span>
          <span>${doc.chunk_count || 0} chunk${doc.chunk_count !== 1 ? "s" : ""}</span>
          <span>·</span>
          <span>${doc.times_cited || 0} cite${doc.times_cited !== 1 ? "s" : ""}</span>
          <span>·</span>
          <span>${doc.upload_date ? new Date(doc.upload_date).toLocaleDateString() : "—"}</span>
        </div>
        <button class="kb-delete-btn" onclick="deleteKBDoc('${esc(doc.doc_id)}', '${esc(doc.filename)}')">🗑</button>
      </div>`;
  }).join("");
}

async function uploadKBFiles() {
  const input = document.getElementById("kb-file-input");
  const btn = document.getElementById("kb-upload-btn");
  const resultEl = document.getElementById("kb-upload-result");
  if (!input.files.length) { toast("No files selected."); return; }
  if (input.files.length > 5) { toast("Maximum 5 files per upload."); return; }

  btn.disabled = true;
  btn.textContent = "Uploading…";
  if (resultEl) resultEl.innerHTML = "";

  const form = new FormData();
  for (const f of input.files) form.append("files", f);

  try {
    const r = await fetch(API + "/knowledge-base/upload", {
      method: "POST",
      body: form,
      headers: API_KEY ? { "X-API-Key": API_KEY } : {},
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const results = await r.json();

    const lines = results.map(res => {
      const ok = res.status === "ready";
      return `<div style="font-size:11px;color:${ok ? "var(--green)" : "var(--red)"};margin-bottom:2px">
        ${ok ? "✓" : "✗"} <strong>${esc(res.filename)}</strong>${!ok ? ` — ${esc(res.error || res.status)}` : ` (${res.chunk_count} chunks)`}
      </div>`;
    }).join("");
    if (resultEl) resultEl.innerHTML = lines;

    const ok = results.filter(r => r.status === "ready").length;
    toast(`✓ ${ok} of ${results.length} PDF${results.length !== 1 ? "s" : ""} uploaded`);
    input.value = "";
    document.getElementById("kb-file-chip")?.classList.add("hidden");
    await loadKBDocs();
  } catch (e) {
    toast("Upload failed: " + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "⬆️ Upload to Knowledge Base";
  }
}

async function deleteKBDoc(docId, filename) {
  if (!confirm(`Delete "${filename}" from the knowledge base? This removes all its chunks.`)) return;
  try {
    await api(`/knowledge-base/documents/${docId}`, { method: "DELETE" });
    toast(`✓ Deleted: ${filename}`);
    await loadKBDocs();
  } catch (e) {
    toast("Delete failed: " + e.message);
  }
}

// ── Init ───────────────────────────────────────────────────────────────────

function init() {
  document.getElementById("run-btn").addEventListener("click", () => {
    const v = document.getElementById("ticket-input").value.trim();
    if (v) runWorkflow(parseInt(v, 10));
  });

  document.getElementById("ticket-input").addEventListener("keydown", e => {
    if (e.key === "Enter") {
      const v = e.target.value.trim();
      if (v) runWorkflow(parseInt(v, 10));
    }
  });

  document.getElementById("search-btn").addEventListener("click", () => {
    searchWorkflow(document.getElementById("search-input").value);
  });

  document.getElementById("search-input").addEventListener("keydown", e => {
    if (e.key === "Enter") searchWorkflow(e.target.value);
  });

  document.addEventListener("keydown", handleKeyShortcut);

  renderSidebar();
  renderMain();
}

// ── Keyboard shortcuts ─────────────────────────────────────────────────────

const SHORTCUTS_VISIBLE_KEY = "sc_shortcuts_hidden";

function handleKeyShortcut(e) {
  if (["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)) return;
  if (e.metaKey || e.ctrlKey || e.altKey) return;

  const key = e.key.toLowerCase();

  if (key === "?") { toggleShortcutsHelp(); e.preventDefault(); return; }
  if (key === "escape") { closeShortcutsHelp(); return; }

  if (currentTab !== "workflows") return;

  const ordered = _flatOrderedWorkflows();
  const idx = selected ? ordered.findIndex(w => w.workflow_id === selected.workflow_id) : -1;

  switch (key) {
    case "j":
      if (idx < ordered.length - 1) pickWorkflow(ordered[idx + 1].workflow_id);
      e.preventDefault(); break;
    case "k":
      if (idx > 0) pickWorkflow(ordered[idx - 1].workflow_id);
      e.preventDefault(); break;
    case "r":
      refreshWorkflow();
      e.preventDefault(); break;
    case "n":
      switchTab("workflows");
      document.getElementById("ticket-input")?.focus();
      e.preventDefault(); break;
    case "a":
      if (document.getElementById("amode-approved")) { switchApprMode("approved"); e.preventDefault(); }
      break;
    case "m":
      if (document.getElementById("amode-modified")) { switchApprMode("modified"); e.preventDefault(); }
      break;
    case "x":
      if (document.getElementById("amode-rejected")) { switchApprMode("rejected"); e.preventDefault(); }
      break;
  }
}

function toggleShortcutsHelp() {
  const el = document.getElementById("shortcuts-help");
  if (el) { el.remove(); return; }
  showShortcutsHelp();
}

function closeShortcutsHelp() {
  document.getElementById("shortcuts-help")?.remove();
}

function showShortcutsHelp() {
  const el = document.createElement("div");
  el.id = "shortcuts-help";
  el.className = "shortcuts-overlay";
  el.innerHTML = `
    <div class="shortcuts-card">
      <div class="shortcuts-head">
        <span>⌨ Keyboard Shortcuts</span>
        <button onclick="closeShortcutsHelp()" style="background:none;border:none;cursor:pointer;font-size:18px;color:var(--text-muted);line-height:1">×</button>
      </div>
      <div class="shortcuts-body">
        <div class="shortcuts-section">Navigation</div>
        <div class="shortcut-row"><kbd>J</kbd><span>Next workflow</span></div>
        <div class="shortcut-row"><kbd>K</kbd><span>Previous workflow</span></div>
        <div class="shortcut-row"><kbd>R</kbd><span>Refresh current workflow</span></div>
        <div class="shortcut-row"><kbd>N</kbd><span>New workflow (focus ticket input)</span></div>
        <div class="shortcuts-section">Approval (when card is visible)</div>
        <div class="shortcut-row"><kbd>A</kbd><span>Switch to Approve mode</span></div>
        <div class="shortcut-row"><kbd>M</kbd><span>Switch to Modify mode</span></div>
        <div class="shortcut-row"><kbd>X</kbd><span>Switch to Reject mode</span></div>
        <div class="shortcuts-section">UI</div>
        <div class="shortcut-row"><kbd>?</kbd><span>Toggle this panel</span></div>
        <div class="shortcut-row"><kbd>Esc</kbd><span>Close this panel</span></div>
      </div>
    </div>`;
  el.addEventListener("click", e => { if (e.target === el) closeShortcutsHelp(); });
  document.body.appendChild(el);
}

document.addEventListener("DOMContentLoaded", init);

// ════════════════════════════════════════════════════════════════════════════
// DATASETS
// ════════════════════════════════════════════════════════════════════════════

let currentTab = "workflows";
let datasets = [];
let selectedDataset = null;
let dsTickets = [];
let dsTicketsTotal = 0;
let dsTicketsSkip = 0;
const DS_PAGE = 20;

// ── Tab switching ─────────────────────────────────────────────────────────

function switchTab(tab) {
  currentTab = tab;
  const tabs = ["workflows", "datasets", "knowledge-base"];
  tabs.forEach(t => {
    const ids = {
      "workflows":      { tab: "tab-wf", panel: "panel-workflows",    list: "workflow-list" },
      "datasets":       { tab: "tab-ds", panel: "panel-datasets",     list: "dataset-list"  },
      "knowledge-base": { tab: "tab-kb", panel: "panel-knowledge-base", list: "kb-list"     },
    }[t];
    const active = t === tab;
    document.getElementById(ids.tab)?.classList.toggle("active", active);
    document.getElementById(ids.panel)?.classList.toggle("hidden", !active);
    document.getElementById(ids.list)?.classList.toggle("hidden", !active);
  });

  if (tab === "workflows") renderMain();
  else if (tab === "datasets") renderDatasetMain();
  else if (tab === "knowledge-base") loadKBDocs();
}

// ── Upload helper ─────────────────────────────────────────────────────────

async function apiUpload(path, formData) {
  const opts = { method: "POST", body: formData };
  if (API_KEY) opts.headers = { "X-API-Key": API_KEY };
  const r = await fetch(API + path, opts);
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(e.detail || `HTTP ${r.status}`);
  }
  return r.json();
}

// ── Status badge ──────────────────────────────────────────────────────────

function dsStatusBadge(status) {
  const cls = {
    uploaded: "b-gray", analysing: "b-blue", analysed: "b-blue",
    cleaning: "b-blue", cleaned: "b-blue", ingesting: "b-blue",
    ready: "b-green", rejected: "b-red",
  };
  const labels = {
    uploaded: "⬆ Uploaded", analysing: "⟳ Analysing", analysed: "✓ Analysed",
    cleaning: "⟳ Cleaning", cleaned: "✓ Cleaned", ingesting: "⟳ Ingesting",
    ready: "✓ Ready", rejected: "✗ Rejected",
  };
  return badge(labels[status] || status || "unknown", cls[status] || "b-gray");
}

// ── Dataset pipeline step class ───────────────────────────────────────────

function dsStepClass(step, st) {
  const doneFor = {
    upload:  ["analysing","analysed","rejected","cleaning","cleaned","ingesting","ready"],
    analyse: ["cleaning","cleaned","ingesting","ready"],
    clean:   ["ingesting","ready"],
    ingest:  ["ready"],
  };
  const activeFor = { upload: ["uploaded"], analyse: ["analysing","analysed"], clean: ["cleaning","cleaned"], ingest: ["ingesting"] };
  const failedFor = { analyse: ["rejected"] };
  if ((failedFor[step] || []).includes(st)) return "failed";
  if ((doneFor[step] || []).includes(st)) return "done";
  if ((activeFor[step] || []).includes(st)) return "active";
  return "";
}

// ── Dataset sidebar ───────────────────────────────────────────────────────

function renderDatasetSidebar() {
  const el = document.getElementById("dataset-list");
  if (!datasets.length) {
    el.innerHTML = `<div class="empty-list"><span class="empty-list-icon">📂</span>No datasets yet.<br/>Enter your user ID and upload a CSV file.</div>`;
    return;
  }
  el.innerHTML = datasets.map(ds => {
    const active = selectedDataset?.dataset_id === ds.dataset_id;
    return `
      <div class="ds-item ${active ? "active" : ""}" onclick="pickDataset('${ds.dataset_id}')">
        <div class="wf-item-id" title="${esc(ds.dataset_id)}">${esc(ds.dataset_id)}</div>
        <div class="wf-item-title">${esc(ds.file_name)}</div>
        <div class="wf-item-meta">
          ${dsStatusBadge(ds.status)}
          ${ds.valid_rows != null ? badge(ds.valid_rows.toLocaleString() + " rows", "b-gray") : ""}
        </div>
      </div>`;
  }).join("");
}

// ── Load datasets ─────────────────────────────────────────────────────────

async function loadUserDatasets() {
  const userId = document.getElementById("user-id-input").value.trim();
  if (!userId) { toast("Enter a user ID first"); return; }
  try {
    const list = await api(`/datasets?user_id=${encodeURIComponent(userId)}`);
    datasets = list;
    renderDatasetSidebar();
    toast(`Loaded ${list.length} dataset${list.length !== 1 ? "s" : ""}`);
    if (list.length) renderDatasetMain();
  } catch (e) {
    toast("Error: " + e.message);
  }
}

// ── File pick ─────────────────────────────────────────────────────────────

function onFileSelected() {
  const file = document.getElementById("csv-file-input").files[0];
  const chip = document.getElementById("file-name-chip");
  if (file) { chip.textContent = "📄 " + file.name; chip.classList.remove("hidden"); }
  else chip.classList.add("hidden");
}

// ── Upload + auto pipeline ────────────────────────────────────────────────

async function startUpload() {
  const userId = document.getElementById("user-id-input").value.trim();
  const fileInput = document.getElementById("csv-file-input");
  const file = fileInput.files[0];
  if (!userId) { toast("Enter a user ID first"); return; }
  if (!file)   { toast("Select a CSV file first"); return; }

  const btn = document.getElementById("upload-btn");
  btn.disabled = true;

  const setLabel = (txt) => {
    btn.innerHTML = `<span class="spinner"></span> ${txt}`;
  };

  try {
    setLabel("Uploading…");
    const formData = new FormData();
    formData.append("user_id", userId);
    formData.append("file", file);
    let ds;
    try {
      ds = await apiUpload("/datasets/upload", formData);
    } catch (e) { toast("Upload failed: " + e.message); return; }

    const idx = datasets.findIndex(d => d.dataset_id === ds.dataset_id);
    if (idx >= 0) datasets[idx] = ds; else datasets.unshift(ds);
    selectedDataset = ds;
    dsTickets = []; dsTicketsTotal = 0; dsTicketsSkip = 0;
    renderDatasetSidebar();
    renderDatasetMain();

    if (ds.duplicate) { toast("ℹ️ Duplicate file — already processed."); return; }

    setLabel("Analysing with AI…");
    let ar;
    try {
      ar = await api(`/datasets/${ds.dataset_id}/analyse`, { method: "POST" });
    } catch (e) { toast("Analysis error: " + e.message); await refreshDataset(ds.dataset_id); return; }
    await refreshDataset(ds.dataset_id);

    if (!ar.is_customer_service_data) {
      toast("✗ Rejected: " + (ar.rejection_reason || "Not customer support data"));
      return;
    }

    setLabel("Cleaning rows…");
    try {
      await api(`/datasets/${ds.dataset_id}/clean`, { method: "POST" });
    } catch (e) { toast("Clean error: " + e.message); await refreshDataset(ds.dataset_id); return; }
    await refreshDataset(ds.dataset_id);

    setLabel("Ingesting tickets…");
    let ir;
    try {
      ir = await api(`/datasets/${ds.dataset_id}/ingest`, { method: "POST" });
    } catch (e) { toast("Ingest error: " + e.message); await refreshDataset(ds.dataset_id); return; }

    await refreshDataset(ds.dataset_id);
    await loadDatasetTickets(ds.dataset_id, 0);
    renderDatasetMain();
    toast(`✓ Ready — ${ir.total.toLocaleString()} tickets ingested!`);

    fileInput.value = "";
    document.getElementById("file-name-chip").classList.add("hidden");

  } finally {
    btn.disabled = false;
    btn.innerHTML = "⚡ Upload &amp; Run Pipeline";
  }
}

// ── Refresh ───────────────────────────────────────────────────────────────

async function refreshDataset(datasetId) {
  try {
    const ds = await api(`/datasets/${datasetId}`);
    const idx = datasets.findIndex(d => d.dataset_id === datasetId);
    if (idx >= 0) datasets[idx] = ds; else datasets.unshift(ds);
    if (selectedDataset?.dataset_id === datasetId) selectedDataset = ds;
    renderDatasetSidebar();
    renderDatasetMain();
  } catch { /* silent */ }
}

// ── Select dataset ────────────────────────────────────────────────────────

async function pickDataset(datasetId) {
  try {
    const ds = await api(`/datasets/${datasetId}`);
    const idx = datasets.findIndex(d => d.dataset_id === datasetId);
    if (idx >= 0) datasets[idx] = ds; else datasets.unshift(ds);
    selectedDataset = ds;
    dsTickets = []; dsTicketsTotal = 0; dsTicketsSkip = 0;
    if (ds.status === "ready") await loadDatasetTickets(datasetId, 0);
    renderDatasetSidebar();
    renderDatasetMain();
  } catch (e) { toast("Error: " + e.message); }
}

// ── Ticket pagination ─────────────────────────────────────────────────────

async function loadDatasetTickets(datasetId, skip) {
  try {
    const r = await api(`/datasets/${datasetId}/tickets?limit=${DS_PAGE}&skip=${skip}`);
    dsTickets = skip === 0 ? r.tickets : [...dsTickets, ...r.tickets];
    dsTicketsTotal = r.total;
    dsTicketsSkip = skip + r.tickets.length;
  } catch { /* silent */ }
}

async function loadMoreTickets() {
  if (!selectedDataset) return;
  await loadDatasetTickets(selectedDataset.dataset_id, dsTicketsSkip);
  renderDatasetMain();
}

// ── Delete ────────────────────────────────────────────────────────────────

async function deleteDatasetConfirm(datasetId) {
  if (!confirm(`Delete dataset "${datasetId}"?\n\nThis removes all ingested tickets and cannot be undone.`)) return;
  try {
    await api(`/datasets/${datasetId}`, { method: "DELETE" });
    datasets = datasets.filter(d => d.dataset_id !== datasetId);
    if (selectedDataset?.dataset_id === datasetId) {
      selectedDataset = null;
      dsTickets = []; dsTicketsTotal = 0; dsTicketsSkip = 0;
    }
    renderDatasetSidebar();
    renderDatasetMain();
    toast("Dataset deleted");
  } catch (e) { toast("Delete failed: " + e.message); }
}

// ── Run workflow on ticket ────────────────────────────────────────────────

async function runDatasetTicketWorkflow(datasetId, rowId, btnEl) {
  if (btnEl) {
    btnEl.disabled = true;
    btnEl.innerHTML = `<span class="spinner"></span>`;
  }
  try {
    const result = await api(`/workflows/datasets/${datasetId}/tickets/${rowId}`, { method: "POST" });
    workflows.unshift(result);
    selected = result;
    switchTab("workflows");
    renderSidebar();
    renderMain();
    toast(`✓ Workflow started for row #${rowId}`);
  } catch (e) {
    toast("Workflow error: " + e.message);
    if (btnEl) { btnEl.disabled = false; btnEl.textContent = "Run"; }
  }
}

// ── Dataset welcome state ─────────────────────────────────────────────────

function renderDatasetWelcome() {
  return `
    <div class="ds-welcome">
      <div class="ds-welcome-hero">
        <div class="ds-welcome-hero-icon">📂</div>
        <h1>Upload Your Support Data</h1>
        <p>Import a CSV export from your helpdesk. SupportCommander will auto-detect column structure, clean the data, and make each ticket ready to run through the full AI resolution pipeline.</p>
      </div>

      <div class="welcome-section-title" style="margin-bottom:12px">How it works</div>
      <div class="ds-steps">
        <div class="ds-step">
          <div class="ds-step-num s1">1</div>
          <div class="ds-step-body">
            <h4>Upload CSV</h4>
            <p>Any customer-support CSV — Zendesk, Freshdesk, Intercom, or custom format. Up to 50 MB. SupportCommander auto-detects encoding and delimiter.</p>
          </div>
        </div>
        <div class="ds-step">
          <div class="ds-step-num s2">2</div>
          <div class="ds-step-body">
            <h4>AI Column Analysis</h4>
            <p>One LLM call maps your CSV columns (e.g. "Body", "Issue Text") to internal fields (ticket_text, urgency, date…). Non–customer-support files are rejected at this stage.</p>
          </div>
        </div>
        <div class="ds-step">
          <div class="ds-step-num s3">3</div>
          <div class="ds-step-body">
            <h4>Deterministic Cleaning</h4>
            <p>Strips HTML, normalises dates, removes duplicates and empty rows — no LLM needed. Cleaned rows are stored in GridFS for fast re-runs.</p>
          </div>
        </div>
        <div class="ds-step">
          <div class="ds-step-num s4">4</div>
          <div class="ds-step-body">
            <h4>Ingest &amp; Run Workflows</h4>
            <p>Tickets are ingested into <code style="background:var(--surface-3);padding:1px 5px;border-radius:3px">user_tickets</code>. Click <strong>Run</strong> on any row to execute the full 8-stage AI workflow and see the resolution result.</p>
          </div>
        </div>
      </div>

      <div class="welcome-cta">
        <div style="font-size:28px">👈</div>
        <div class="welcome-cta-text">
          <strong>Enter your User ID and upload a CSV to begin</strong>
          <span>All datasets are scoped to your user ID — enter any identifier (e.g. your name or team).</span>
        </div>
      </div>
    </div>`;
}

// ── Dataset pipeline bar (numbered circles) ───────────────────────────────

function renderDsPipeline(st) {
  const steps = [
    { key: "upload",  label: "Upload",  num: "⬆" },
    { key: "analyse", label: "Analyse", num: "🔍" },
    { key: "clean",   label: "Clean",   num: "✨" },
    { key: "ingest",  label: "Ingest",  num: "✅" },
  ];
  return steps.map((s, i) => {
    const cls = dsStepClass(s.key, st);
    return `
      <div class="ds-stage-step">
        <div class="ds-stage-inner">
          <div class="ds-stage-circle ${cls}">${s.num}</div>
          <div class="ds-stage-name ${cls}">${s.label}</div>
        </div>
        ${i < steps.length - 1 ? `<div class="ds-stage-arrow ${cls === "done" ? "done" : ""}"></div>` : ""}
      </div>`;
  }).join("");
}

// ── Main panel ────────────────────────────────────────────────────────────

function renderDatasetMain() {
  if (currentTab !== "datasets") return;
  const panel = document.getElementById("main-panel");

  if (!selectedDataset) {
    panel.innerHTML = renderDatasetWelcome();
    return;
  }

  const ds = selectedDataset;
  const st = ds.status || "uploaded";

  const sizeLabel = ds.file_size_bytes
    ? ds.file_size_bytes >= 1048576
      ? (ds.file_size_bytes / 1048576).toFixed(1) + " MB"
      : Math.round(ds.file_size_bytes / 1024) + " KB"
    : "";

  let html = `
    <div class="wf-hero">
      <div class="wf-hero-info">
        <h2>${esc(ds.file_name)}</h2>
        <div class="wf-hero-meta">
          <span class="wf-id-chip"
            onclick="navigator.clipboard.writeText('${esc(ds.dataset_id)}').then(()=>toast('ID copied!'))"
            title="Click to copy dataset ID">${esc(ds.dataset_id)}</span>
          ${dsStatusBadge(st)}
          ${sizeLabel ? badge(sizeLabel, "b-gray") : ""}
          <span style="font-size:11px;color:var(--text-xs)">Uploaded ${fmt(ds.created_at)}</span>
        </div>
      </div>
      <div class="wf-hero-actions">
        <button class="btn btn-ghost btn-sm" onclick="pickDataset('${ds.dataset_id}')">↻ Refresh</button>
        <button class="btn btn-danger btn-sm" onclick="deleteDatasetConfirm('${ds.dataset_id}')">🗑 Delete</button>
      </div>
    </div>
    <div class="ds-pipeline">${renderDsPipeline(st)}</div>
    <div class="cards">`;

  // Rejection
  if (st === "rejected") {
    html += `
      <div class="card card-accent-red">
        <div class="card-head"><h3>✗ Dataset Rejected</h3></div>
        <div class="card-body">
          <div class="error-bar" style="margin-top:0">${esc(ds.rejection_reason || "This file was not recognised as customer support data.")}</div>
          <div style="margin-top:12px;font-size:12px;color:var(--text-muted)">
            The AI could not identify a customer message or complaint column. Try a different CSV that contains ticket or complaint text.
          </div>
        </div>
      </div>`;
  }

  // In-progress indicator
  if (["analysing","cleaning","ingesting"].includes(st)) {
    const label = { analysing: "AI is analysing your dataset…", cleaning: "Cleaning and normalising rows…", ingesting: "Ingesting tickets into the database…" }[st];
    html += `
      <div class="card">
        <div class="card-body" style="display:flex;align-items:center;gap:12px;padding:18px 20px">
          <span class="spinner" style="border-color:rgba(79,70,229,.2);border-top-color:var(--primary);width:18px;height:18px;"></span>
          <span style="color:var(--primary-dark);font-weight:600;font-size:13px">${label}</span>
        </div>
      </div>`;
  }

  // Column mapping
  const colMap = ds.column_mapping;
  if (colMap && Object.keys(colMap).length) {
    const unmapped = ds.unmapped_columns || [];
    html += `
      <div class="card card-accent-left">
        <div class="card-head">
          <h3>🗂️ Column Mapping</h3>
          ${ds.domain_confidence ? badge(ds.domain_confidence + " confidence", "b-indigo") : ""}
          <span style="margin-left:auto;font-size:11px;color:var(--text-muted)">${Object.keys(colMap).length} mapped · ${unmapped.length} unmapped</span>
        </div>
        <div class="card-body" style="padding:0">
          <table class="mapping-table">
            <thead style="background:var(--surface-2)">
              <tr>
                <td style="padding:7px 16px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--text-xs)">CSV Column</td>
                <td></td>
                <td style="padding:7px 16px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--text-xs)">Internal Field</td>
              </tr>
            </thead>
            <tbody>
              ${Object.entries(colMap).map(([csv, field]) => `
                <tr>
                  <td class="mapping-csv">${esc(csv)}</td>
                  <td class="mapping-arrow">→</td>
                  <td class="mapping-field">${esc(field)}</td>
                </tr>`).join("")}
              ${unmapped.map(c => `
                <tr style="opacity:.5">
                  <td class="mapping-csv">${esc(c)}</td>
                  <td class="mapping-arrow">—</td>
                  <td style="font-size:11px;color:var(--text-xs)">not used</td>
                </tr>`).join("")}
            </tbody>
          </table>
        </div>
      </div>`;
  }

  // Stats
  if (ds.row_count_raw != null) {
    const applied = ds.cleaning_applied || [];
    const flags   = ds.cleaning_flags   || [];
    const kept = ds.valid_rows ?? 0;
    const raw  = ds.row_count_raw ?? 0;
    const drop = ds.dropped_rows ?? 0;
    html += `
      <div class="card card-accent-green">
        <div class="card-head"><h3>📊 Dataset Stats</h3></div>
        <div class="card-body" style="padding:0">
          <div class="stats-row">
            <div class="stat-cell">
              <div class="stat-label">Raw Rows</div>
              <div class="stat-value">${raw.toLocaleString()}</div>
              <div class="stat-sub">in uploaded CSV</div>
            </div>
            <div class="stat-cell">
              <div class="stat-label">Valid Rows</div>
              <div class="stat-value" style="color:var(--green)">${kept.toLocaleString()}</div>
              <div class="stat-sub">${raw > 0 ? Math.round(kept/raw*100) : 0}% kept</div>
            </div>
            <div class="stat-cell">
              <div class="stat-label">Dropped</div>
              <div class="stat-value" style="color:var(--red)">${drop.toLocaleString()}</div>
              <div class="stat-sub">empty / duplicate</div>
            </div>
            ${ds.ingested_count != null ? `
            <div class="stat-cell">
              <div class="stat-label">Ingested</div>
              <div class="stat-value" style="color:var(--primary)">${ds.ingested_count.toLocaleString()}</div>
              <div class="stat-sub">ready for workflows</div>
            </div>` : ""}
          </div>
          ${applied.length ? `
            <div style="padding:12px 16px;border-top:1px solid var(--border-light)">
              <div class="section-label">Cleaning steps applied</div>
              <div style="display:flex;flex-wrap:wrap;gap:5px">${applied.map(f => badge("✓ " + f, "b-green")).join("")}</div>
            </div>` : ""}
          ${flags.length && !applied.length ? `
            <div style="padding:12px 16px;border-top:1px solid var(--border-light)">
              <div class="section-label">Detected flags</div>
              <div style="display:flex;flex-wrap:wrap;gap:5px">${flags.map(f => badge(f, "b-amber")).join("")}</div>
            </div>` : ""}
        </div>
      </div>`;
  }

  // Ticket list
  if (st === "ready") {
    const remaining = dsTicketsTotal - dsTickets.length;
    html += `
      <div class="card">
        <div class="card-head">
          <h3>🎫 Tickets</h3>
          <span style="margin-left:auto;font-size:11px;color:var(--text-muted)">showing ${dsTickets.length} of ${dsTicketsTotal.toLocaleString()}</span>
        </div>
        <div class="card-body" style="padding:0 16px">
          <div style="padding:10px 0 4px;font-size:11px;color:var(--text-muted)">
            Click <strong>Run</strong> on any row to execute the full AI resolution pipeline for that ticket.
          </div>
          ${dsTickets.length ? dsTickets.map(t => `
            <div class="ticket-row">
              <span class="ticket-row-idx">#${t.row_id}</span>
              <div class="ticket-row-text" title="${esc(t.ticket_text)}">${esc((t.ticket_text || "").slice(0, 100))}${(t.ticket_text || "").length > 100 ? "…" : ""}</div>
              <div class="ticket-row-meta">
                ${t.urgency ? decisionBadge(t.urgency) : ""}
                <button class="btn btn-primary btn-xs"
                  onclick="runDatasetTicketWorkflow('${ds.dataset_id}', ${t.row_id}, this)">Run</button>
              </div>
            </div>`).join("") : `<div class="info-bar" style="margin:12px 0">No tickets found in this dataset.</div>`}
          ${remaining > 0 ? `
            <div style="padding:14px 0 8px;text-align:center">
              <button class="btn btn-ghost btn-sm" onclick="loadMoreTickets()">
                Load ${Math.min(DS_PAGE, remaining)} more <span class="badge b-gray" style="margin-left:4px">${remaining} remaining</span>
              </button>
            </div>` : ""}
        </div>
      </div>`;
  } else if (st !== "rejected") {
    html += `
      <div class="card">
        <div class="card-head"><h3>🎫 Tickets</h3></div>
        <div class="card-body">
          <div class="info-bar">
            Tickets will be available here once the pipeline reaches <strong>Ready</strong> status.
            ${["uploaded","analysed","cleaned"].includes(st) ? `<br/><br/><button class="btn btn-primary btn-sm" onclick="startUpload()">Re-run pipeline from current step</button>` : ""}
          </div>
        </div>
      </div>`;
  }

  html += "</div>";
  panel.innerHTML = html;
}
