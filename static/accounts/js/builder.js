/**
 * Custom Builder Client Controller (Phases 10 & 11)
 * Live CSS variable manipulation, iframe preview synchronization,
 * and AJAX integration for saving, loading, duplicating, and exporting configurations.
 */

(function () {
  'use strict';

  let currentConfig = window.initialConfig || {};
  let activeConfigId = window.activeConfigId || null;
  let currentScreen = 'login'; // 'login', 'register', 'forgot_password', 'reset_password'

  const previewFrame = document.getElementById('preview-iframe');
  const frameWrapper = document.getElementById('preview-frame-wrapper');

  // Screen URL mapping
  const screenUrls = {
    login: '/login/',
    register: '/register/',
    forgot_password: '/forgot-password/',
    reset_password: '/reset-password/',
  };

  // --------------------------------------------------------------------------
  // TOAST FEEDBACK
  // --------------------------------------------------------------------------
  function showToast(message, isError = false) {
    const toast = document.getElementById('builder-toast');
    if (!toast) return;
    toast.textContent = message;
    toast.style.borderColor = isError ? '#ef4444' : '#10b981';
    toast.classList.add('show');
    setTimeout(() => {
      toast.classList.remove('show');
    }, 3000);
  }

  // --------------------------------------------------------------------------
  // ACCORDION CONTROLS — Fixed: HTML uses .section-card-header not .section-header
  // --------------------------------------------------------------------------
  function initAccordions() {
    const headers = document.querySelectorAll('.section-card-header');
    headers.forEach((btn, index) => {
      const body = btn.nextElementSibling;
      const arrow = btn.querySelector('.section-arrow');
      // First section open by default, rest collapsed
      if (index === 0) {
        btn.setAttribute('aria-expanded', 'true');
        if (body) body.classList.remove('collapsed');
        if (arrow) arrow.style.transform = 'rotate(0deg)';
      } else {
        btn.setAttribute('aria-expanded', 'false');
        if (body) body.classList.add('collapsed');
        if (arrow) arrow.style.transform = 'rotate(-90deg)';
      }

      btn.addEventListener('click', () => {
        const isOpen = btn.getAttribute('aria-expanded') === 'true';
        if (isOpen) {
          btn.setAttribute('aria-expanded', 'false');
          if (body) body.classList.add('collapsed');
          if (arrow) arrow.style.transform = 'rotate(-90deg)';
        } else {
          btn.setAttribute('aria-expanded', 'true');
          if (body) body.classList.remove('collapsed');
          if (arrow) arrow.style.transform = 'rotate(0deg)';
        }
      });
    });
  }
  initAccordions();

  // --------------------------------------------------------------------------
  // VIEWPORT CONTROLS
  // --------------------------------------------------------------------------
  document.querySelectorAll('.viewport-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.viewport-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      const mode = btn.dataset.mode;
      frameWrapper.className = `preview-frame-wrapper mode-${mode}`;
    });
  });

  // --------------------------------------------------------------------------
  // SCREEN SWITCHER
  // --------------------------------------------------------------------------
  document.querySelectorAll('.screen-tab-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.screen-tab-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      currentScreen = btn.dataset.screen;
      updatePreviewUrl();
    });
  });

  function updatePreviewUrl() {
    const template = currentConfig.template || 'modern';
    const base = screenUrls[currentScreen] || '/login/';
    previewFrame.src = `${base}?template=${template}&preview=1`;
  }

  // --------------------------------------------------------------------------
  // LIVE PREVIEW SYNCHRONIZATION
  // --------------------------------------------------------------------------
  function applyLiveStylesToPreview() {
    try {
      const doc = previewFrame.contentDocument || previewFrame.contentWindow.document;
      if (!doc || !doc.documentElement) return;

      const colors = currentConfig.colors || {};
      const card = currentConfig.card || {};
      const inputs = currentConfig.inputs || {};
      const buttons = currentConfig.buttons || {};
      const typography = currentConfig.typography || {};
      const auth = currentConfig.authentication || {};

      const root = doc.documentElement;
      if (colors.primary) root.style.setProperty('--primary-color', colors.primary);
      if (colors.primary_hover) root.style.setProperty('--primary-hover', colors.primary_hover);
      if (colors.secondary) root.style.setProperty('--secondary-color', colors.secondary);
      if (colors.background) root.style.setProperty('--background-color', colors.background);
      if (colors.card_bg) root.style.setProperty('--card-background', colors.card_bg);
      if (colors.text) root.style.setProperty('--text-color', colors.text);
      if (colors.muted) root.style.setProperty('--muted-color', colors.muted);
      if (colors.border) root.style.setProperty('--border-color', colors.border);

      if (card.width) root.style.setProperty('--card-width', card.width);
      if (card.radius) root.style.setProperty('--radius-lg', card.radius);
      if (inputs.height) root.style.setProperty('--input-height', inputs.height);
      if (inputs.radius) root.style.setProperty('--radius-sm', inputs.radius);
      if (typography.font_family) root.style.setProperty('--font-family', typography.font_family);
      if (typography.heading_size) {
        root.style.setProperty('--heading-size', typography.heading_size);
        const headings = doc.querySelectorAll('.auth-title, h1');
        headings.forEach((h) => {
          h.style.fontSize = typography.heading_size;
        });
      }

      // Branding & Logo Customization Tokens
      const branding = currentConfig.branding || {};
      const widthVal = branding.logo_width || '120px';
      const heightVal = branding.logo_height || '36px';
      const scaleNum = parseFloat(branding.logo_scale || 100);
      const scaleFactor = (scaleNum / 100).toFixed(2);
      const alignVal = branding.logo_align || 'center';
      const objectFitVal = branding.maintain_aspect_ratio !== false ? 'contain' : 'fill';

      root.style.setProperty('--logo-width', widthVal);
      root.style.setProperty('--logo-height', heightVal);
      root.style.setProperty('--logo-scale', scaleFactor);
      root.style.setProperty('--logo-align', alignVal);
      root.style.setProperty('--logo-object-fit', objectFitVal);

      // OTP Buttons Customization Tokens
      const otpButtons = currentConfig.otp_buttons || {};
      if (otpButtons.height) root.style.setProperty('--otp-btn-height', otpButtons.height);
      if (otpButtons.icon_size) root.style.setProperty('--otp-btn-icon-size', otpButtons.icon_size);
      if (otpButtons.font_size) root.style.setProperty('--otp-btn-font-size', otpButtons.font_size);
      if (otpButtons.radius) root.style.setProperty('--otp-btn-radius', otpButtons.radius);
      if (otpButtons.gap) root.style.setProperty('--otp-btn-gap', otpButtons.gap);
      if (otpButtons.padding) root.style.setProperty('--otp-btn-padding', otpButtons.padding);
      if (otpButtons.border_width) root.style.setProperty('--otp-btn-border-width', otpButtons.border_width);
      if (otpButtons.custom_width) root.style.setProperty('--otp-btn-custom-width', otpButtons.custom_width);

      // OTP Channel Selector Width Mode in Preview DOM
      const widthMode = otpButtons.width_mode || 'auto';
      const subChannelSelectors = doc.querySelectorAll('.sub-channel-selector');
      subChannelSelectors.forEach((sel) => {
        sel.classList.remove('width-mode-auto', 'width-mode-full', 'width-mode-custom');
        sel.classList.add(`width-mode-${widthMode}`);
      });

      // Live Logo / Badge Reflection in Preview DOM
      const logoImgs = doc.querySelectorAll('.brand-custom-logo, #brand-header-logo, #hero-brand-logo');
      const defaultBadges = doc.querySelectorAll('.brand-badge, .hero-brand-icon, #brand-header-default-badge, #hero-brand-default-badge');
      const logoContainers = doc.querySelectorAll('.brand-header-logo-container, #brand-header-container');

      if (branding.logo_url) {
        logoImgs.forEach((img) => {
          img.src = branding.logo_url;
          img.style.display = 'block';
          img.style.maxWidth = `calc(${widthVal} * ${scaleFactor})`;
          img.style.maxHeight = `calc(${heightVal} * ${scaleFactor})`;
          img.style.objectFit = objectFitVal;
          if (branding.brand_name) {
            img.alt = `${branding.brand_name} Logo`;
          }
        });
        defaultBadges.forEach((badge) => {
          badge.style.display = 'none';
        });
      } else {
        logoImgs.forEach((img) => {
          img.style.display = 'none';
          img.src = '';
        });
        defaultBadges.forEach((badge) => {
          badge.style.display = '';
        });
      }

      logoContainers.forEach((container) => {
        container.classList.remove('align-left', 'align-center', 'align-right');
        container.classList.add(`align-${alignVal}`);
      });

      // Also update brand title text inside iframe if element exists
      const brandText = branding.brand_name !== undefined ? branding.brand_name : 'Auth Platform';
      if (brandText) {
        doc.title = `${brandText} — Auth`;
      }

      const brandElements = doc.querySelectorAll('.brand-name, #brand-header-name, .hero-brand-title, .brand-name-title');
      brandElements.forEach((el) => {
        el.textContent = brandText;
      });

      const brandContainers = doc.querySelectorAll('.brand-name-container, #brand-name-container');
      brandContainers.forEach((container) => {
        container.style.display = brandText ? 'flex' : 'none';
        container.classList.remove('align-left', 'align-center', 'align-right');
        container.classList.add(`align-${alignVal}`);
      });

      // --- AUTHENTICATION SETTINGS REFLECTION IN PREVIEW IFRAME ---
      const enablePwd = auth.enable_password !== false;
      const enableOtp = auth.enable_otp !== false;
      const enableEmail = auth.enable_email !== false;
      const enableSms = auth.enable_sms !== false;
      const enableWhatsapp = auth.enable_whatsapp !== false;
      const rememberMe = auth.remember_me !== false;
      const showRegister = auth.show_register !== false;
      const showForgot = auth.show_forgot !== false;

      // 1. Mode Selector & Login Tabs
      const modeSelector = doc.querySelector('.auth-mode-selector');
      const pwdBtn = doc.getElementById('mode-password-btn');
      const otpBtn = doc.getElementById('mode-otp-btn');
      const pwdSection = doc.getElementById('password-login-section');
      const otpSection = doc.getElementById('otp-login-section');

      if (modeSelector) {
        modeSelector.style.display = (enablePwd && enableOtp) ? 'flex' : 'none';
      }

      if (!enablePwd && enableOtp) {
        if (pwdSection) pwdSection.style.display = 'none';
        if (otpSection) {
          otpSection.style.display = 'block';
          otpSection.classList.add('active');
        }
        if (otpBtn) otpBtn.classList.add('active');
        if (pwdBtn) pwdBtn.classList.remove('active');
      } else if (enablePwd && !enableOtp) {
        if (otpSection) otpSection.style.display = 'none';
        if (pwdSection) {
          pwdSection.style.display = 'block';
          pwdSection.classList.add('active');
        }
        if (pwdBtn) pwdBtn.classList.add('active');
        if (otpBtn) otpBtn.classList.remove('active');
      } else if (!enablePwd && !enableOtp) {
        if (pwdSection) pwdSection.style.display = 'none';
        if (otpSection) otpSection.style.display = 'none';
      } else {
        // Both enabled: keep active section or default to password
        if (otpBtn && otpBtn.classList.contains('active') && !pwdBtn?.classList.contains('active')) {
          if (otpSection) otpSection.style.display = 'block';
          if (pwdSection) pwdSection.style.display = 'none';
        } else {
          if (pwdSection) pwdSection.style.display = 'block';
          if (otpSection) otpSection.style.display = 'none';
          if (pwdBtn) pwdBtn.classList.add('active');
        }
      }

      // 2. OTP Sub-Channels (Email, SMS, WhatsApp)
      const emailBtns = doc.querySelectorAll('[data-channel="email"], #channel-email-btn, #subchannel-email-btn');
      const smsBtns = doc.querySelectorAll('[data-channel="sms"], #channel-mobile-btn, #subchannel-sms-btn');
      const waBtns = doc.querySelectorAll('[data-channel="whatsapp"], #channel-whatsapp-btn, #subchannel-whatsapp-btn');

      emailBtns.forEach((b) => (b.style.display = enableEmail ? '' : 'none'));
      smsBtns.forEach((b) => (b.style.display = enableSms ? '' : 'none'));
      waBtns.forEach((b) => (b.style.display = enableWhatsapp ? '' : 'none'));

      // If currently active sub-channel button was hidden, select the first visible channel
      const allSubChannels = doc.querySelectorAll('.sub-channel-btn');
      let hasActiveVisible = false;
      allSubChannels.forEach((btn) => {
        if (btn.classList.contains('active') && btn.style.display !== 'none') {
          hasActiveVisible = true;
        }
      });
      if (!hasActiveVisible && allSubChannels.length > 0) {
        for (const btn of allSubChannels) {
          if (btn.style.display !== 'none') {
            allSubChannels.forEach((b) => b.classList.remove('active'));
            btn.classList.add('active');
            const ch = btn.getAttribute('data-channel');
            const chInput = doc.querySelector('input[name="channel"]');
            if (chInput && ch) chInput.value = ch;
            break;
          }
        }
      }

      // 3. Remember Me Checkboxes
      const remInputs = doc.querySelectorAll('#remember-me, #otp-remember-me');
      remInputs.forEach((inp) => {
        const parent = inp.closest('.form-row-between') || inp.closest('label');
        if (parent) parent.style.display = rememberMe ? '' : 'none';
      });

      // 4. Show Forgot Password Links
      const forgotLinks = doc.querySelectorAll('a[href*="forgot"]');
      forgotLinks.forEach((a) => (a.style.display = showForgot ? '' : 'none'));

      // 5. Show Create Account Footers
      const regFooters = doc.querySelectorAll('.auth-footer');
      regFooters.forEach((f) => (f.style.display = showRegister ? '' : 'none'));
    } catch (e) {
      if (window.console && window.console.warn) {
        console.warn('[Builder Preview] Error applying live styles to iframe preview:', e);
      }
    }
  }

  previewFrame.addEventListener('load', () => {
    applyLiveStylesToPreview();
  });

  // --------------------------------------------------------------------------
  // STATE SIMULATOR (Google Stitch)
  // --------------------------------------------------------------------------
  function applySimulatorState(state) {
    try {
      const doc = previewFrame.contentDocument || previewFrame.contentWindow.document;
      if (!doc) return;
      const submitBtn = doc.querySelector('.btn-primary');
      let alertBox = doc.querySelector('.alert-box:not(.demo-banner)');
      let alertContainer = doc.querySelector('.alert-container');

      if (!alertContainer) {
        const body = doc.querySelector('.auth-body');
        if (body) {
          alertContainer = doc.createElement('div');
          alertContainer.className = 'alert-container';
          body.insertBefore(alertContainer, body.firstChild);
        }
      }

      if (state === 'default') {
        if (submitBtn) submitBtn.classList.remove('is-loading');
        if (alertBox) alertBox.remove();
      } else if (state === 'loading') {
        if (submitBtn) submitBtn.classList.add('is-loading');
        if (alertBox) alertBox.remove();
      } else if (state === 'error') {
        if (submitBtn) submitBtn.classList.remove('is-loading');
        if (!alertBox && alertContainer) {
          alertBox = doc.createElement('div');
          alertContainer.appendChild(alertBox);
        }
        if (alertBox) {
          alertBox.className = 'alert-box alert-error';
          alertBox.textContent = 'Invalid username or password. Please try again.';
        }
      } else if (state === 'success') {
        if (submitBtn) submitBtn.classList.remove('is-loading');
        if (!alertBox && alertContainer) {
          alertBox = doc.createElement('div');
          alertContainer.appendChild(alertBox);
        }
        if (alertBox) {
          alertBox.className = 'alert-box alert-success';
          alertBox.textContent = 'Authentication successful! Redirecting to workspace...';
        }
      }
    } catch (e) {
      if (window.console && window.console.warn) {
        console.warn('[State Simulator] Error updating preview state:', e);
      }
    }
  }

  // --------------------------------------------------------------------------
  // BIND FORM CONTROLS
  // --------------------------------------------------------------------------
  function bindInputs() {
    // Template Selector (Dropdown & Bottom Style Segmented Pills)
    const tplSelect = document.getElementById('ctrl-template-select');
    if (tplSelect) {
      tplSelect.addEventListener('change', () => {
        currentConfig.template = tplSelect.value;
        document.querySelectorAll('.style-pill-btn').forEach((btn) => {
          btn.classList.toggle('active', btn.dataset.template === tplSelect.value);
        });
        updatePreviewUrl();
      });
    }

    document.querySelectorAll('.style-pill-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const tpl = btn.dataset.template;
        if (!tpl) return;
        currentConfig.template = tpl;
        if (tplSelect) tplSelect.value = tpl;
        document.querySelectorAll('.style-pill-btn').forEach((b) => {
          b.classList.toggle('active', b.dataset.template === tpl);
        });
        updatePreviewUrl();
      });
    });

    // Colors
    ['primary', 'secondary', 'background', 'card_bg', 'text', 'muted', 'border'].forEach((colorKey) => {
      const picker = document.getElementById(`ctrl-color-${colorKey}`);
      const text = document.getElementById(`ctrl-color-${colorKey}-text`);
      if (picker && text) {
        picker.addEventListener('input', () => {
          text.value = picker.value;
          currentConfig.colors = currentConfig.colors || {};
          currentConfig.colors[colorKey] = picker.value;
          applyLiveStylesToPreview();
        });
        text.addEventListener('input', () => {
          picker.value = text.value;
          currentConfig.colors = currentConfig.colors || {};
          currentConfig.colors[colorKey] = text.value;
          applyLiveStylesToPreview();
        });
      }
    });

    // Primary Swatches (Google Stitch)
    document.querySelectorAll('.swatch-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const color = btn.dataset.color;
        if (!color) return;
        const picker = document.getElementById('ctrl-color-primary');
        const text = document.getElementById('ctrl-color-primary-text');
        if (picker) picker.value = color;
        if (text) text.value = color;
        currentConfig.colors = currentConfig.colors || {};
        currentConfig.colors.primary = color;
        applyLiveStylesToPreview();
      });
    });

    // Card Surface Preset (Google Stitch)
    const surfaceSelect = document.getElementById('card-surface-select');
    if (surfaceSelect) {
      surfaceSelect.addEventListener('change', () => {
        const color = surfaceSelect.value;
        const cardBgPicker = document.getElementById('ctrl-color-card_bg');
        const cardBgText = document.getElementById('ctrl-color-card_bg-text');
        if (cardBgPicker) cardBgPicker.value = color;
        if (cardBgText) cardBgText.value = color;
        currentConfig.colors = currentConfig.colors || {};
        currentConfig.colors.card_bg = color;
        applyLiveStylesToPreview();
      });
    }

    // Sliders
    const sliders = [
      { id: 'ctrl-card-width', key: 'card.width', unit: 'px' },
      { id: 'ctrl-card-radius', key: 'card.radius', unit: 'px' },
      { id: 'ctrl-input-height', key: 'inputs.height', unit: 'px' },
      { id: 'ctrl-btn-height', key: 'buttons.height', unit: 'px' },
    ];

    sliders.forEach(({ id, key, unit }) => {
      const slider = document.getElementById(id);
      const display = document.getElementById(`${id}-val`);
      if (slider && display) {
        slider.addEventListener('input', () => {
          const val = `${slider.value}${unit}`;
          display.textContent = val;
          const [section, prop] = key.split('.');
          currentConfig[section] = currentConfig[section] || {};
          currentConfig[section][prop] = val;
          applyLiveStylesToPreview();
        });
      }
    });

    // Branding: Brand Name
    const brandNameInput = document.getElementById('ctrl-brand-name');
    if (brandNameInput) {
      brandNameInput.addEventListener('input', () => {
        currentConfig.branding = currentConfig.branding || {};
        currentConfig.branding.brand_name = brandNameInput.value.slice(0, 60);
        applyLiveStylesToPreview();
      });
    }

    // --- BRAND LOGO UPLOAD, SIZING & ALIGNMENT ---
    const logoFileInput = document.getElementById('ctrl-logo-file');
    const logoDropzone = document.getElementById('ctrl-logo-dropzone');
    const replaceLogoBtn = document.getElementById('btn-replace-logo');
    const removeLogoBtn = document.getElementById('btn-remove-logo');
    const restoreDefaultLogoBtn = document.getElementById('btn-restore-default-logo');

    function handleLogoFile(file) {
      if (!file) return;

      // 1. Enforce strict 500 KB raw upload limit
      if (file.size > 500 * 1024) {
        showToast('Image exceeds 500 KB limit. Please upload an image under 500 KB.', true);
        return;
      }

      // 2. Validate MIME type strictly: PNG, JPEG, WebP. Reject SVG!
      const validTypes = ['image/png', 'image/jpeg', 'image/webp'];
      if (!validTypes.includes(file.type.toLowerCase())) {
        showToast('Invalid file format. Only PNG, JPEG, and WebP are supported. SVG is not allowed.', true);
        return;
      }

      const reader = new FileReader();
      reader.onload = (e) => {
        currentConfig.branding = currentConfig.branding || {};
        currentConfig.branding.logo_url = e.target.result;
        currentConfig.branding._logo_filename = file.name;
        currentConfig.branding._logo_filesize = `${(file.size / 1024).toFixed(1)} KB`;
        updateLogoUI(currentConfig.branding);
        applyLiveStylesToPreview();

        if (window.console && window.console.log) {
          const mimeMatch = (currentConfig.branding.logo_url || '').match(/^data:([^;]+);base64,/);
          console.log('[Logo Upload Verified]', {
            exists: !!currentConfig.branding.logo_url,
            type: typeof currentConfig.branding.logo_url,
            length: (currentConfig.branding.logo_url || '').length,
            mime: mimeMatch ? mimeMatch[1] : (file.type || 'unknown'),
          });
        }

        showToast('Brand logo uploaded successfully!');
      };
      reader.onerror = () => {
        showToast('Failed to read image file.', true);
      };
      reader.readAsDataURL(file);
    }

    if (logoFileInput) {
      logoFileInput.addEventListener('change', () => {
        if (logoFileInput.files && logoFileInput.files[0]) {
          handleLogoFile(logoFileInput.files[0]);
          logoFileInput.value = '';
        }
      });
    }

    if (logoDropzone) {
      logoDropzone.addEventListener('click', (e) => {
        // Only trigger file picker if not clicking action buttons
        if (!e.target.closest('#btn-replace-logo') && !e.target.closest('#btn-remove-logo')) {
          if (logoFileInput) logoFileInput.click();
        }
      });

      logoDropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        logoDropzone.classList.add('drag-over');
      });

      logoDropzone.addEventListener('dragleave', () => {
        logoDropzone.classList.remove('drag-over');
      });

      logoDropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        logoDropzone.classList.remove('drag-over');
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
          handleLogoFile(e.dataTransfer.files[0]);
        }
      });
    }

    if (replaceLogoBtn) {
      replaceLogoBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (logoFileInput) logoFileInput.click();
      });
    }

    if (removeLogoBtn) {
      removeLogoBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        currentConfig.branding = currentConfig.branding || {};
        currentConfig.branding.logo_url = '';
        delete currentConfig.branding._logo_filename;
        delete currentConfig.branding._logo_filesize;
        updateLogoUI(currentConfig.branding);
        applyLiveStylesToPreview();
        showToast('Custom logo removed. Default brand emblem active.');
      });
    }

    if (restoreDefaultLogoBtn) {
      restoreDefaultLogoBtn.addEventListener('click', () => {
        currentConfig.branding = currentConfig.branding || {};
        currentConfig.branding.logo_url = '';
        currentConfig.branding.logo_width = '120px';
        currentConfig.branding.logo_height = '36px';
        currentConfig.branding.logo_scale = 100;
        currentConfig.branding.logo_align = 'center';
        currentConfig.branding.maintain_aspect_ratio = true;
        delete currentConfig.branding._logo_filename;
        delete currentConfig.branding._logo_filesize;
        syncSidebarControlsFromConfig(currentConfig);
        applyLiveStylesToPreview();
        showToast('Restored default brand settings and emblem.');
      });
    }

    // Logo Alignment Segmented Control
    const logoAlignBtns = document.querySelectorAll('#ctrl-logo-align-group .segmented-btn');
    logoAlignBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        logoAlignBtns.forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        currentConfig.branding = currentConfig.branding || {};
        currentConfig.branding.logo_align = btn.dataset.align;
        applyLiveStylesToPreview();
      });
    });

    // Maintain Aspect Ratio Toggle & Proportional Sizing
    const aspectToggle = document.getElementById('ctrl-logo-aspect-ratio');
    const logoWidthInput = document.getElementById('ctrl-logo-width');
    const logoHeightInput = document.getElementById('ctrl-logo-height');

    if (aspectToggle) {
      aspectToggle.addEventListener('change', () => {
        currentConfig.branding = currentConfig.branding || {};
        currentConfig.branding.maintain_aspect_ratio = aspectToggle.checked;
      });
    }

    if (logoWidthInput) {
      logoWidthInput.addEventListener('input', () => {
        const w = parseInt(logoWidthInput.value, 10) || 120;
        const clampedW = Math.max(30, Math.min(240, w));
        currentConfig.branding = currentConfig.branding || {};

        if (aspectToggle && aspectToggle.checked && logoHeightInput) {
          const prevH = parseInt(logoHeightInput.value, 10) || 36;
          const prevW = parseInt(currentConfig.branding.logo_width, 10) || 120;
          const ratio = prevW > 0 ? prevH / prevW : 36 / 120;
          const newH = Math.round(clampedW * ratio);
          const clampedH = Math.max(20, Math.min(80, newH));
          logoHeightInput.value = clampedH;
          currentConfig.branding.logo_height = `${clampedH}px`;
        }

        currentConfig.branding.logo_width = `${clampedW}px`;
        applyLiveStylesToPreview();
      });
    }

    if (logoHeightInput) {
      logoHeightInput.addEventListener('input', () => {
        const h = parseInt(logoHeightInput.value, 10) || 36;
        const clampedH = Math.max(20, Math.min(80, h));
        currentConfig.branding = currentConfig.branding || {};

        if (aspectToggle && aspectToggle.checked && logoWidthInput) {
          const prevW = parseInt(logoWidthInput.value, 10) || 120;
          const prevH = parseInt(currentConfig.branding.logo_height, 10) || 36;
          const ratio = prevH > 0 ? prevW / prevH : 120 / 36;
          const newW = Math.round(clampedH * ratio);
          const clampedW = Math.max(30, Math.min(240, newW));
          logoWidthInput.value = clampedW;
          currentConfig.branding.logo_width = `${clampedW}px`;
        }

        currentConfig.branding.logo_height = `${clampedH}px`;
        applyLiveStylesToPreview();
      });
    }

    // Logo Scale Slider
    const logoScaleSlider = document.getElementById('ctrl-logo-scale');
    const logoScaleVal = document.getElementById('ctrl-logo-scale-val');
    if (logoScaleSlider) {
      logoScaleSlider.addEventListener('input', () => {
        const val = parseInt(logoScaleSlider.value, 10) || 100;
        if (logoScaleVal) logoScaleVal.textContent = `${val}%`;
        currentConfig.branding = currentConfig.branding || {};
        currentConfig.branding.logo_scale = val;
        applyLiveStylesToPreview();
      });
    }

    // --- OTP CHANNEL SELECTOR BUTTON CONTROLS ---
    // Width Mode Segmented Control
    const otpWidthBtns = document.querySelectorAll('#ctrl-otp-width-mode-group .segmented-btn');
    const customWidthRow = document.getElementById('ctrl-otp-custom-width-row');
    otpWidthBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        otpWidthBtns.forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        const mode = btn.dataset.mode || 'auto';
        currentConfig.otp_buttons = currentConfig.otp_buttons || {};
        currentConfig.otp_buttons.width_mode = mode;
        if (customWidthRow) {
          customWidthRow.style.display = mode === 'custom' ? 'flex' : 'none';
        }
        applyLiveStylesToPreview();
      });
    });

    // Custom Width Input
    const otpCustomWidthInput = document.getElementById('ctrl-otp-custom-width');
    if (otpCustomWidthInput) {
      otpCustomWidthInput.addEventListener('input', () => {
        const val = Math.max(60, Math.min(200, parseInt(otpCustomWidthInput.value, 10) || 100));
        currentConfig.otp_buttons = currentConfig.otp_buttons || {};
        currentConfig.otp_buttons.custom_width = `${val}px`;
        applyLiveStylesToPreview();
      });
    }

    // Height Input
    const otpHeightInput = document.getElementById('ctrl-otp-height');
    const otpHeightVal = document.getElementById('ctrl-otp-height-val');
    if (otpHeightInput) {
      otpHeightInput.addEventListener('input', () => {
        const val = Math.max(30, Math.min(54, parseInt(otpHeightInput.value, 10) || 38));
        if (otpHeightVal) otpHeightVal.textContent = `${val}px`;
        currentConfig.otp_buttons = currentConfig.otp_buttons || {};
        currentConfig.otp_buttons.height = `${val}px`;
        applyLiveStylesToPreview();
      });
    }

    // Icon Size Segmented Control
    const otpIconBtns = document.querySelectorAll('#ctrl-otp-icon-size-group .segmented-btn');
    otpIconBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        otpIconBtns.forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        currentConfig.otp_buttons = currentConfig.otp_buttons || {};
        currentConfig.otp_buttons.icon_size = btn.dataset.size || '16px';
        applyLiveStylesToPreview();
      });
    });

    // Font Size Input
    const otpFontSizeInput = document.getElementById('ctrl-otp-font-size');
    if (otpFontSizeInput) {
      otpFontSizeInput.addEventListener('input', () => {
        const val = Math.max(10, Math.min(16, parseInt(otpFontSizeInput.value, 10) || 12));
        currentConfig.otp_buttons = currentConfig.otp_buttons || {};
        currentConfig.otp_buttons.font_size = `${val}px`;
        applyLiveStylesToPreview();
      });
    }

    // Corner Radius Input
    const otpRadiusInput = document.getElementById('ctrl-otp-radius');
    if (otpRadiusInput) {
      otpRadiusInput.addEventListener('input', () => {
        const val = Math.max(0, Math.min(24, parseInt(otpRadiusInput.value, 10) || 6));
        currentConfig.otp_buttons = currentConfig.otp_buttons || {};
        currentConfig.otp_buttons.radius = `${val}px`;
        applyLiveStylesToPreview();
      });
    }

    // Button Gap Input
    const otpGapInput = document.getElementById('ctrl-otp-gap');
    if (otpGapInput) {
      otpGapInput.addEventListener('input', () => {
        const val = Math.max(2, Math.min(20, parseInt(otpGapInput.value, 10) || 8));
        currentConfig.otp_buttons = currentConfig.otp_buttons || {};
        currentConfig.otp_buttons.gap = `${val}px`;
        applyLiveStylesToPreview();
      });
    }

    // Border Width Segmented Control
    const otpBorderBtns = document.querySelectorAll('#ctrl-otp-border-width-group .segmented-btn');
    otpBorderBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        otpBorderBtns.forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        currentConfig.otp_buttons = currentConfig.otp_buttons || {};
        currentConfig.otp_buttons.border_width = btn.dataset.border || '1px';
        applyLiveStylesToPreview();
      });
    });

    // Typography
    const fontSelect = document.getElementById('ctrl-font-family');
    if (fontSelect) {
      fontSelect.addEventListener('change', () => {
        currentConfig.typography = currentConfig.typography || {};
        currentConfig.typography.font_family = fontSelect.value;
        applyLiveStylesToPreview();
      });
    }

    const headingSizeSlider = document.getElementById('ctrl-heading-size');
    const headingSizeVal = document.getElementById('ctrl-heading-size-val');
    if (headingSizeSlider) {
      headingSizeSlider.addEventListener('input', () => {
        const val = `${headingSizeSlider.value}px`;
        if (headingSizeVal) headingSizeVal.textContent = val;
        currentConfig.typography = currentConfig.typography || {};
        currentConfig.typography.heading_size = val;
        applyLiveStylesToPreview();
      });
    }

    // Interactive State Simulator Buttons (Google Stitch)
    ['default', 'loading', 'error', 'success'].forEach((stateName) => {
      const stateBtn = document.getElementById(`state-${stateName}`);
      if (stateBtn) {
        stateBtn.addEventListener('click', () => {
          document.querySelectorAll('.state-btn').forEach((b) => b.classList.remove('active'));
          stateBtn.classList.add('active');
          applySimulatorState(stateName);
        });
      }
    });

    // Section 8: Authentication Checkboxes
    const authCheckboxes = [
      { id: 'ctrl-enable-pwd', key: 'enable_password' },
      { id: 'ctrl-enable-otp', key: 'enable_otp' },
      { id: 'ctrl-enable-email', key: 'enable_email' },
      { id: 'ctrl-enable-sms', key: 'enable_sms' },
      { id: 'ctrl-enable-whatsapp', key: 'enable_whatsapp' },
      { id: 'ctrl-remember-me', key: 'remember_me' },
      { id: 'ctrl-show-register', key: 'show_register' },
      { id: 'ctrl-show-forgot', key: 'show_forgot' },
    ];

    authCheckboxes.forEach(({ id, key }) => {
      const cb = document.getElementById(id);
      if (cb) {
        cb.addEventListener('change', () => {
          currentConfig.authentication = currentConfig.authentication || {};
          currentConfig.authentication[key] = cb.checked;
          applyLiveStylesToPreview();
        });
      }
    });
  }

  // --------------------------------------------------------------------------
  // SAVE CONFIGURATION MODAL & API
  // --------------------------------------------------------------------------
  const saveModal = document.getElementById('save-modal');
  const openSaveBtn = document.getElementById('btn-open-save-modal');
  const closeSaveBtn = document.getElementById('btn-close-save-modal');
  const cancelSaveBtn = document.getElementById('btn-cancel-save');
  const confirmSaveBtn = document.getElementById('btn-confirm-save');

  if (openSaveBtn && saveModal) {
    openSaveBtn.addEventListener('click', () => {
      saveModal.classList.add('open');
    });
  }

  [closeSaveBtn, cancelSaveBtn].forEach((btn) => {
    if (btn) {
      btn.addEventListener('click', () => {
        saveModal.classList.remove('open');
      });
    }
  });

  if (confirmSaveBtn) {
    confirmSaveBtn.addEventListener('click', async () => {
      const nameInput = document.getElementById('save-config-name');
      const name = (nameInput ? nameInput.value : '').trim() || 'Custom Auth Design';
      confirmSaveBtn.disabled = true;

      try {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
        const res = await fetch('/api/builder/configurations/save/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
          },
          body: JSON.stringify({
            config_id: activeConfigId,
            configuration_name: name,
            configuration_data: currentConfig,
          }),
        });

        const data = await res.json();
        if (data.success) {
          activeConfigId = data.config.id;
          const badge = document.getElementById('active-config-badge');
          if (badge) badge.textContent = data.config.name;
          showToast('Configuration saved successfully!');
          saveModal.classList.remove('open');
        } else {
          showToast(data.message || 'Failed to save configuration', true);
        }
      } catch (err) {
        showToast('Network error saving configuration', true);
      } finally {
        confirmSaveBtn.disabled = false;
      }
    });
  }

  // --------------------------------------------------------------------------
  // MANAGE CONFIGURATIONS MODAL & LIST
  // --------------------------------------------------------------------------
  const manageModal = document.getElementById('manage-modal');
  const openManageBtn = document.getElementById('btn-open-manage-modal');
  const closeManageBtn = document.getElementById('btn-close-manage-modal');
  const configListContainer = document.getElementById('saved-configs-list');

  if (openManageBtn && manageModal) {
    openManageBtn.addEventListener('click', async () => {
      manageModal.classList.add('open');
      await loadConfigurationsList();
    });
  }

  if (closeManageBtn && manageModal) {
    closeManageBtn.addEventListener('click', () => {
      manageModal.classList.remove('open');
    });
  }

  async function loadConfigurationsList() {
    if (!configListContainer) return;
    configListContainer.innerHTML = '<p style="color: var(--builder-text-muted); font-size: 0.85rem;">Loading configurations...</p>';

    try {
      const res = await fetch('/api/builder/configurations/');
      const data = await res.json();
      if (!data.success || !data.configurations.length) {
        configListContainer.innerHTML = '<p style="color: var(--builder-text-muted); font-size: 0.85rem;">No saved configurations found. Save your current design first!</p>';
        return;
      }

      configListContainer.innerHTML = '';
      data.configurations.forEach((cfg) => {
        const item = document.createElement('div');
        item.className = 'config-item';
        item.innerHTML = `
          <div class="config-item-info">
            <span class="config-item-title">${escapeHtml(cfg.name)}</span>
            <span class="config-item-meta">Template: ${cfg.template} &bull; Updated: ${cfg.updated_at.substring(0, 10)}</span>
          </div>
          <div class="config-item-actions">
            <button type="button" class="config-action-btn load-btn" data-id="${cfg.id}">Load</button>
            <button type="button" class="config-action-btn dup-btn" data-id="${cfg.id}">Clone</button>
            <button type="button" class="config-action-btn delete delete-btn" data-id="${cfg.id}">Delete</button>
          </div>
        `;
        configListContainer.appendChild(item);
      });

      // Bind item buttons
      configListContainer.querySelectorAll('.load-btn').forEach((btn) => {
        btn.addEventListener('click', () => loadConfig(btn.dataset.id));
      });
      configListContainer.querySelectorAll('.dup-btn').forEach((btn) => {
        btn.addEventListener('click', () => duplicateConfig(btn.dataset.id));
      });
      configListContainer.querySelectorAll('.delete-btn').forEach((btn) => {
        btn.addEventListener('click', () => deleteConfig(btn.dataset.id));
      });
    } catch (e) {
      configListContainer.innerHTML = '<p style="color: #ef4444; font-size: 0.85rem;">Failed to load configurations.</p>';
    }
  }

  function updateLogoUI(branding) {
    branding = branding || {};
    const previewBox = document.getElementById('dropzone-preview-box');
    const emptyPrompt = document.getElementById('dropzone-empty-prompt');
    const previewImg = document.getElementById('logo-preview-img');
    const previewName = document.getElementById('logo-preview-name');
    const previewSize = document.getElementById('logo-preview-size');

    if (branding.logo_url) {
      if (previewBox) previewBox.style.display = 'flex';
      if (emptyPrompt) emptyPrompt.style.display = 'none';
      if (previewImg) previewImg.src = branding.logo_url;
      if (previewName) previewName.textContent = branding._logo_filename || 'Custom Brand Logo';
      if (previewSize) previewSize.textContent = branding._logo_filesize || 'Active';
    } else {
      if (previewBox) previewBox.style.display = 'none';
      if (emptyPrompt) emptyPrompt.style.display = 'flex';
      if (previewImg) previewImg.src = '';
    }
  }

  function syncSidebarControlsFromConfig(config) {
    if (!config) return;

    // Template Selector
    const tplSelect = document.getElementById('ctrl-template-select');
    if (tplSelect && config.template) {
      tplSelect.value = config.template;
    }
    const activeTemplate = config.template || 'modern';
    document.querySelectorAll('.style-pill-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.template === activeTemplate);
    });

    // Colors
    const colors = config.colors || {};
    ['primary', 'secondary', 'background', 'card_bg', 'text', 'muted', 'border'].forEach((colorKey) => {
      const picker = document.getElementById(`ctrl-color-${colorKey}`);
      const text = document.getElementById(`ctrl-color-${colorKey}-text`);
      if (colors[colorKey]) {
        if (picker) picker.value = colors[colorKey];
        if (text) text.value = colors[colorKey];
      }
    });

    const surfaceSelect = document.getElementById('card-surface-select');
    if (surfaceSelect && colors.card_bg) {
      surfaceSelect.value = colors.card_bg;
    }

    // Sliders
    const sliders = [
      { id: 'ctrl-card-width', val: config.card?.width },
      { id: 'ctrl-card-radius', val: config.card?.radius },
      { id: 'ctrl-input-height', val: config.inputs?.height },
      { id: 'ctrl-btn-height', val: config.buttons?.height },
    ];
    sliders.forEach(({ id, val }) => {
      if (val) {
        const num = parseInt(val, 10);
        const slider = document.getElementById(id);
        const disp = document.getElementById(`${id}-val`);
        if (slider && !isNaN(num)) slider.value = num;
        if (disp) disp.textContent = val;
      }
    });

    // Branding & Logo
    const branding = config.branding || {};
    const bn = document.getElementById('ctrl-brand-name');
    if (bn) {
      bn.value = branding.brand_name !== undefined ? branding.brand_name : 'Auth Platform';
    }
    updateLogoUI(branding);

    // Logo Alignment
    const align = branding.logo_align || 'center';
    document.querySelectorAll('#ctrl-logo-align-group .segmented-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.align === align);
    });

    // Aspect ratio toggle
    const aspectToggle = document.getElementById('ctrl-logo-aspect-ratio');
    if (aspectToggle) {
      aspectToggle.checked = branding.maintain_aspect_ratio !== false;
    }

    // Logo Width & Height
    const lw = document.getElementById('ctrl-logo-width');
    if (lw) lw.value = parseInt(branding.logo_width, 10) || 120;

    const lh = document.getElementById('ctrl-logo-height');
    if (lh) lh.value = parseInt(branding.logo_height, 10) || 36;

    // Logo Scale
    const ls = document.getElementById('ctrl-logo-scale');
    const lsVal = document.getElementById('ctrl-logo-scale-val');
    const scaleNum = parseInt(branding.logo_scale, 10) || 100;
    if (ls) ls.value = scaleNum;
    if (lsVal) lsVal.textContent = `${scaleNum}%`;

    // OTP Button Controls
    const otp = config.otp_buttons || {
      width_mode: 'auto',
      custom_width: '100px',
      height: '38px',
      icon_size: '16px',
      font_size: '12px',
      radius: '6px',
      gap: '8px',
      border_width: '1px',
    };

    // OTP Width Mode
    const widthMode = otp.width_mode || 'auto';
    document.querySelectorAll('#ctrl-otp-width-mode-group .segmented-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.mode === widthMode);
    });
    const customWidthRow = document.getElementById('ctrl-otp-custom-width-row');
    if (customWidthRow) {
      customWidthRow.style.display = widthMode === 'custom' ? 'flex' : 'none';
    }

    // OTP Custom Width
    const ocw = document.getElementById('ctrl-otp-custom-width');
    if (ocw) ocw.value = parseInt(otp.custom_width, 10) || 100;

    // OTP Height
    const oh = document.getElementById('ctrl-otp-height');
    const ohVal = document.getElementById('ctrl-otp-height-val');
    const heightNum = parseInt(otp.height, 10) || 38;
    if (oh) oh.value = heightNum;
    if (ohVal) ohVal.textContent = `${heightNum}px`;

    // OTP Icon Size
    const iconSize = otp.icon_size || '16px';
    document.querySelectorAll('#ctrl-otp-icon-size-group .segmented-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.size === iconSize);
    });

    // OTP Font Size
    const ofs = document.getElementById('ctrl-otp-font-size');
    if (ofs) ofs.value = parseInt(otp.font_size, 10) || 12;

    // OTP Radius
    const orad = document.getElementById('ctrl-otp-radius');
    if (orad) orad.value = parseInt(otp.radius, 10) || 6;

    // OTP Gap
    const ogap = document.getElementById('ctrl-otp-gap');
    if (ogap) ogap.value = parseInt(otp.gap, 10) || 8;

    // OTP Border Width
    const borderWidth = otp.border_width || '1px';
    document.querySelectorAll('#ctrl-otp-border-width-group .segmented-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.border === borderWidth);
    });

    // Typography
    if (config.typography?.font_family) {
      const ff = document.getElementById('ctrl-font-family');
      if (ff) ff.value = config.typography.font_family;
    }
    if (config.typography?.heading_size) {
      const hs = document.getElementById('ctrl-heading-size');
      const hsVal = document.getElementById('ctrl-heading-size-val');
      const hsNum = parseInt(config.typography.heading_size, 10);
      if (hs && !isNaN(hsNum)) hs.value = hsNum;
      if (hsVal) hsVal.textContent = config.typography.heading_size;
    }

    // Authentication Checkboxes
    const auth = config.authentication || {};
    const authList = [
      { id: 'ctrl-enable-pwd', val: auth.enable_password !== false },
      { id: 'ctrl-enable-otp', val: auth.enable_otp !== false },
      { id: 'ctrl-enable-email', val: auth.enable_email !== false },
      { id: 'ctrl-enable-sms', val: auth.enable_sms !== false },
      { id: 'ctrl-enable-whatsapp', val: auth.enable_whatsapp !== false },
      { id: 'ctrl-remember-me', val: auth.remember_me !== false },
      { id: 'ctrl-show-register', val: auth.show_register !== false },
      { id: 'ctrl-show-forgot', val: auth.show_forgot !== false },
    ];
    authList.forEach(({ id, val }) => {
      const cb = document.getElementById(id);
      if (cb) cb.checked = val;
    });
  }

  async function loadConfig(id) {
    try {
      const res = await fetch(`/api/builder/configurations/${id}/load/`);
      const data = await res.json();
      if (data.success) {
        currentConfig = data.configuration.data;
        activeConfigId = data.configuration.id;
        const badge = document.getElementById('active-config-badge');
        if (badge) badge.textContent = data.configuration.name;
        syncSidebarControlsFromConfig(currentConfig);
        updatePreviewUrl();
        manageModal.classList.remove('open');
        showToast(`Loaded "${data.configuration.name}" (Applied to main site!)`);
      } else {
        showToast(data.message, true);
      }
    } catch (e) {
      showToast('Error loading configuration', true);
    }
  }

  async function duplicateConfig(id) {
    try {
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
      const res = await fetch(`/api/builder/configurations/${id}/duplicate/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken },
      });
      const data = await res.json();
      if (data.success) {
        showToast('Configuration cloned!');
        await loadConfigurationsList();
      }
    } catch (e) {
      showToast('Error cloning configuration', true);
    }
  }

  async function deleteConfig(id) {
    if (!confirm('Are you sure you want to delete this configuration?')) return;
    try {
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
      const res = await fetch(`/api/builder/configurations/${id}/delete/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken },
      });
      const data = await res.json();
      if (data.success) {
        showToast('Configuration deleted');
        await loadConfigurationsList();
      }
    } catch (e) {
      showToast('Error deleting configuration', true);
    }
  }

  // --------------------------------------------------------------------------
  // APPLY TO MAIN SITE ACTION
  // --------------------------------------------------------------------------
  const applyMainBtn = document.getElementById('btn-apply-main');
  if (applyMainBtn) {
    applyMainBtn.addEventListener('click', async () => {
      applyMainBtn.disabled = true;
      applyMainBtn.textContent = 'Applying...';

      try {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
        const res = await fetch('/api/builder/configurations/apply/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
          },
          body: JSON.stringify({
            config_id: activeConfigId,
            configuration: currentConfig,
          }),
        });

        const data = await res.json();
        if (data.success) {
          showToast('Applied to main site successfully! All main pages now reflect your changes.');
        } else {
          showToast(data.message || 'Failed to apply configuration', true);
        }
      } catch (err) {
        showToast('Error applying configuration to main site', true);
      } finally {
        applyMainBtn.disabled = false;
        applyMainBtn.textContent = 'Apply to Main';
      }
    });
  }

  // --------------------------------------------------------------------------
  // EXPORT ZIP
  // --------------------------------------------------------------------------
  const exportBtn = document.getElementById('btn-export-zip');
  if (exportBtn) {
    exportBtn.addEventListener('click', async () => {
      exportBtn.disabled = true;
      exportBtn.textContent = 'Generating ZIP...';

      try {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
        const res = await fetch('/api/builder/export-zip/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
          },
          body: JSON.stringify({
            template: currentConfig.template || 'modern',
            configuration: currentConfig,
          }),
        });

        if (!res.ok) {
          throw new Error('ZIP generation failed');
        }

        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = `auth-platform-${currentConfig.template || 'custom'}.zip`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        showToast('ZIP Project downloaded successfully!');
      } catch (err) {
        showToast('Failed to export ZIP package', true);
      } finally {
        exportBtn.disabled = false;
        exportBtn.textContent = 'Export ZIP';
      }
    });
  }

  // --------------------------------------------------------------------------
  // RESET TO DEFAULTS
  // --------------------------------------------------------------------------
  const resetBtn = document.getElementById('btn-reset-defaults');
  if (resetBtn) {
    resetBtn.addEventListener('click', async () => {
      if (confirm('Reset current configuration to template defaults?')) {
        const tpl = currentConfig.template || 'modern';
        currentConfig = {
          template: tpl,
          authentication: {
            enable_password: true,
            enable_otp: true,
            enable_email: true,
            enable_sms: true,
            enable_whatsapp: true,
            remember_me: true,
            show_register: true,
            show_forgot: true,
          },
        };
        activeConfigId = null;
        const badge = document.getElementById('active-config-badge');
        if (badge) badge.textContent = `Default ${tpl.charAt(0).toUpperCase() + tpl.slice(1)}`;
        syncSidebarControlsFromConfig(currentConfig);
        updatePreviewUrl();

        try {
          const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
          await fetch('/api/builder/configurations/reset/', {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken },
          });
        } catch (e) {}

        showToast('Reset to defaults and restored main site defaults.');
      }
    });
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // Initialize
  syncSidebarControlsFromConfig(currentConfig);
  bindInputs();

  // Handle URL query parameters (e.g. ?template=split, ?action=export)
  try {
    const urlParams = new URLSearchParams(window.location.search);
    const paramTemplate = urlParams.get('template');
    if (paramTemplate && ['modern', 'split', 'corporate'].includes(paramTemplate)) {
      currentConfig.template = paramTemplate;
      const tplSelect = document.getElementById('ctrl-template-select');
      if (tplSelect) tplSelect.value = paramTemplate;
      document.querySelectorAll('.style-pill-btn').forEach((b) => {
        b.classList.toggle('active', b.dataset.template === paramTemplate);
      });
      updatePreviewUrl();
    }
    const paramAction = urlParams.get('action');
    if (paramAction === 'export') {
      const expBtn = document.getElementById('btn-export-zip');
      if (expBtn) setTimeout(() => expBtn.click(), 400);
    }
  } catch (e) {}

  // Ensure live styles and logo are applied immediately if iframe is already loaded
  if (previewFrame && previewFrame.contentDocument && (previewFrame.contentDocument.readyState === 'complete' || previewFrame.contentDocument.readyState === 'interactive')) {
    applyLiveStylesToPreview();
  }
})();
