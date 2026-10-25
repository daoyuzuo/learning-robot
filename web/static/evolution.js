(function () {
  const root = document.getElementById("evolution");
  if (!root) return;
  const enabled = root.dataset.enabled === "true";
  const progress = root.querySelector('[data-role="progress"]');
  const current = root.querySelector('[data-role="current"]');
  const errorBox = root.querySelector('[data-role="error"]');
  const results = root.querySelector('[data-role="results"]');
  const start = root.querySelector('[data-action="start"]');
  let timer = null;

  function showError(message) {
    errorBox.hidden = false;
    errorBox.textContent = message;
  }

  function clearError() {
    errorBox.hidden = true;
    errorBox.textContent = "";
  }

  async function call(url, options) {
    const response = await fetch(url, options);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = payload.detail;
      throw new Error(
        detail ? (detail.message || detail) : "请求失败"
      );
    }
    return payload;
  }

  function node(tag, text, className) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
  }

  function qualityLine(quality) {
    if (!quality) return "质量分不可用";
    return "质量 " + quality.score + "/" + quality.possible +
      (quality.ok === false ? "（未通过）" : "");
  }

  function qualityDelta(before, after) {
    if (!before || !after) return "";
    const diff = after.score - before.score;
    return "（" + (diff > 0 ? "+" : "") + diff + "）";
  }

  function historyLink(draftId, lessonId) {
    const link = node("a", "查看历史");
    link.href = "/studio/" + encodeURIComponent(draftId) +
      "/history/" + encodeURIComponent(lessonId);
    return link;
  }

  function renderLesson(draftId, lesson) {
    const item = node("li");
    item.appendChild(node("strong", lesson.lesson_id + " "));
    if (!lesson.ok) {
      item.appendChild(node(
        "span", "失败：" + (lesson.error || "未知错误"), "tb-error"
      ));
      item.appendChild(historyLink(draftId, lesson.lesson_id));
      return item;
    }
    const before = lesson.before || {};
    const after = lesson.after || {};
    const changed = lesson.changed || {};
    item.appendChild(node(
      "span",
      "练习 " + (before.exercise_count || 0) + "→" +
        (after.exercise_count || 0) + " · 资源 " +
        (before.resource_count || 0) + "→" +
        (after.resource_count || 0) + " · 版本 " +
        (before.prompt_version || "?") + "→" +
        (after.prompt_version || "?")
    ));
    if (changed.types_added && changed.types_added.length) {
      item.appendChild(node("span", " · 新增题型 " + changed.types_added.join("、")));
    }
    if (changed.types_removed && changed.types_removed.length) {
      item.appendChild(node("span", " · 移除题型 " + changed.types_removed.join("、")));
    }
    item.appendChild(historyLink(draftId, lesson.lesson_id));
    return item;
  }

  function renderDraft(draft) {
    const section = node("section", undefined, "tb-evo-result");
    section.appendChild(node("h3", draft.draft_id));
    if (draft.error) {
      section.appendChild(node("p", "草稿失败：" + draft.error, "tb-error"));
    }
    const quality = node(
      "p",
      qualityLine(draft.quality_before) + " → " +
        qualityLine(draft.quality_after) +
        qualityDelta(draft.quality_before, draft.quality_after)
    );
    section.appendChild(quality);
    const list = node("ul");
    (draft.lessons || []).forEach((lesson) => {
      list.appendChild(renderLesson(draft.draft_id, lesson));
    });
    section.appendChild(list);
    return section;
  }

  function render(payload) {
    if (payload.status === "idle") {
      progress.textContent = "";
      current.textContent = "";
      results.replaceChildren();
      return;
    }
    progress.textContent = "完成 " + (payload.done || 0) + "/" +
      (payload.total || 0);
    if (payload.current) {
      current.textContent = "当前 " + payload.current.draft_id +
        (payload.current.lesson_id ? " / " + payload.current.lesson_id : "");
    } else {
      current.textContent = "";
    }
    if (payload.error) {
      showError(payload.error);
    }
    results.replaceChildren();
    (payload.results || []).forEach((draft) => {
      results.appendChild(renderDraft(draft));
    });
  }

  function stopPolling() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
  }

  function startPolling() {
    if (!timer) timer = setInterval(poll, 2000);
  }

  async function poll() {
    try {
      const payload = await call("/api/studio/evolution/status");
      render(payload);
      if (payload.status === "running") {
        if (start) start.disabled = true;
        startPolling();
      } else {
        stopPolling();
        if (start) start.disabled = !enabled;
      }
    } catch (err) {
      stopPolling();
      showError(err.message);
    }
  }

  if (start) {
    start.addEventListener("click", async () => {
      if (!enabled) return;
      clearError();
      const targets = [];
      root.querySelectorAll(".tb-evo-check:checked").forEach((box) => {
        targets.push({
          draft_id: box.dataset.draft,
          lesson_id: box.dataset.lesson,
        });
      });
      if (!targets.length) {
        showError("请先勾选课程");
        return;
      }
      start.disabled = true;
      try {
        await call("/api/studio/evolution", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ targets: targets }),
        });
        await poll();
      } catch (err) {
        showError(err.message);
        start.disabled = !enabled;
      }
    });
  }

  poll();
})();
