(function () {
  const root = document.getElementById("studio");
  if (!root) return;
  const draftId = root.dataset.draft;
  const enabled = root.dataset.enabled === "true";
  const error = root.querySelector(".tb-error");
  let timer = null;

  function showError(message) {
    error.hidden = false;
    error.textContent = message;
  }

  async function call(url, options) {
    const response = await fetch(url, options);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail ? (payload.detail.message || payload.detail) : "请求失败");
    }
    return payload;
  }

  function paintLesson(step, lesson, entry) {
    const status = root.querySelector(`[data-step-status="${step}:${lesson}"]`);
    if (status) {
      status.textContent = entry.status || "pending";
      status.dataset.status = entry.status || "pending";
    }
    const progress = root.querySelector(`[data-progress-for="${step}:${lesson}"]`);
    if (!progress) return;
    const done = entry.queries || 0;
    const total = entry.total || 0;
    if (step === "research" && entry.status === "running") {
      progress.textContent = total ? `检索 ${done}/${total}` : `检索 ${done}`;
    } else if (step === "research" && done) {
      progress.textContent = `检索 ${done} 次，命中 ${entry.hits || 0} 条`;
    } else {
      progress.textContent = "";
    }
  }

  function paintQuality(quality) {
    const box = root.querySelector(".tb-quality");
    if (!box) return;
    const score = box.querySelector(".tb-quality-score");
    const flags = box.querySelector(".tb-quality-flags");
    const note = box.querySelector(".tb-quality-note");
    const list = box.querySelector(".tb-quality-metrics");
    list.replaceChildren();
    if (!quality) {
      score.textContent = "—";
      flags.textContent = "";
      note.textContent = "质量评估未运行";
      return;
    }
    score.textContent = quality.score + "/100";
    flags.textContent = "硬错误 " + quality.errors.length + " · 警告 " +
      quality.warnings.length;
    note.textContent = quality.provenance_evaluated ? "" : "溯源与调研未评估";
    quality.metrics.forEach((metric) => {
      const item = document.createElement("li");
      item.textContent = metric.label + " " + metric.earned + "/" +
        metric.possible + " · " + metric.detail;
      list.appendChild(item);
    });
  }

  function batchProgressBar(node) {
    const next = node.nextElementSibling;
    if (next && next.classList.contains("tb-progress-bar")) return next;
    const bar = document.createElement("progress");
    bar.className = "tb-progress-bar";
    bar.setAttribute("aria-label", "批量进度");
    node.insertAdjacentElement("afterend", bar);
    return bar;
  }

  function paintBatch(batch) {
    document.querySelectorAll("[data-batch-status]").forEach((node) => {
      if (!batch || !batch.mode || node.dataset.batchStatus !== batch.mode) {
        node.textContent = "";
        delete node.dataset.status;
        return;
      }
      node.textContent = batch.status === "failed"
        ? "失败：" + (batch.error || "")
        : "完成 " + (batch.done || 0) + "/" + (batch.total || 0);
      node.dataset.status = batch.status || "";
      const bar = batchProgressBar(node);
      const total = Number(batch.total) || 0;
      if (total > 0) {
        bar.max = total;
        bar.value = Number(batch.done) || 0;
      } else {
        bar.removeAttribute("max");
        bar.removeAttribute("value");
      }
    });
  }

  function paint(payload) {
    document.querySelectorAll("[data-status-for]").forEach((node) => {
      const entry = payload.steps[node.dataset.statusFor] || {};
      node.textContent = entry.status || "pending";
      node.dataset.status = entry.status || "pending";
    });
    paintBatch(payload.steps.batch);
    ["research", "lessons"].forEach((step) => {
      Object.entries(payload.steps[step] || {}).forEach(([lesson, entry]) => {
        paintLesson(step, lesson, entry);
      });
    });
    paintQuality(payload.steps.validation && payload.steps.validation.quality);
    const issues = payload.steps.validation && payload.steps.validation.issues;
    if (Array.isArray(issues)) {
      root.querySelector('[data-step="validation"] .tb-issues').textContent =
        issues.join("\n") || "校验通过";
    }
  }

  async function poll() {
    try {
      const payload = await call("/api/studio/" + draftId);
      paint(payload);
      const busy = JSON.stringify(payload.steps).includes('"running"');
      if (busy) {
        startPolling();
      } else if (timer) {
        clearInterval(timer);
        timer = null;
      }
    } catch (err) {
      showError(err.message);
    }
  }

  function startPolling() {
    if (!timer) timer = setInterval(poll, 2000);
  }

  root.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!enabled) return;
      error.hidden = true;
      const action = button.dataset.action;
      const lesson = button.dataset.lesson || null;
      try {
        if (action === "save-outline") {
          const editor = root.querySelector(".tb-outline-editor");
          await call("/api/studio/" + draftId + "/outline", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ html: editor.innerHTML }),
          });
          location.reload();
          return;
        }
        if (action === "regen-outline") {
          await call("/api/studio/" + draftId + "/outline", { method: "POST" });
        } else if (action === "batch-research" || action === "batch-lessons") {
          await call("/api/studio/" + draftId + "/batch", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              mode: action === "batch-research" ? "research" : "lessons",
            }),
          });
        } else if (action === "rewrite") {
          await call("/api/studio/" + draftId + "/lessons", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ lesson_id: lesson, replace: true }),
          });
        } else if (action === "research") {
          await call("/api/studio/" + draftId + "/research", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ lesson_id: lesson }),
          });
        } else if (action === "lesson") {
          await call("/api/studio/" + draftId + "/lessons", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ lesson_id: lesson }),
          });
        } else if (action === "validate") {
          const skipVerify = root.querySelector(".tb-skip-verify").checked;
          const payload = await call("/api/studio/" + draftId + "/validate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ skip_verify: skipVerify }),
          });
          paintQuality(payload.quality);
          root.querySelector('[data-step="validation"] .tb-issues').textContent =
            [...payload.errors, ...payload.warnings].join("\n") ||
            (payload.ok ? "校验通过" : "");
        } else if (action === "promote") {
          const force = root.querySelector(".tb-force").checked;
          const skipVerify = root.querySelector(".tb-skip-verify-promote").checked;
          const payload = await call("/api/studio/" + draftId + "/promote", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ force: force, skip_verify: skipVerify }),
          });
          root.querySelector(".tb-promote-path").textContent = "已写入 " + payload.path;
        }
        startPolling();
        poll();
      } catch (err) {
        showError(err.message);
      }
    });
  });

  // Refresh once on load so a reload mid/after a batch shows progress and
  // rewrite controls; polling continues only while a step is running.
  poll();
})();
