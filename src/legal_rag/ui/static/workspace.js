document.querySelectorAll("form[data-submit-state]").forEach((form) => {
  const question = form.querySelector("textarea[name='question']");
  const count = form.querySelector("[data-character-count]");
  const updateCount = () => {
    if (question && count) count.textContent = question.value.length;
  };

  question?.addEventListener("input", updateCount);
  question?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  updateCount();

  form.addEventListener("submit", () => {
    const button = form.querySelector("button[type='submit']");
    if (!button || button.disabled) return;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    button.textContent = button.dataset.loadingLabel || "Working";
  });
});

const analysisResult = document.querySelector("[data-analysis-result]");
analysisResult?.querySelector("h2")?.focus({ preventScroll: true });
