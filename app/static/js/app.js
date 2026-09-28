document.addEventListener("click", (event) => {
  const toggle = event.target.closest(".why-toggle");
  if (toggle) {
    const details = toggle.parentElement.querySelector(".why-details");
    if (details) details.classList.toggle("open");
  }

  const fbBtn = event.target.closest(".fb-btn");
  if (fbBtn) {
    const row = fbBtn.closest(".feedback-row");
    const profileId = Number(row.dataset.profileId);
    const articleId = Number(row.dataset.articleId);
    const action = fbBtn.dataset.action;

    fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id: profileId, article_id: articleId, action }),
    })
      .then((r) => r.json())
      .then(() => {
        row.querySelectorAll(".fb-btn").forEach((b) => b.classList.remove("selected", "like", "dislike"));
        fbBtn.classList.add("selected", action === "like" ? "like" : "dislike");
        const status = row.querySelector(".fb-status");
        if (status) status.textContent = action === "like" ? "Отмечено: релевантно" : "Отмечено: нерелевантно";
      })
      .catch(() => {
        const status = row.querySelector(".fb-status");
        if (status) status.textContent = "Ошибка сохранения отзыва";
      });
  }
});
