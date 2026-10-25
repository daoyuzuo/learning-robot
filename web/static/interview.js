(() => {
  const root = document.querySelector("[data-interview-session]");
  if (!root) return;
  const sessionId = root.dataset.interviewSession;
  const questionId = root.dataset.questionId;
  const textarea = root.querySelector("#tb-interview-answer");
  const errorBox = root.querySelector(".tb-interview-error[hidden]");
  const saveStatus = root.querySelector(".tb-interview-save");
  let timer = null;
  let started = Date.now();

  function showError(message) {
    if (!errorBox) return;
    errorBox.textContent = message;
    errorBox.hidden = false;
  }

  async function post(path, body) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || "请求失败");
    }
    return data;
  }

  async function saveDraft() {
    if (!textarea || textarea.readOnly) return;
    try {
      await fetch(`/api/interview/session/${sessionId}/answer`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question_id: questionId, answer: textarea.value }),
      });
      if (saveStatus) saveStatus.textContent = "已保存";
    } catch (error) {
      showError("保存失败，请稍后重试");
    }
  }

  if (textarea && !textarea.readOnly) {
    textarea.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(saveDraft, 1000);
    });
    textarea.addEventListener("blur", saveDraft);
  }

  root.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;
    const action = button.dataset.action;
    button.disabled = true;
    try {
      if (action === "grade") {
        await saveDraft();
        await post(`/api/interview/session/${sessionId}/grade`, {
          question_id: questionId,
        });
        location.reload();
      } else if (action === "reset") {
        await post(`/api/interview/session/${sessionId}/reset`, {
          question_id: questionId,
        });
        location.reload();
      } else if (action === "abandon") {
        if (!confirm("放弃本次模拟？已确认的成绩会保留。")) return;
        await post(`/api/interview/session/${sessionId}/abandon`, {});
        location.href = "/interview";
      } else if (action === "confirm") {
        const scores = [...root.querySelectorAll("input[data-dimension]")].map(
          (input) => ({
            dimension: input.dataset.dimension,
            score: Number(input.value),
          })
        );
        await post(`/api/interview/session/${sessionId}/confirm`, {
          question_id: questionId,
          scores,
          duration_ms: Date.now() - started,
        });
        location.reload();
      }
    } catch (error) {
      showError(error.message);
    } finally {
      button.disabled = false;
    }
  });
})();
