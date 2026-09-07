document.addEventListener("DOMContentLoaded", function () {
  const alertContainer = document.getElementById("alert-container");

  // Step 1 Elements (supports both standard and template variant IDs)
  const forgotForm = document.getElementById("forgot-password-form") || document.getElementById("forgot-form");
  const submitForgotBtn = document.getElementById("submit-forgot-btn") || document.getElementById("btn-request-otp");
  const forgotIdentifierInput = document.getElementById("forgot-identifier");
  const forgotIdentifierLabel = document.getElementById("forgot-identifier-label");
  const forgotChannelInput = document.getElementById("forgot-channel") || document.getElementById("forgot-channel-input");
  const forgotChannelBtns = document.querySelectorAll(".sub-channel-btn, .channel-option-btn");

  // Step 2 Elements
  const forgotStepForm = document.getElementById("forgot-step-form") || document.getElementById("forgot-step-1");
  const forgotStepVerify = document.getElementById("forgot-step-verify") || document.getElementById("forgot-step-2");
  const forgotTargetDisplay = document.getElementById("forgot-target-display") || document.getElementById("masked-recipient");
  const forgotVerifyIdentifier = document.getElementById("forgot-verify-identifier");
  const forgotOtpCodeInput = document.getElementById("forgot-otp-code-input") || document.getElementById("otp-code-input");
  const verifyForgotOtpBtn = document.getElementById("verify-forgot-otp-btn") || document.getElementById("btn-verify-otp");
  const resendForgotOtpBtn = document.getElementById("resend-forgot-otp-btn") || document.getElementById("btn-resend-otp");
  const forgotExpiryTimerText = document.getElementById("forgot-expiry-timer-text") || document.getElementById("otp-countdown");
  const forgotCooldownText = document.getElementById("forgot-cooldown-text");
  const changeForgotDetailsBtn = document.getElementById("change-forgot-details-btn") || document.getElementById("btn-back-to-form");

  let expiryInterval = null;
  let cooldownInterval = null;
  let cooldownRemaining = 0;
  let selectedChannel = "email";
  let activeIdentifier = "";

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

  // Helper: Get OTP Code from 6-digit boxes or hidden/text input
  function getOtpCode() {
    const digitBoxes = document.querySelectorAll("#forgot-step-verify .otp-digit, #forgot-step-2 .otp-digit, .otp-grid .otp-digit");
    if (digitBoxes && digitBoxes.length === 6) {
      let code = "";
      digitBoxes.forEach(box => { code += box.value; });
      if (code.length === 6) return code;
    }
    if (forgotOtpCodeInput) {
      return forgotOtpCodeInput.value.trim();
    }
    return "";
  }

  // Helper: Set OTP Code
  function setOtpCode(code) {
    const digitBoxes = document.querySelectorAll("#forgot-step-verify .otp-digit, #forgot-step-2 .otp-digit, .otp-grid .otp-digit");
    if (digitBoxes && digitBoxes.length === 6) {
      for (let i = 0; i < 6; i++) {
        digitBoxes[i].value = code[i] || "";
      }
    }
    if (forgotOtpCodeInput) {
      forgotOtpCodeInput.value = code;
    }
  }

  // 1. Channel Selector Switching
  function activateForgotChannel(btn) {
    if (!btn) return;
    if (btn.classList.contains("is-disabled") || btn.disabled) return;

    forgotChannelBtns.forEach((b) => {
      b.classList.remove("active");
      b.setAttribute("aria-checked", "false");
      b.setAttribute("tabindex", "-1");
    });
    btn.classList.add("active");
    btn.setAttribute("aria-checked", "true");
    btn.setAttribute("tabindex", "0");
    btn.focus();

    const channel = btn.getAttribute("data-channel");
    if (channel) {
      selectedChannel = channel;
      if (forgotChannelInput) forgotChannelInput.value = channel;

      if (channel === "email") {
        if (forgotIdentifierLabel) forgotIdentifierLabel.textContent = "Email Address";
        if (forgotIdentifierInput) forgotIdentifierInput.placeholder = "name@company.com";
      } else if (channel === "sms") {
        if (forgotIdentifierLabel) forgotIdentifierLabel.textContent = "Mobile Number";
        if (forgotIdentifierInput) forgotIdentifierInput.placeholder = "+91 9876543210 (with country code)";
      } else if (channel === "whatsapp") {
        if (forgotIdentifierLabel) forgotIdentifierLabel.textContent = "WhatsApp Mobile Number";
        if (forgotIdentifierInput) forgotIdentifierInput.placeholder = "+91 9876543210 (with country code)";
      }
    }
  }

  forgotChannelBtns.forEach((btn, index) => {
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      activateForgotChannel(this);
    });

    btn.addEventListener("keydown", function (e) {
      let newIndex = -1;
      const total = forgotChannelBtns.length;
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
        activateForgotChannel(forgotChannelBtns[newIndex]);
      }
    });
  });

  // 2. Timers
  function startExpiryTimer(seconds) {
    clearInterval(expiryInterval);
    let remaining = seconds;
    function update() {
      const m = Math.floor(remaining / 60);
      const s = remaining % 60;
      const timeStr = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
      if (forgotExpiryTimerText) {
        if (forgotExpiryTimerText.id === "otp-countdown") {
          forgotExpiryTimerText.textContent = timeStr;
        } else {
          forgotExpiryTimerText.textContent = `Expires in: ${timeStr}`;
        }
      }
      if (remaining <= 0) {
        clearInterval(expiryInterval);
        if (forgotExpiryTimerText) {
          forgotExpiryTimerText.textContent = "Code expired. Please request a new one.";
        }
      }
      remaining--;
    }
    update();
    expiryInterval = setInterval(update, 1000);
  }

  function startCooldownTimer(seconds) {
    clearInterval(cooldownInterval);
    cooldownRemaining = seconds;
    if (resendForgotOtpBtn) resendForgotOtpBtn.disabled = true;

    function update() {
      if (forgotCooldownText) {
        forgotCooldownText.textContent = `(${cooldownRemaining}s)`;
      } else if (resendForgotOtpBtn) {
        resendForgotOtpBtn.textContent = `Resend Code (${cooldownRemaining}s)`;
      }

      if (cooldownRemaining <= 0) {
        clearInterval(cooldownInterval);
        if (resendForgotOtpBtn) {
          resendForgotOtpBtn.disabled = false;
          if (!forgotCooldownText) {
            resendForgotOtpBtn.textContent = "Resend Code";
          }
        }
        if (forgotCooldownText) {
          forgotCooldownText.textContent = "";
        }
      }
      cooldownRemaining--;
    }
    update();
    cooldownInterval = setInterval(update, 1000);
  }

  // 3. Step 1: Request Reset OTP (AJAX)
  if (forgotForm) {
    forgotForm.addEventListener("submit", async function (e) {
      e.preventDefault();
      clearAlerts();

      const ident = forgotIdentifierInput ? forgotIdentifierInput.value.trim() : "";
      if (!ident) {
        showAlert("Please enter your email or mobile number.", "error");
        return;
      }
      activeIdentifier = ident;

      if (submitForgotBtn) {
        submitForgotBtn.classList.add("is-loading");
        submitForgotBtn.disabled = true;
      }

      try {
        const response = await fetch("/api/forgot-password/otp/request/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify({
            identifier: ident,
            channel: selectedChannel,
          }),
        });

        const data = await response.json();

        if (response.ok && data.success) {
          if (forgotTargetDisplay && data.masked_identifier) {
            forgotTargetDisplay.textContent = data.masked_identifier;
          }
          if (forgotVerifyIdentifier) {
            forgotVerifyIdentifier.value = data.identifier || ident;
          }

          if (forgotStepForm) {
            forgotStepForm.style.display = "none";
            forgotStepForm.classList.remove("active");
          }
          if (forgotStepVerify) {
            forgotStepVerify.style.display = "block";
            forgotStepVerify.classList.add("active");
          }

          const firstOtpInput = document.querySelector("#forgot-step-verify .otp-digit, #forgot-step-2 .otp-digit") || forgotOtpCodeInput;
          if (firstOtpInput) firstOtpInput.focus();

          showAlert(data.message, "success");
          startExpiryTimer(data.expires_in || 300);
          startCooldownTimer(data.cooldown || 60);
        } else {
          showAlert(data.message || "Unable to send verification code. Please try again.", "error");
        }
      } catch (err) {
        showAlert("Network error. Please try again.", "error");
      } finally {
        if (submitForgotBtn) {
          submitForgotBtn.classList.remove("is-loading");
          submitForgotBtn.disabled = false;
        }
      }
    });
  }

  // 4. Step 2: Verify Reset OTP (AJAX)
  if (verifyForgotOtpBtn) {
    verifyForgotOtpBtn.addEventListener("click", async function (e) {
      e.preventDefault();
      const code = getOtpCode();
      const ident = (forgotVerifyIdentifier && forgotVerifyIdentifier.value.trim()) || activeIdentifier;

      if (!code || code.length !== 6) {
        showAlert("Please enter the complete 6-digit verification code.", "error");
        const firstOtpInput = document.querySelector("#forgot-step-verify .otp-digit, #forgot-step-2 .otp-digit") || forgotOtpCodeInput;
        if (firstOtpInput) firstOtpInput.focus();
        return;
      }

      verifyForgotOtpBtn.classList.add("is-loading");
      verifyForgotOtpBtn.disabled = true;
      clearAlerts();

      try {
        const response = await fetch("/api/forgot-password/otp/verify/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify({
            identifier: ident,
            otp_code: code,
          }),
        });

        const data = await response.json();

        if (response.ok && data.success) {
          showAlert(data.message, "success");
          setTimeout(() => {
            window.location.href = data.redirect_url || "/reset-password/";
          }, 500);
        } else {
          showAlert(data.message || "Invalid or expired verification code.", "error");
          const firstOtpInput = document.querySelector("#forgot-step-verify .otp-digit, #forgot-step-2 .otp-digit") || forgotOtpCodeInput;
          if (firstOtpInput) firstOtpInput.focus();
          verifyForgotOtpBtn.disabled = false;
        }
      } catch (err) {
        showAlert("Network communication error. Please try again.", "error");
        verifyForgotOtpBtn.disabled = false;
      } finally {
        verifyForgotOtpBtn.classList.remove("is-loading");
      }
    });
  }

  // 5. Step 2: Resend Reset OTP
  if (resendForgotOtpBtn) {
    resendForgotOtpBtn.addEventListener("click", async function (e) {
      e.preventDefault();
      if (cooldownRemaining > 0) return;

      const ident = (forgotVerifyIdentifier && forgotVerifyIdentifier.value.trim()) || activeIdentifier;
      resendForgotOtpBtn.disabled = true;
      clearAlerts();

      try {
        const response = await fetch("/api/forgot-password/otp/resend/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify({
            identifier: ident,
            channel: selectedChannel,
          }),
        });

        const data = await response.json();

        if (response.ok && data.success) {
          if (forgotTargetDisplay && data.masked_identifier) {
            forgotTargetDisplay.textContent = data.masked_identifier;
          }
          showAlert(data.message, "success");
          startExpiryTimer(data.expires_in || 300);
          startCooldownTimer(data.cooldown || 60);
        } else {
          showAlert(data.message || "Unable to resend code right now.", "error");
          resendForgotOtpBtn.disabled = false;
        }
      } catch (err) {
        showAlert("Network error. Please try again.", "error");
        resendForgotOtpBtn.disabled = false;
      }
    });
  }

  // 6. Change Details / Return to Step 1
  if (changeForgotDetailsBtn) {
    changeForgotDetailsBtn.addEventListener("click", function (e) {
      e.preventDefault();
      clearInterval(expiryInterval);
      clearInterval(cooldownInterval);
      if (forgotStepVerify) {
        forgotStepVerify.style.display = "none";
        forgotStepVerify.classList.remove("active");
      }
      if (forgotStepForm) {
        forgotStepForm.style.display = "block";
        forgotStepForm.classList.add("active");
      }
      clearAlerts();
    });
  }

  // 7. Single numeric input fallback
  if (forgotOtpCodeInput) {
    forgotOtpCodeInput.addEventListener("input", function () {
      this.value = this.value.replace(/[^0-9]/g, "").slice(0, 6);
      if (this.value.length === 6 && verifyForgotOtpBtn) {
        verifyForgotOtpBtn.click();
      }
    });
  }
});
