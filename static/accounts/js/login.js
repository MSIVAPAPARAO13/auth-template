/**
 * Authentication Platform - Interactive Login Controller
 * Handles Mode toggling (Password vs OTP), Show/Hide password,
 * and complete OTP AJAX lifecycle across all visual templates.
 */

document.addEventListener("DOMContentLoaded", function () {
  // 1. Elements - Mode & Tabs
  const modePasswordBtn = document.getElementById("mode-password-btn");
  const modeOtpBtn = document.getElementById("mode-otp-btn");
  const passwordSection = document.getElementById("password-login-section");
  const otpSection = document.getElementById("otp-login-section");

  // 2. Elements - OTP Sub-channels (Email, SMS, WhatsApp)
  const subChannelBtns = document.querySelectorAll(".sub-channel-btn");
  const otpChannelInput =
    document.getElementById("otp-channel-input") ||
    document.getElementById("otp-channel") ||
    document.querySelector("input[name='channel']");

  const otpIdentifierInput =
    document.getElementById("otp-request-identifier") ||
    document.getElementById("otp-identifier") ||
    document.querySelector("input[name='identifier']");

  const otpIdentifierLabel = document.getElementById("otp-identifier-label");

  // 3. Elements - OTP Steps
  const otpStepRequest =
    document.getElementById("otp-step-1") ||
    document.getElementById("otp-step-request");

  const otpStepVerify =
    document.getElementById("otp-step-2") ||
    document.getElementById("otp-step-verify");

  const otpTargetDisplay =
    document.getElementById("otp-target-display") ||
    document.getElementById("masked-recipient");

  const verifyIdentifierInput =
    document.getElementById("otp-verify-identifier") ||
    document.getElementById("verify-identifier");

  const changeIdentifierBtn =
    document.getElementById("otp-change-identifier-btn") ||
    document.getElementById("change-identifier-btn");

  // 4. Elements - Buttons & Alerts
  const sendOtpBtn =
    document.getElementById("send-otp-btn") ||
    document.getElementById("btn-send-otp");

  const verifyOtpBtn =
    document.getElementById("verify-otp-btn") ||
    document.getElementById("btn-verify-otp");

  const resendOtpBtn =
    document.getElementById("resend-otp-btn") ||
    document.getElementById("btn-resend-otp");

  const otpCountdownEl =
    document.getElementById("otp-countdown-val") ||
    document.getElementById("otp-countdown");

  const alertContainer = document.getElementById("alert-container");

  // 5. State Variables
  let expiryInterval = null;
  let cooldownInterval = null;
  let cooldownSecondsRemaining = 0;
  let currentActiveChannel = (otpChannelInput && otpChannelInput.value) || "email";

  // CSRF Helper
  function getCsrfToken() {
    const cookieValue = document.cookie
      .split("; ")
      .find((row) => row.startsWith("csrftoken="))
      ?.split("=")[1];
    return cookieValue || document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
  }

  // Notification Banner Helper
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

  // 1. Mode Switching: Password vs OTP
  if (modePasswordBtn && modeOtpBtn) {
    modePasswordBtn.addEventListener("click", function () {
      modePasswordBtn.classList.add("active");
      modeOtpBtn.classList.remove("active");
      if (passwordSection) {
        passwordSection.style.display = "block";
        passwordSection.classList.add("active");
      }
      if (otpSection) {
        otpSection.style.display = "none";
        otpSection.classList.remove("active");
      }
      clearAlerts();
    });

    modeOtpBtn.addEventListener("click", function () {
      modeOtpBtn.classList.add("active");
      modePasswordBtn.classList.remove("active");
      if (otpSection) {
        otpSection.style.display = "block";
        otpSection.classList.add("active");
      }
      if (passwordSection) {
        passwordSection.style.display = "none";
        passwordSection.classList.remove("active");
      }
      clearAlerts();
    });
  }

  // 2. OTP Sub-Channels: Email vs SMS vs WhatsApp
  if (subChannelBtns.length > 0) {
    function activateChannelBtn(btn) {
      if (!btn) return;
      if (btn.classList.contains("is-disabled") || btn.disabled) {
        const channelLabel = btn.querySelector("span")?.textContent.trim() || "This channel";
        showAlert(`${channelLabel} is currently unavailable. Provider credentials must be configured in .env.`, "error");
        return;
      }

      subChannelBtns.forEach((b) => {
        b.classList.remove("active");
        b.setAttribute("aria-checked", "false");
        b.setAttribute("tabindex", "-1");
      });
      btn.classList.add("active");
      btn.setAttribute("aria-checked", "true");
      btn.setAttribute("tabindex", "0");
      btn.focus();

      const ch = btn.dataset.channel || "email";
      if (otpChannelInput) otpChannelInput.value = ch;
      currentActiveChannel = ch;
      clearAlerts();

      if (otpIdentifierInput) {
        if (ch === "email") {
          if (otpIdentifierLabel) otpIdentifierLabel.textContent = "Email Address";
          otpIdentifierInput.placeholder = "e.g. user@company.com";
          otpIdentifierInput.type = "email";
        } else if (ch === "sms") {
          if (otpIdentifierLabel) otpIdentifierLabel.textContent = "Mobile Phone (SMS)";
          otpIdentifierInput.placeholder = "e.g. +91 9876543210";
          otpIdentifierInput.type = "tel";
        } else if (ch === "whatsapp") {
          if (otpIdentifierLabel) otpIdentifierLabel.textContent = "WhatsApp Mobile Number";
          otpIdentifierInput.placeholder = "e.g. +91 9876543210";
          otpIdentifierInput.type = "tel";
        }
      }
    }

    subChannelBtns.forEach(function (btn, index) {
      btn.addEventListener("click", function () {
        activateChannelBtn(btn);
      });

      btn.addEventListener("keydown", function (e) {
        let newIndex = -1;
        const total = subChannelBtns.length;
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
          activateChannelBtn(subChannelBtns[newIndex]);
        }
      });
    });
  }

  // 3. Timer Helpers
  function startExpiryTimer(totalSeconds = 300) {
    clearInterval(expiryInterval);
    let secondsLeft = totalSeconds;

    function update() {
      if (!otpCountdownEl) return;
      const mins = Math.floor(secondsLeft / 60);
      const secs = secondsLeft % 60;
      otpCountdownEl.textContent = `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
      if (secondsLeft <= 0) {
        clearInterval(expiryInterval);
        otpCountdownEl.textContent = "00:00 (Expired)";
        showAlert("Your verification code has expired. Please request a new one.", "error");
      }
      secondsLeft--;
    }
    update();
    expiryInterval = setInterval(update, 1000);
  }

  function startCooldownTimer(seconds = 60) {
    clearInterval(cooldownInterval);
    cooldownSecondsRemaining = seconds;
    if (resendOtpBtn) resendOtpBtn.disabled = true;

    function update() {
      if (!resendOtpBtn) return;
      if (cooldownSecondsRemaining <= 0) {
        clearInterval(cooldownInterval);
        resendOtpBtn.disabled = false;
        resendOtpBtn.textContent = "Resend Code";
      } else {
        resendOtpBtn.textContent = `Resend in ${cooldownSecondsRemaining}s`;
        cooldownSecondsRemaining--;
      }
    }
    update();
    cooldownInterval = setInterval(update, 1000);
  }

  // 4. Helper: Get Entered OTP
  function getEnteredLoginOtp() {
    const digitInputs = document.querySelectorAll(
      "#otp-step-2 .otp-digit, #otp-step-verify .otp-digit, .otp-digit"
    );
    if (digitInputs.length >= 6) {
      const code = Array.from(digitInputs).map((d) => d.value.trim()).join("");
      if (code.length === 6) return code;
    }

    const hidden = document.getElementById("otp-code-hidden");
    if (hidden && hidden.value.trim().length === 6) return hidden.value.trim();

    const single =
      document.getElementById("otp-verify-code") ||
      document.getElementById("otp-code-input");
    if (single && single.value.trim()) return single.value.trim();

    return Array.from(digitInputs).map((d) => d.value.trim()).join("");
  }

  // 5. Send / Request OTP (AJAX)
  if (sendOtpBtn) {
    sendOtpBtn.addEventListener("click", async function (e) {
      e.preventDefault();
      const identifier = otpIdentifierInput ? otpIdentifierInput.value.trim() : "";
      const channel = (otpChannelInput && otpChannelInput.value) || currentActiveChannel;

      if (!identifier) {
        showAlert(channel === "email" ? "Please enter your email address." : "Please enter your mobile phone number.", "error");
        if (otpIdentifierInput) otpIdentifierInput.focus();
        return;
      }

      sendOtpBtn.classList.add("is-loading");
      sendOtpBtn.disabled = true;
      clearAlerts();

      try {
        const response = await fetch("/api/otp/request/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify({ identifier: identifier, channel: channel }),
        });

        const data = await response.json();

        if (response.ok && data.success) {
          // Switch to Step 2
          if (otpStepRequest) {
            otpStepRequest.classList.remove("active");
            otpStepRequest.style.display = "none";
          }
          if (otpStepVerify) {
            otpStepVerify.classList.add("active");
            otpStepVerify.style.display = "block";
          }

          const masked = data.masked_identifier || identifier;
          if (otpTargetDisplay) otpTargetDisplay.textContent = masked;
          if (verifyIdentifierInput) verifyIdentifierInput.value = data.identifier || identifier;
          currentActiveChannel = data.channel || channel;

          // Clear previous code and focus first digit
          document.querySelectorAll(".otp-digit").forEach((d) => (d.value = ""));
          const hiddenOtp = document.getElementById("otp-code-hidden");
          if (hiddenOtp) hiddenOtp.value = "";
          const firstDigit = document.querySelector(".otp-digit");
          if (firstDigit) firstDigit.focus();

          showAlert(data.message, "success");
          startExpiryTimer(data.expires_in || 300);
          startCooldownTimer(data.cooldown || 60);
        } else {
          showAlert(data.message || "Unable to send verification code.", "error");
        }
      } catch (err) {
        showAlert("Network communication error. Please try again.", "error");
      } finally {
        sendOtpBtn.classList.remove("is-loading");
        sendOtpBtn.disabled = false;
      }
    });
  }

  // 6. Resend OTP Button Handler
  if (resendOtpBtn) {
    resendOtpBtn.addEventListener("click", async function (e) {
      e.preventDefault();
      if (cooldownSecondsRemaining > 0) return;

      const identifier = verifyIdentifierInput ? verifyIdentifierInput.value.trim() : "";
      if (!identifier) return;

      resendOtpBtn.disabled = true;
      clearAlerts();

      try {
        const response = await fetch("/api/otp/request/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify({ identifier: identifier, channel: currentActiveChannel }),
        });
        const data = await response.json();
        if (response.ok && data.success) {
          showAlert(data.message || "A fresh verification code has been dispatched.", "success");
          startExpiryTimer(data.expires_in || 300);
          startCooldownTimer(data.cooldown || 60);
        } else {
          showAlert(data.message || "Failed to resend code.", "error");
          resendOtpBtn.disabled = false;
        }
      } catch (err) {
        showAlert("Network error during resend. Please try again.", "error");
        resendOtpBtn.disabled = false;
      }
    });
  }

  // 7. Verify OTP (AJAX)
  if (verifyOtpBtn) {
    verifyOtpBtn.addEventListener("click", async function (e) {
      e.preventDefault();
      const identifier = verifyIdentifierInput ? verifyIdentifierInput.value.trim() : "";
      const code = getEnteredLoginOtp();
      const rememberMe =
        document.getElementById("otp-remember-me")?.checked ||
        document.getElementById("remember-me")?.checked ||
        false;

      if (!code || code.length !== 6) {
        showAlert("Please enter the complete 6-digit code.", "error");
        const emptyDigit = Array.from(document.querySelectorAll(".otp-digit")).find((d) => !d.value);
        if (emptyDigit) emptyDigit.focus();
        return;
      }

      verifyOtpBtn.classList.add("is-loading");
      verifyOtpBtn.disabled = true;
      clearAlerts();

      try {
        const response = await fetch("/api/otp/verify/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify({
            identifier: identifier,
            otp_code: code,
            remember_me: rememberMe,
          }),
        });

        const data = await response.json();

        if (response.ok && data.success) {
          showAlert(data.message, "success");
          setTimeout(() => {
            window.location.href = data.redirect_url || "/dashboard/";
          }, 400);
        } else {
          showAlert(data.message || "Invalid or expired verification code.", "error");
          verifyOtpBtn.disabled = false;
        }
      } catch (err) {
        showAlert("Network communication error. Please try again.", "error");
        verifyOtpBtn.disabled = false;
      } finally {
        verifyOtpBtn.classList.remove("is-loading");
      }
    });
  }

  // 8. Edit / Change Identifier
  if (changeIdentifierBtn) {
    changeIdentifierBtn.addEventListener("click", function (e) {
      e.preventDefault();
      clearInterval(expiryInterval);
      clearInterval(cooldownInterval);
      if (otpStepVerify) {
        otpStepVerify.classList.remove("active");
        otpStepVerify.style.display = "none";
      }
      if (otpStepRequest) {
        otpStepRequest.classList.add("active");
        otpStepRequest.style.display = "block";
      }
      clearAlerts();
    });
  }
});
