/**
 * Authentication Platform - Common Interactive Utilities (auth_common.js)
 * Provides universal password visibility toggling, 6-digit OTP input coordination,
 * and robust cross-template component bindings.
 */

(function () {
  'use strict';

  // SVG Icons
  const ICON_EYE = `<svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>`;
  const ICON_EYE_SLASH = `<svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24M1 1l22 22"></path></svg>`;

  /**
   * Universal Password Show/Hide Toggle
   * Uses event delegation on document so it works on any template,
   * any element ID, and even dynamically created/swapped DOM elements.
   */
  document.addEventListener('click', function (e) {
    const toggleBtn = e.target.closest(
      '.toggle-password-btn, [data-toggle="password"], #toggle-password-btn, #toggle-reg-password, #toggle-reg-confirm, #toggle-new-password, #toggle-confirm-password, #toggle-reset-password-btn, #toggle-reset-confirm-password-btn'
    );
    if (!toggleBtn) return;

    e.preventDefault();

    // Find the associated password input:
    // 1. Explicit target by ID if data-target is provided
    let input = null;
    if (toggleBtn.dataset.target) {
      input = document.getElementById(toggleBtn.dataset.target);
    }

    // 2. Look inside the same .input-wrapper parent
    if (!input) {
      const wrapper = toggleBtn.closest('.input-wrapper');
      if (wrapper) {
        input = wrapper.querySelector('input[type="password"], input[type="text"]');
      }
    }

    // 3. Sibling element
    if (!input && toggleBtn.previousElementSibling && toggleBtn.previousElementSibling.tagName === 'INPUT') {
      input = toggleBtn.previousElementSibling;
    }

    if (!input) return;

    const isPassword = input.type === 'password';
    input.type = isPassword ? 'text' : 'password';

    // Update accessibility attributes & icon
    toggleBtn.setAttribute('aria-label', isPassword ? 'Hide password' : 'Show password');
    toggleBtn.innerHTML = isPassword ? ICON_EYE_SLASH : ICON_EYE;

    // Focus input back for user convenience
    input.focus();
  });

  /**
   * Universal 6-Digit OTP Box Coordination
   * Auto-advances across boxes, handles backspace, and supports pasting entire 6-digit code.
   */
  function initOtpGroups() {
    const groups = document.querySelectorAll('.otp-digit-group, #otp-inputs');
    groups.forEach((group) => {
      const digits = Array.from(group.querySelectorAll('.otp-digit'));
      if (digits.length === 0) return;

      function syncHiddenOtp() {
        const fullCode = digits.map((d) => d.value.trim()).join('');
        // Sync to hidden input in current form or standard IDs
        const form = group.closest('form');
        const hidden =
          (form ? form.querySelector('input[name="otp_code"], #otp-code-hidden') : null) ||
          document.getElementById('otp-code-hidden') ||
          document.getElementById('reg-otp-code-input') ||
          document.getElementById('otp-verify-code') ||
          document.getElementById('otp-code-input') ||
          document.getElementById('forgot-otp-code-input');
        if (hidden) {
          hidden.value = fullCode;
        }
        return fullCode;
      }

      digits.forEach((digit, index) => {
        digit.addEventListener('input', function () {
          this.value = this.value.replace(/[^0-9]/g, '').slice(-1);
          const code = syncHiddenOtp();

          if (this.value && index < digits.length - 1) {
            digits[index + 1].focus();
            digits[index + 1].select();
          }

          if (code.length === 6) {
            const form = group.closest('form');
            const submitBtn = form
              ? form.querySelector('button[type="submit"], #btn-verify-otp, #verify-reg-otp-btn, #verify-otp-btn, #verify-forgot-otp-btn')
              : null;
            if (submitBtn && !submitBtn.disabled) {
              submitBtn.click();
            }
          }
        });

        digit.addEventListener('keydown', function (e) {
          if (e.key === 'Backspace' && !this.value && index > 0) {
            digits[index - 1].focus();
            digits[index - 1].value = '';
            syncHiddenOtp();
          } else if (e.key === 'ArrowLeft' && index > 0) {
            digits[index - 1].focus();
          } else if (e.key === 'ArrowRight' && index < digits.length - 1) {
            digits[index + 1].focus();
          }
        });

        digit.addEventListener('paste', function (e) {
          e.preventDefault();
          const pasteData = (e.clipboardData || window.clipboardData).getData('text') || '';
          const cleanDigits = pasteData.replace(/[^0-9]/g, '').slice(0, 6);
          if (!cleanDigits) return;

          for (let i = 0; i < digits.length; i++) {
            digits[i].value = cleanDigits[i] || '';
          }
          const code = syncHiddenOtp();
          const lastIdx = Math.min(cleanDigits.length - 1, digits.length - 1);
          if (lastIdx >= 0) digits[lastIdx].focus();

          if (code.length === 6) {
            const form = group.closest('form');
            const submitBtn = form
              ? form.querySelector('button[type="submit"], #btn-verify-otp, #verify-reg-otp-btn, #verify-otp-btn, #verify-forgot-otp-btn')
              : null;
            if (submitBtn && !submitBtn.disabled) {
              submitBtn.click();
            }
          }
        });
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initOtpGroups);
  } else {
    initOtpGroups();
  }
})();
