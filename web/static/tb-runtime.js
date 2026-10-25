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
        path: form.querySelector('input[name="path"]').value,
        notes: form.querySelector('textarea[name="notes"]').value,
        checked: Array.from(form.querySelectorAll('input[name="checked"]:checked')).map((el) => el.value),
      };
    }
    return null;
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
      button.disabled = true;
      try {
        const res = await fetch("/api/evidence", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            lesson_id: lessonId,
            exercise_id: form.dataset.exerciseId,
            response,
            hints_used: hintsUsed,
            duration_ms: Date.now() - startedAt,
          }),
        });
        if (!res.ok) throw new Error(await res.text());
        const payload = await res.json();
        feedback.hidden = false;
        feedback.dataset.outcome = payload.grade.outcome;
        feedback.textContent = payload.grade.feedback;
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

    const basisLabels = {
      lesson: "本课内容",
      resource: "包内资源",
      general: "通用知识",
    };

    function appendMessage(role, content, basis, citations) {
      const item = document.createElement("div");
      item.className = "tb-tutor-message";
      item.dataset.role = role;
      if (basis) {
        const badge = document.createElement("span");
        badge.className = "tb-tutor-basis";
        badge.dataset.basis = basis;
        badge.textContent = basisLabels[basis] || basisLabels.general;
        item.appendChild(badge);
      }
      const body = document.createElement("p");
      body.textContent = content;
      item.appendChild(body);
      if (citations && citations.length) {
        const meta = document.createElement("p");
        meta.className = "tb-tutor-citations";
        meta.textContent = "依据：" + citations.join("、");
        item.appendChild(meta);
      }
      log.appendChild(item);
    }

    button.addEventListener("click", async () => {
      const question = input.value.trim();
      if (!question) return;
      button.disabled = true;
      error.hidden = true;
      try {
        const response = await fetch("/api/tutor", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            lesson_id: document.body.dataset.lessonId || "",
            anchor: anchor ? anchor.value : "",
            question,
          }),
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.detail ? payload.detail.message : "追问失败");
        }
        appendMessage("user", question, null, []);
        appendMessage("assistant", payload.answer, payload.basis, payload.citations);
        if (!payload.saved) {
          const warn = document.createElement("p");
          warn.className = "tb-tutor-citations";
          warn.textContent = "本次回答未保存。";
          log.appendChild(warn);
        }
        input.value = "";
      } catch (err) {
        error.hidden = false;
        error.textContent = "追问失败：" + err.message;
      } finally {
        button.disabled = false;
      }
    });
  }
})();
