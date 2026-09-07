/**
 * Authentication Platform - Interactive Registration Controller
 * Handles live password strength metering, password matching,
 * AJAX registration step transitions, and 6-digit OTP verification.
 * Fully compatible across all visual templates (Modern Glass, Split Screen, Minimal Corporate).
 */

document.addEventListener("DOMContentLoaded", function () {
  // 1. Form & Container Elements (supporting both template naming conventions)
  const regForm =
    document.getElementById("registration-form") ||
    document.getElementById("register-form") ||
    document.querySelector("form[action*='register']");

  const regStepForm =
    document.getElementById("register-step-1") ||
    document.getElementById("reg-step-form");

  const regStepVerify =
    document.getElementById("register-step-2") ||
    document.getElementById("reg-step-verify");

  // 2. Input Fields
  const fullNameInput =
    document.getElementById("reg-fullname") ||
    document.getElementById("reg-full-name") ||
    document.querySelector("input[name='full_name']");

  const emailInput =
    document.getElementById("reg-email") ||
    document.querySelector("input[name='email']");

  const mobileInput =
    document.getElementById("reg-mobile") ||
    document.querySelector("input[name='mobile']");

  const passwordInput =
    document.getElementById("reg-password") ||
    document.querySelector("input[name='password']");

  const confirmPasswordInput =
    document.getElementById("reg-password-confirm") ||
    document.getElementById("reg-confirm-password") ||
    document.querySelector("input[name='confirm_password']");

  const submitRegBtn =
    document.getElementById("btn-register-submit") ||
    document.getElementById("submit-reg-btn") ||
    (regForm ? regForm.querySelector("button[type='submit']") : null);

  // 3. Password Strength Meter
  const strengthBar =
    document.getElementById("strength-meter-bar") ||
    document.getElementById("password-strength-bar");

  const strengthText =
    document.getElementById("strength-text") ||
    document.getElementById("password-strength-text");

  // 4. Step 2 OTP Elements
  const regTargetDisplay =
    document.getElementById("masked-recipient") ||
    document.getElementById("reg-target-display") ||
    document.getElementById("reg-email-display");

  const verifyRegOtpBtn =
    document.getElementById("btn-verify-otp") ||
    document.getElementById("verify-reg-otp-btn");

  const resendRegOtpBtn =
    document.getElementById("btn-resend-otp") ||
    document.getElementById("resend-reg-otp-btn");

  const regCountdownEl =
    document.getElementById("otp-countdown") ||
    document.getElementById("reg-otp-countdown");

  const changeRegDetailsBtn =
    document.getElementById("btn-back-to-form") ||
    document.getElementById("change-reg-details-btn");

  const alertContainer =
    document.getElementById("reg-alert-container") ||
    document.getElementById("alert-container");

  // 5. Channel Selector
  const regChannelBtns = document.querySelectorAll(".sub-channel-btn");
  const regChannelInput =
    document.getElementById("reg-channel-input") ||
    document.getElementById("reg-channel") ||
    document.querySelector("input[name='channel']");

  let currentRegChannel = (regChannelInput && regChannelInput.value) || "email";

  if (regChannelBtns.length > 0) {
    function activateRegChannel(btn) {
      if (!btn) return;
      if (btn.classList.contains("is-disabled") || btn.disabled) {
        const channelLabel = btn.querySelector("span")?.textContent.trim() || "This channel";
        showAlert(`${channelLabel} is currently unavailable. Provider credentials must be configured in .env.`, "error");
        return;
      }

      regChannelBtns.forEach((b) => {
        b.classList.remove("active");
        b.setAttribute("aria-checked", "false");
        b.setAttribute("tabindex", "-1");
      });
      btn.classList.add("active");
      btn.setAttribute("aria-checked", "true");
      btn.setAttribute("tabindex", "0");
      btn.focus();

      const ch = btn.dataset.channel || "email";
      if (regChannelInput) regChannelInput.value = ch;
      currentRegChannel = ch;
      clearAlerts();

      if (mobileInput) {
        if (ch === "sms" || ch === "whatsapp") {
          mobileInput.required = true;
          mobileInput.placeholder = "e.g. +91 9876543210 (required)";
        } else {
          mobileInput.required = false;
          mobileInput.placeholder = "e.g. +91 9876543210 (optional)";
        }
      }
    }

    regChannelBtns.forEach(function (btn, index) {
      btn.addEventListener("click", function () {
        activateRegChannel(btn);
      });

      btn.addEventListener("keydown", function (e) {
        let newIndex = -1;
        const total = regChannelBtns.length;
        if (e.key === "ArrowRight" || e.key === "ArrowDown") {
          e.preventDefault();
          newIndex = (index + 1) % total;
        } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
          e.preventDefault();
          newIndex = (index - 1 + total) % total;
        } else if (e.key === "Home") {
          e.preventDefault();
          newIndex = 0;
        } else if (e.key === "End") {
          e.preventDefault();
          newIndex = total - 1;
        }

        if (newIndex !== -1) {
          activateRegChannel(regChannelBtns[newIndex]);
        }
      });
    });
  }

  let expiryInterval = null;
  let cooldownInterval = null;
  let cooldownRemaining = 0;

  function getCsrfToken() {
    return (
      document.cookie
        .split("; ")
        .find((row) => row.startsWith("csrftoken="))
        ?.split("=")[1] ||
      document.querySelector("[name=csrfmiddlewaretoken]")?.value ||
      ""
    );
  }

  function showAlert(message, type = "error") {
    if (!alertContainer) return;
    alertContainer.innerHTML = `
      <div class="alert-box alert-${type === 'error' ? 'error' : 'success'}" role="alert">
        <span>${message}</span>
      </div>
    `;
  }

  function clearAlerts() {
    if (alertContainer) alertContainer.innerHTML = "";
  }

  // -------------------------------------------------------------
  // Password Strength Meter Logic
  // -------------------------------------------------------------
  function evaluatePasswordStrength(pass) {
    if (!pass) return { score: 0, label: "None", color: "#e2e8f0", width: "0%" };
    let score = 0;
    if (pass.length >= 8) score += 1;
    if (pass.length >= 12) score += 1;
    if (/[A-Z]/.test(pass) && /[a-z]/.test(pass)) score += 1;
    if (/[0-9]/.test(pass)) score += 1;
    if (/[^A-Za-z0-9]/.test(pass)) score += 1;

    if (score <= 2) return { score: 1, label: "Weak", color: "#ef4444", width: "33%" };
    if (score <= 3) return { score: 2, label: "Medium", color: "#f59e0b", width: "66%" };
    return { score: 3, label: "Strong", color: "#10b981", width: "100%" };
  }

  if (passwordInput && (strengthBar || strengthText)) {
    passwordInput.addEventListener("input", function () {
      const evaluation = evaluatePasswordStrength(this.value);
      if (strengthBar) {
        strengthBar.style.width = evaluation.width;
        strengthBar.style.backgroundColor = evaluation.color;
      }
      if (strengthText) {
        strengthText.textContent = evaluation.label;
        strengthText.style.color = evaluation.color;
      }
    });
  }

  // -------------------------------------------------------------
  // Timer Helpers
  // -------------------------------------------------------------
  function startExpiryTimer(totalSeconds = 300) {
    clearInterval(expiryInterval);
    let seconds = totalSeconds;
    function update() {
      if (!regCountdownEl) return;
      const mins = Math.floor(seconds / 60);
      const secs = seconds % 60;
      regCountdownEl.textContent = `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
      if (seconds <= 0) {
        clearInterval(expiryInterval);
        regCountdownEl.textContent = "00:00 (Expired)";
        showAlert("Registration verification code has expired. Please resend code.", "error");
      }
      seconds--;
    }
    update();
    expiryInterval = setInterval(update, 1000);
  }

  function startCooldownTimer(seconds = 60) {
    clearInterval(cooldownInterval);
    cooldownRemaining = seconds;
    if (resendRegOtpBtn) resendRegOtpBtn.disabled = true;
    function update() {
      if (!resendRegOtpBtn) return;
      if (cooldownRemaining <= 0) {
        clearInterval(cooldownInterval);
        resendRegOtpBtn.disabled = false;
        resendRegOtpBtn.textContent = "Resend Code";
      } else {
        resendRegOtpBtn.textContent = `Resend in ${cooldownRemaining}s`;
        cooldownRemaining--;
      }
    }
    update();
    cooldownInterval = setInterval(update, 1000);
  }

  // -------------------------------------------------------------
  // Helper: Read 6-digit OTP code from inputs
  // -------------------------------------------------------------
  function getEnteredOtp() {
    // 1. Try 6 individual boxes
    const digitInputs = document.querySelectorAll(
      "#register-step-2 .otp-digit, #reg-step-verify .otp-digit, .otp-digit"
    );
    if (digitInputs.length >= 6) {
      const code = Array.from(digitInputs).map((d) => d.value.trim()).join("");
      if (code.length === 6) return code;
    }

    // 2. Try hidden aggregate field
    const hidden = document.getElementById("otp-code-hidden");
    if (hidden && hidden.value.trim().length === 6) return hidden.value.trim();

    // 3. Try single OTP input
    const single =
      document.getElementById("reg-otp-code-input") ||
      document.getElementById("otp-verify-code");
    if (single && single.value.trim()) return single.value.trim();

    // 4. Return whatever digits were entered
    return Array.from(digitInputs).map((d) => d.value.trim()).join("");
  }

  // -------------------------------------------------------------
  // Step 1: Submit Registration Form (AJAX)
  // -------------------------------------------------------------
  if (regForm) {
    regForm.addEventListener("submit", async function (e) {
      e.preventDefault();
      clearAlerts();

      const fullName = fullNameInput ? fullNameInput.value.trim() : "";
      const email = emailInput ? emailInput.value.trim() : "";
      const mobileVal = mobileInput ? mobileInput.value.trim() : "";
      const pass = passwordInput ? passwordInput.value : "";
      const confirmPass = confirmPasswordInput ? confirmPasswordInput.value : "";
      const selectedChannel = (regChannelInput && regChannelInput.value) || currentRegChannel;

      if (!fullName) {
        showAlert("Please enter your full name.", "error");
        if (fullNameInput) fullNameInput.focus();
        return;
      }

      if (!email) {
        showAlert("Please enter your email address.", "error");
        if (emailInput) emailInput.focus();
        return;
      }

      if (!pass) {
        showAlert("Please create a password.", "error");
        if (passwordInput) passwordInput.focus();
        return;
      }

      if (pass !== confirmPass) {
        showAlert("Passwords do not match. Please verify and re-enter.", "error");
        if (confirmPasswordInput) confirmPasswordInput.focus();
        return;
      }

      if ((selectedChannel === "sms" || selectedChannel === "whatsapp") && !mobileVal) {
        showAlert(`Mobile number is required when selecting ${selectedChannel.toUpperCase()} verification.`, "error");
        if (mobileInput) mobileInput.focus();
        return;
      }

      if (submitRegBtn) {
        submitRegBtn.classList.add("is-loading");
        submitRegBtn.disabled = true;
      }

      const payload = {
        full_name: fullName,
        email: email,
        mobile: mobileVal,
        channel: selectedChannel,
        password: pass,
        confirm_password: confirmPass,
      };

      try {
        const response = await fetch("/register/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
            "X-Requested-With": "XMLHttpRequest",
          },
          body: JSON.stringify(payload),
        });

        const data = await response.json();

        if (response.ok && data.success) {
          // Transition to Step 2
          if (regStepForm) regStepForm.style.display = "none";
          if (regStepVerify) regStepVerify.style.display = "block";

          if (regTargetDisplay) {
            regTargetDisplay.textContent = data.masked_identifier || data.otp_identifier || data.email || email;
          }
          currentRegChannel = data.channel || selectedChannel;

          // Clear any OTP inputs
          document.querySelectorAll(".otp-digit").forEach((d) => (d.value = ""));
          const hiddenOtp = document.getElementById("otp-code-hidden");
          if (hiddenOtp) hiddenOtp.value = "";
          const firstDigit = document.querySelector(".otp-digit");
          if (firstDigit) firstDigit.focus();

          showAlert(data.message, "success");
          startExpiryTimer(data.expires_in || 300);
          startCooldownTimer(data.cooldown || 60);
        } else {
          showAlert(data.message || "Please correct the errors in the form.", "error");
        }
      } catch (err) {
        showAlert("Network communication error. Please try again.", "error");
      } finally {
        if (submitRegBtn) {
          submitRegBtn.classList.remove("is-loading");
          submitRegBtn.disabled = false;
        }
      }
    });
  }

  // -------------------------------------------------------------
  // Step 2: Verify Registration OTP (AJAX)
  // -------------------------------------------------------------
  if (verifyRegOtpBtn) {
    verifyRegOtpBtn.addEventListener("click", async function (e) {
      e.preventDefault();
      const code = getEnteredOtp();

      if (!code || code.length !== 6) {
        showAlert("Please enter the complete 6-digit verification code.", "error");
        const emptyDigit = Array.from(document.querySelectorAll(".otp-digit")).find((d) => !d.value);
        if (emptyDigit) emptyDigit.focus();
        return;
      }

      verifyRegOtpBtn.classList.add("is-loading");
      verifyRegOtpBtn.disabled = true;
      clearAlerts();

      try {
        const response = await fetch("/api/register/otp/verify/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify({ otp_code: code }),
        });

        const data = await response.json();

        if (response.ok && data.success) {
          showAlert(data.message, "success");
          setTimeout(() => {
            window.location.href = data.redirect_url || "/dashboard/";
          }, 600);
        } else {
          showAlert(data.message || "Invalid or expired verification code.", "error");
          verifyRegOtpBtn.disabled = false;
        }
      } catch (err) {
        showAlert("Network error during verification. Please try again.", "error");
        verifyRegOtpBtn.disabled = false;
      } finally {
        verifyRegOtpBtn.classList.remove("is-loading");
      }
    });
  }

  // -------------------------------------------------------------
  // Step 2: Resend Registration OTP (Channel-Aware)
  // -------------------------------------------------------------
  if (resendRegOtpBtn) {
    resendRegOtpBtn.addEventListener("click", async function (e) {
      e.preventDefault();
      if (cooldownRemaining > 0) return;

      resendRegOtpBtn.disabled = true;
      clearAlerts();

      try {
        const response = await fetch("/api/register/otp/resend/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
        });
        const data = await response.json();
        if (response.ok && data.success) {
          if (regTargetDisplay && data.masked_identifier) {
            regTargetDisplay.textContent = data.masked_identifier;
          }
          showAlert(data.message, "success");
          startExpiryTimer(data.expires_in || 300);
          startCooldownTimer(data.cooldown || 60);
        } else {
          showAlert(data.message || "Unable to resend code.", "error");
          resendRegOtpBtn.disabled = false;
        }
      } catch (err) {
        showAlert("Network error. Please try again.", "error");
        resendRegOtpBtn.disabled = false;
      }
    });
  }

  // -------------------------------------------------------------
  // Step 2: Back to Registration Form
  // -------------------------------------------------------------
  if (changeRegDetailsBtn) {
    changeRegDetailsBtn.addEventListener("click", function (e) {
      e.preventDefault();
      clearInterval(expiryInterval);
      clearInterval(cooldownInterval);
      if (regStepVerify) regStepVerify.style.display = "none";
      if (regStepForm) regStepForm.style.display = "block";
      clearAlerts();
    });
  }
});
