(function () {
  const lessonId = document.body.dataset.lessonId || "";

  function collect(form, type) {
    if (type === "single_choice") {
      const el = form.querySelector('input[name="answer"]:checked');
      return el ? el.value : null;
    }
    if (type === "multi_choice") {
      return Array.from(form.querySelectorAll('input[name="answer"]:checked')).map((el) => el.value);
    }
    if (type === "short_answer") {
      return form.querySelector('textarea[name="answer"]').value;
    }
    if (type === "self_assess") {
      return { checked: Array.from(form.querySelectorAll('input[name="checked"]:checked')).map((el) => el.value) };
    }
    if (type === "artifact") {
      return {
        notes: form.querySelector('textarea[name="notes"]').value,
        checked: Array.from(form.querySelectorAll('input[name="checked"]:checked')).map((el) => el.value),
      };
    }
    return null;
  }

  let sessionCorrect = 0;

  function markSessionProgress(form, correct) {
    const card = form.closest(".tb-session-card");
    if (!card) return;
    if (correct) sessionCorrect += 1;
    const score = document.querySelector(".tb-session-correct");
    if (score) score.textContent = String(sessionCorrect);
    const next = card.querySelector(".tb-session-next");
    if (next) next.hidden = false;
  }

  function wireSession() {
    const session = document.querySelector(".tb-session");
    if (!session) return;
    const cards = Array.from(session.querySelectorAll(".tb-session-card"));
    const done = session.querySelector(".tb-session-done");
    cards.forEach((card, index) => {
      const button = card.querySelector(".tb-session-next button");
      if (!button) return;
      button.addEventListener("click", () => {
        card.hidden = true;
        const following = cards[index + 1];
        if (following) {
          following.hidden = false;
          following.scrollIntoView({ block: "start" });
        } else if (done) {
          done.hidden = false;
        }
      });
    });
  }

  function tutorEnabled() {
    const panel = document.querySelector(".tb-tutor");
    return panel && panel.dataset.tutorEnabled === "true";
  }

  function renderReview(container, payload) {
    container.innerHTML = "";
    const badge = document.createElement("p");
    badge.className = "tb-review-verdict";
    badge.textContent = "AI 讲评（" + payload.model + "）";
    container.appendChild(badge);

    const explanation = document.createElement("p");
    explanation.textContent = payload.explanation;
    container.appendChild(explanation);

    [["优点", payload.strengths], ["差距", payload.gaps]].forEach(([label, items]) => {
      if (!items || !items.length) return;
      const title = document.createElement("p");
      title.textContent = label + "：";
      container.appendChild(title);
      const list = document.createElement("ul");
      items.forEach((item) => {
        const li = document.createElement("li");
        li.textContent = item;
        list.appendChild(li);
      });
      container.appendChild(list);
    });

    if (payload.rubric && payload.rubric.length) {
      const table = document.createElement("table");
      payload.rubric.forEach((item) => {
        const row = document.createElement("tr");
        [item.dimension, item.met ? "达成" : "未达成", item.comment].forEach((text) => {
          const cell = document.createElement("td");
          cell.textContent = text;
          row.appendChild(cell);
        });
        table.appendChild(row);
      });
      container.appendChild(table);
    }

    if (payload.suggested_score !== null && payload.suggested_score !== undefined) {
      const score = document.createElement("p");
      score.className = "tb-review-score";
      score.textContent =
        "参考分 " + payload.suggested_score.toFixed(2)
        + "（" + payload.model + "，不参与掌握度）";
      container.appendChild(score);
    }
  }

  function maybeAddReviewButton(form, evidenceId) {
    if (!tutorEnabled() || !evidenceId) return;
    if (form.querySelector(".tb-review-button")) return;
    const box = document.createElement("div");
    box.className = "tb-review";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "tb-review-button";
    button.textContent = "让 AI 讲讲";
    button.addEventListener("click", async () => {
      button.disabled = true;
      const original = button.textContent;
      button.textContent = "正在讲评…";
      try {
        const response = await fetch("/api/review", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ evidence_id: evidenceId }),
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.detail ? payload.detail.message : "讲评失败");
        }
        renderReview(box, payload);
      } catch (err) {
        box.textContent = "讲评失败：" + err.message;
      } finally {
        button.disabled = false;
        button.textContent = original;
      }
    });
    box.appendChild(button);
    form.appendChild(box);
  }

  document.querySelectorAll("form.tb-exercise").forEach((form) => {
    let hintsUsed = 0;
    const startedAt = Date.now();
    const hintButton = form.querySelector(".tb-hint-button");
    if (hintButton) {
      hintButton.addEventListener("click", () => {
        const next = Array.from(form.querySelectorAll(".tb-hint[hidden]"))[0];
        if (next) {
          next.hidden = false;
          hintsUsed += 1;
        } else {
          hintButton.disabled = true;
          hintButton.textContent = "没有更多提示";
        }
      });
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const type = form.dataset.exerciseType;
      const response = collect(form, type);
      const feedback = form.querySelector(".tb-feedback");
      const button = form.querySelector('button[type="submit"]');
      let endpoint = "/api/evidence";
      let request = null;
      if (type === "artifact") {
        const fileInput = form.querySelector('input[name="file"]');
        if (!fileInput || !fileInput.files.length) {
          feedback.hidden = false;
          feedback.textContent = "请先选择文件。";
          return;
        }
        const formData = new FormData();
        formData.append("lesson_id", form.dataset.lessonId || lessonId);
        formData.append("exercise_id", form.dataset.exerciseId);
        formData.append("notes", response.notes || "");
        formData.append("checked", JSON.stringify(response.checked || []));
        formData.append("hints_used", String(hintsUsed));
        formData.append("duration_ms", String(Date.now() - startedAt));
        formData.append("file", fileInput.files[0]);
        endpoint = "/api/artifact";
        request = { method: "POST", body: formData };
      } else {
        request = {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            lesson_id: form.dataset.lessonId || lessonId,
            exercise_id: form.dataset.exerciseId,
            response,
            hints_used: hintsUsed,
            duration_ms: Date.now() - startedAt,
          }),
        };
      }
      button.disabled = true;
      try {
        const res = await fetch(endpoint, request);
        if (!res.ok) throw new Error(await res.text());
        const payload = await res.json();
        feedback.hidden = false;
        feedback.dataset.outcome = payload.grade.outcome;
        feedback.textContent = payload.grade.feedback;
        maybeAddReviewButton(form, payload.evidence_id);
        markSessionProgress(form, payload.grade.correct);
      } catch (err) {
        feedback.hidden = false;
        feedback.textContent = "提交失败：" + err.message;
        button.disabled = false;
      }
    });
  });

  document.querySelectorAll(".tb-widget").forEach((widget) => {
    const template = widget.querySelector("template.tb-widget-template");
    const canvas = widget.querySelector(".tb-widget-canvas");
    if (!template || !canvas) return;
    const inputs = Array.from(widget.querySelectorAll("input[data-param]"));
    function render() {
      let html = template.innerHTML;
      inputs.forEach((input) => {
        html = html.split("{{" + input.dataset.param + "}}").join(input.value);
        const output = input.parentElement.querySelector("output");
        if (output) output.textContent = input.value;
      });
      canvas.innerHTML = html;
    }
    inputs.forEach((input) => input.addEventListener("input", render));
    render();
  });

  const tutor = document.querySelector(".tb-tutor");
  if (tutor && tutor.dataset.tutorEnabled === "true") {
    const anchor = tutor.querySelector(".tb-tutor-anchor");
    const input = tutor.querySelector(".tb-tutor-question");
    const button = tutor.querySelector(".tb-tutor-submit");
    const log = tutor.querySelector(".tb-tutor-log");
    const error = tutor.querySelector(".tb-tutor-error");
    const webToggle = tutor.querySelector(".tb-tutor-web-toggle");
    const webState = tutor.querySelector("[data-web-state]");
    if (webToggle && webState) {
      const paintWebState = () => {
        webState.textContent = webToggle.checked ? "已开启" : "已关闭";
      };
      webToggle.addEventListener("change", paintWebState);
      paintWebState();
    }

    const basisLabels = {
      lesson: "本课内容",
      resource: "包内资源",
      web: "网络来源",
      general: "通用知识",
    };

    const SELECTION_MAX = 400;
    const lessonBody = document.querySelector(".tb-lesson");
    const pendingQuote = tutor.querySelector(".tb-tutor-quote-pending");
    let selection = "";

    function normalize(text) {
      return String(text || "").replace(/\s+/g, " ").trim();
    }

    function headingFor(node) {
      let current = node;
      while (current && current !== lessonBody) {
        if (current.nodeType === 1) {
          for (const heading of current.querySelectorAll("h2")) {
            return normalize(heading.textContent);
          }
        }
        let sibling = current.previousElementSibling || current;
        while (sibling && sibling.previousElementSibling) {
          sibling = sibling.previousElementSibling;
          if (sibling.tagName === "H2") return normalize(sibling.textContent);
        }
        current = current.parentElement;
      }
      return "";
    }

    function paintQuote() {
      if (!pendingQuote) return;
      if (!selection) {
        pendingQuote.hidden = true;
        pendingQuote.textContent = "";
        return;
      }
      pendingQuote.hidden = false;
      pendingQuote.textContent = selection;
      const clear = document.createElement("button");
      clear.type = "button";
      clear.className = "tb-tutor-quote-clear";
      clear.setAttribute("aria-label", "清除引用的正文");
      clear.textContent = "×";
      clear.addEventListener("click", () => {
        selection = "";
        paintQuote();
      });
      pendingQuote.appendChild(clear);
    }

    // Only quotes prose inside the lesson body: a selection that spans the
    // header or the navigation is not a passage the tutor should ground on.
    function captureSelection() {
      if (!lessonBody) return;
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed || !sel.rangeCount) return;
      const text = normalize(sel.toString());
      if (!text) return;
      const anchorNode = sel.getRangeAt(0).commonAncestorContainer;
      const container = anchorNode.nodeType === 1 ? anchorNode : anchorNode.parentElement;
      if (!container || !lessonBody.contains(container)) return;

      selection = text.slice(0, SELECTION_MAX);
      paintQuote();

      const heading = headingFor(container);
      if (heading && anchor) {
        const match = Array.from(anchor.options).find((o) => o.value === heading);
        if (match) anchor.value = heading;
      }
    }

    if (lessonBody) {
      document.addEventListener("mouseup", () => setTimeout(captureSelection, 0));
      document.addEventListener("keyup", (event) => {
        if (event.shiftKey) setTimeout(captureSelection, 0);
      });
    }

    const fab = document.querySelector(".tb-tutor-fab");
    const closeButton = tutor.querySelector(".tb-tutor-close");
    function setOpen(open) {
      tutor.dataset.open = open ? "true" : "false";
      if (fab) fab.setAttribute("aria-expanded", open ? "true" : "false");
      if (open && input) input.focus();
    }
    if (fab) fab.addEventListener("click", () => setOpen(tutor.dataset.open !== "true"));
    if (closeButton) closeButton.addEventListener("click", () => setOpen(false));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && tutor.dataset.open === "true") setOpen(false);
    });

    function appendMessage(role, content, basis, citations, quote) {
      const item = document.createElement("div");
      item.className = "tb-tutor-message";
      item.dataset.role = role;
      const ctx = document.createElement("p");
      ctx.className = "tb-tutor-ctx";
      const focus = anchor ? anchor.value : "";
      ctx.textContent = (role === "user" ? "你" : "助手")
        + " · " + (focus ? "本节「" + focus + "」" : "整节课");
      item.appendChild(ctx);
      if (basis) {
        const badge = document.createElement("span");
        badge.className = "tb-tutor-basis";
        badge.dataset.basis = basis;
        badge.textContent = basisLabels[basis] || basisLabels.general;
        item.appendChild(badge);
      }
      if (quote) {
        const block = document.createElement("blockquote");
        block.className = "tb-tutor-quote";
        block.textContent = quote;
        item.appendChild(block);
      }
      const body = document.createElement("p");
      body.textContent = content;
      item.appendChild(body);
      if (citations && citations.length) {
        const meta = document.createElement("p");
        meta.className = "tb-tutor-citations";
        meta.appendChild(document.createTextNode("依据："));
        citations.forEach((citation, index) => {
          if (index) meta.appendChild(document.createTextNode("、"));
          if (/^https?:\/\//.test(citation)) {
            const link = document.createElement("a");
            link.href = citation;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.textContent = citation;
            meta.appendChild(link);
          } else {
            meta.appendChild(document.createTextNode(citation));
          }
        });
        item.appendChild(meta);
      }
      log.appendChild(item);
    }

    button.addEventListener("click", async () => {
      const question = input.value.trim();
      if (!question) return;
      button.disabled = true;
      error.hidden = true;
      const quoted = selection;
      try {
        const response = await fetch("/api/tutor", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            lesson_id: document.body.dataset.lessonId || "",
            anchor: anchor ? anchor.value : "",
            question,
            web: webToggle ? webToggle.checked : true,
            selection: quoted,
          }),
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.detail ? payload.detail.message : "追问失败");
        }
        appendMessage("user", question, null, [], quoted);
        appendMessage("assistant", payload.answer, payload.basis, payload.citations, quoted);
        if (payload.web_sources && payload.web_sources.length) {
          const sources = document.createElement("ul");
          sources.className = "tb-tutor-web-sources";
          payload.web_sources.forEach((source) => {
            const item = document.createElement("li");
            const link = document.createElement("a");
            link.href = source.url;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.textContent = source.title || source.url;
            item.appendChild(link);
            const trust = document.createElement("span");
            trust.className = "tb-trust";
            trust.textContent = source.trust;
            item.appendChild(trust);
            const kind = document.createElement("span");
            kind.className = "tb-tutor-basis";
            kind.textContent = source.kind;
            item.appendChild(kind);
            sources.appendChild(item);
          });
          log.appendChild(sources);
        }
        if (webToggle && webToggle.checked && payload.web_used === false) {
          const notice = document.createElement("p");
          notice.className = "tb-tutor-citations";
          notice.textContent = "本次未获取到网络结果。";
          log.appendChild(notice);
        }
        if (!payload.saved) {
          const warn = document.createElement("p");
          warn.className = "tb-tutor-citations";
          warn.textContent = "本次回答未保存。";
          log.appendChild(warn);
        }
        input.value = "";
        selection = "";
        paintQuote();
      } catch (err) {
        error.hidden = false;
        error.textContent = "追问失败：" + err.message;
      } finally {
        button.disabled = false;
      }
    });
  }

  wireSession();
})();
