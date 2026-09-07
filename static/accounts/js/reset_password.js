document.addEventListener("DOMContentLoaded", function () {
  const alertContainer = document.getElementById("alert-container");
  const resetForm = document.getElementById("reset-password-form");
  const submitResetBtn = document.getElementById("submit-reset-btn") || document.getElementById("btn-submit-reset");
  const passwordInput = document.getElementById("reset-password") || document.getElementById("new-password");
  const confirmPasswordInput = document.getElementById("reset-confirm-password") || document.getElementById("confirm-password");
  const strengthBar = document.getElementById("password-strength-bar") || document.getElementById("strength-meter-fill");
  const strengthText = document.getElementById("password-strength-text") || document.getElementById("strength-meter-label");

  // Helper: Get CSRF Token
  function getCsrfToken() {
    const el = document.querySelector("[name=csrfmiddlewaretoken]");
    return el ? el.value : "";
  }

  // Helper: Show Alert
  function showAlert(message, type) {
    if (!alertContainer) return;
    alertContainer.innerHTML = `
      <div class="alert-box alert-${type === 'error' ? 'error' : 'success'}" role="alert">
        <span>${message}</span>
      </div>
    `;
    alertContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function clearAlerts() {
    if (alertContainer) alertContainer.innerHTML = "";
  }

  // 1. Live Password Strength Calculation
  function calculatePasswordStrength(pass) {
    if (!pass) return { score: 0, label: "None", color: "transparent" };
    let score = 0;
    if (pass.length >= 8) score += 1;
    if (pass.length >= 12) score += 1;
    if (/[a-z]/.test(pass) && /[A-Z]/.test(pass)) score += 1;
    if (/\d/.test(pass)) score += 1;
    if (/[^a-zA-Z0-9]/.test(pass)) score += 1;

    if (score <= 1) return { score: 20, label: "Very Weak", color: "var(--error, #ef4444)" };
    if (score === 2) return { score: 40, label: "Weak", color: "#f97316" };
    if (score === 3) return { score: 65, label: "Medium", color: "#eab308" };
    if (score === 4) return { score: 85, label: "Strong", color: "#3b82f6" };
    return { score: 100, label: "Very Strong", color: "var(--success, #10b981)" };
  }

  if (passwordInput && (strengthBar || strengthText)) {
    passwordInput.addEventListener("input", function () {
      const val = this.value;
      const res = calculatePasswordStrength(val);
      if (strengthBar) {
        strengthBar.style.width = `${res.score}%`;
        strengthBar.style.backgroundColor = res.color;
      }
      if (strengthText) {
        strengthText.textContent = res.label;
        strengthText.style.color = res.color === "transparent" ? "var(--text-muted, #94a3b8)" : res.color;
      }
    });
  }

  // 2. Form Submission (AJAX)
  if (resetForm) {
    resetForm.addEventListener("submit", async function (e) {
      e.preventDefault();
      clearAlerts();

      const pass = passwordInput ? passwordInput.value : "";
      const confirmPass = confirmPasswordInput ? confirmPasswordInput.value : "";

      if (!pass || pass.length < 8) {
        showAlert("Password must be at least 8 characters long.", "error");
        if (passwordInput) passwordInput.focus();
        return;
      }

      if (pass !== confirmPass) {
        showAlert("Passwords do not match. Please verify and re-enter.", "error");
        if (confirmPasswordInput) confirmPasswordInput.focus();
        return;
      }

      if (submitResetBtn) {
        submitResetBtn.classList.add("is-loading");
        submitResetBtn.disabled = true;
      }

      try {
        const response = await fetch("/api/reset-password/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify({
            password: pass,
            confirm_password: confirmPass,
          }),
        });

        const data = await response.json();

        if (response.ok && data.success) {
          showAlert(data.message, "success");
          setTimeout(() => {
            window.location.href = data.redirect_url || "/login/";
          }, 800);
        } else {
          showAlert(data.message || "Failed to reset password. Please try again.", "error");
          if (submitResetBtn) {
            submitResetBtn.classList.remove("is-loading");
            submitResetBtn.disabled = false;
          }
        }
      } catch (err) {
        showAlert("Network error during password reset. Please try again.", "error");
        if (submitResetBtn) {
          submitResetBtn.classList.remove("is-loading");
          submitResetBtn.disabled = false;
        }
      }
    });
  }
});
