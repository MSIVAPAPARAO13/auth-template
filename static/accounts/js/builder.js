/**
 * Custom Builder Client Controller (Phases 10 & 11)
 * Live CSS variable manipulation, iframe preview synchronization,
 * and AJAX integration for saving, loading, duplicating, and exporting configurations.
 */

(function () {
  'use strict';

  let currentConfig = window.initialConfig || {};
  window.currentConfig = currentConfig;
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

  function hexToRgba(hex, alpha) {
    if (!hex) return `rgba(255, 255, 255, ${alpha})`;
    let h = String(hex).trim().replace('#', '');
    if (h.length === 3) h = h.split('').map((c) => c + c).join('');
    if (h.length !== 6) return `rgba(255, 255, 255, ${alpha})`;
    const r = parseInt(h.substring(0, 2), 16) || 0;
    const g = parseInt(h.substring(2, 4), 16) || 0;
    const b = parseInt(h.substring(4, 6), 16) || 0;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
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
      frameWrapper.className = `preview-frame-wrapper preview-viewport mode-${mode}`;
      setTimeout(fitPreviewCard, 150);
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

      // --- THEME MODE SYNCHRONIZATION ---
      currentConfig.theme = currentConfig.theme || { mode: 'dark' };
      const themeMode = (currentConfig.theme.mode || 'dark').toLowerCase();
      root.setAttribute('data-theme', themeMode);
      if (doc.body) doc.body.setAttribute('data-theme', themeMode);

      // System preference tracking
      const isSystemMode = themeMode === 'system';
      const systemPrefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      const isLightEffective = themeMode === 'light' || (isSystemMode && !systemPrefersDark);

      if (isSystemMode) {
        root.classList.toggle('system-dark', systemPrefersDark);
        root.classList.toggle('system-light', !systemPrefersDark);
        if (doc.body) {
          doc.body.classList.toggle('system-dark', systemPrefersDark);
          doc.body.classList.toggle('system-light', !systemPrefersDark);
        }
      } else {
        root.classList.remove('system-dark', 'system-light');
        if (doc.body) doc.body.classList.remove('system-dark', 'system-light');
      }

      const themeDefaults = isLightEffective ? {
        bg: '#F5F6F8',
        card_bg: '#FFFFFF',
        text: '#17181A',
        muted: '#656970',
        input_bg: '#FFFFFF',
        input_border: '#D7DADF',
        input_text: '#17181A',
        btn_bg: '#17181A',
        btn_text: '#FFFFFF',
        border: '#E2E5EA',
        focus_ring: 'rgba(23, 24, 26, 0.15)',
        tab_bg: '#EDEFF2',
        tab_border: '#D7DADF',
        tab_active_bg: '#FFFFFF',
        tab_active_text: '#17181A',
        otp_bg: '#FFFFFF',
        otp_border: '#D7DADF',
        otp_text: '#17181A',
        otp_active_bg: '#EDEFF2',
        otp_active_border: '#17181A',
      } : {
        bg: '#111214',
        card_bg: '#1B1D21',
        text: '#F5F5F5',
        muted: '#A7A7A7',
        input_bg: '#15171A',
        input_border: '#34373C',
        input_text: '#F5F5F5',
        btn_bg: '#FFFFFF',
        btn_text: '#111111',
        border: 'rgba(255, 255, 255, 0.08)',
        focus_ring: 'rgba(255, 255, 255, 0.2)',
        tab_bg: '#15171A',
        tab_border: '#34373C',
        tab_active_bg: '#2A2C30',
        tab_active_text: '#F5F5F5',
        otp_bg: '#15171A',
        otp_border: '#34373C',
        otp_text: '#F5F5F5',
        otp_active_bg: '#2A2C30',
        otp_active_border: '#FFFFFF',
      };

      root.style.setProperty('--theme-mode', themeMode);
      root.style.setProperty('--tab-bg', themeDefaults.tab_bg);
      root.style.setProperty('--tab-border', themeDefaults.tab_border);
      root.style.setProperty('--tab-active-bg', themeDefaults.tab_active_bg);
      root.style.setProperty('--tab-active-text', themeDefaults.tab_active_text);
      root.style.setProperty('--otp-channel-bg', themeDefaults.otp_bg);
      root.style.setProperty('--otp-channel-border', themeDefaults.otp_border);
      root.style.setProperty('--otp-channel-text', themeDefaults.otp_text);
      root.style.setProperty('--otp-channel-active-bg', themeDefaults.otp_active_bg);
      root.style.setProperty('--otp-channel-active-border', themeDefaults.otp_active_border);

      // --- PALETTE RESOLUTION & DESIGN TOKENS ---
      const paletteSetting = currentConfig.palette || {};
      const paletteKey = paletteSetting.preset || 'indigo';
      const palettes = window.colorPalettes || {};
      const chosenPalette = palettes[paletteKey] || palettes['indigo'] || {};
      const paletteTokens = isLightEffective ? (chosenPalette.light || {}) : (chosenPalette.dark || {});
      const customColors = paletteSetting.custom_colors || {};

      const primaryCol = colors.primary || customColors.primary || paletteTokens.primary || (isLightEffective ? '#17181A' : '#FFFFFF');
      const primaryHoverCol = colors.primary_hover || customColors.primary_hover || paletteTokens.primary_hover || primaryCol;
      const bgCol = colors.background || customColors.background || paletteTokens.bg || themeDefaults.bg;
      const surfaceCol = card.background_color || colors.card_bg || customColors.card_bg || paletteTokens.surface || themeDefaults.card_bg;
      const textCol = colors.text || customColors.text || paletteTokens.text || themeDefaults.text;
      const textMutedCol = colors.muted || customColors.text_muted || paletteTokens.text_muted || themeDefaults.muted;
      const borderCol = card.border_color || colors.border || customColors.border || paletteTokens.border || themeDefaults.border;

      // Centralized Design System CSS tokens
      root.style.setProperty('--color-primary', primaryCol);
      root.style.setProperty('--color-primary-hover', primaryHoverCol);
      root.style.setProperty('--color-bg', bgCol);
      root.style.setProperty('--color-surface', surfaceCol);
      root.style.setProperty('--color-surface-elevated', paletteTokens.surface_elevated || surfaceCol);
      root.style.setProperty('--color-text', textCol);
      root.style.setProperty('--color-text-muted', textMutedCol);
      root.style.setProperty('--color-border', borderCol);

      root.style.setProperty('--background-color', bgCol);
      root.style.setProperty('--card-background', surfaceCol);
      root.style.setProperty('--card-bg-color', surfaceCol);
      root.style.setProperty('--text-color', textCol);
      root.style.setProperty('--muted-color', textMutedCol);
      root.style.setProperty('--border-color', borderCol);
      root.style.setProperty('--btn-primary-bg', buttons.bg || colors.btn_bg || primaryCol);
      root.style.setProperty('--btn-primary-text', buttons.text_color || colors.btn_text || (isLightEffective ? '#FFFFFF' : '#111111'));
      root.style.setProperty('--input-bg', inputs.bg || themeDefaults.input_bg);
      root.style.setProperty('--input-border', inputs.border || borderCol);
      root.style.setProperty('--input-text-color', inputs.text_color || textCol);
      root.style.setProperty('--focus-ring', inputs.focus_ring || themeDefaults.focus_ring);

      root.style.setProperty('--primary-color', primaryCol);
      root.style.setProperty('--primary-hover', primaryHoverCol);
      if (colors.secondary) root.style.setProperty('--secondary-color', colors.secondary);

      // --- COMPONENT PRESETS REFLECTION ---
      // Density
      const spacingSetting = currentConfig.spacing || {};
      const density = spacingSetting.density || 'comfortable';
      ['density-compact', 'density-comfortable', 'density-spacious'].forEach(c => doc.body && doc.body.classList.remove(c));
      if (doc.body) doc.body.classList.add(`density-${density}`);

      // Type scale
      const typeScale = typography.scale || 'modern';
      ['type-scale-modern', 'type-scale-minimal', 'type-scale-compact', 'type-scale-editorial', 'type-scale-enterprise'].forEach(c => doc.body && doc.body.classList.remove(c));
      if (doc.body) doc.body.classList.add(`type-scale-${typeScale}`);

      // Card Preset
      const cardPreset = card.preset || 'default';
      const cardElements = doc.querySelectorAll('.auth-card, .corporate-card, .split-card');
      cardElements.forEach(c => {
        ['card-style-default', 'card-style-minimal', 'card-style-soft', 'card-style-elevated', 'card-style-glass', 'card-style-bordered'].forEach(cls => c.classList.remove(cls));
        c.classList.add(`card-style-${cardPreset}`);
      });

      // Button Preset
      const btnPreset = buttons.preset || 'solid';
      const btnElements = doc.querySelectorAll('.btn-primary, .btn-submit, .btn-submit-main, button[type="submit"]');
      btnElements.forEach(b => {
        ['btn-style-solid', 'btn-style-soft', 'btn-style-outline', 'btn-style-ghost', 'btn-style-gradient', 'btn-style-pill', 'btn-style-sharp'].forEach(cls => b.classList.remove(cls));
        b.classList.add(`btn-style-${btnPreset}`);
      });

      // Input Preset
      const inputPreset = inputs.preset || 'minimal';
      const inputElements = doc.querySelectorAll('.form-control, .input-stitch, input[type="text"], input[type="password"], input[type="email"], input[type="tel"]');
      inputElements.forEach(i => {
        ['input-style-minimal', 'input-style-bordered', 'input-style-filled', 'input-style-soft', 'input-style-glass'].forEach(cls => i.classList.remove(cls));
        i.classList.add(`input-style-${inputPreset}`);
      });

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
      if (typography.body_size) {
        root.style.setProperty('--body-size', typography.body_size);
        const subtitles = doc.querySelectorAll('.auth-subtitle, p');
        subtitles.forEach((p) => {
          if (!p.closest('.alert-box')) p.style.fontSize = typography.body_size;
        });
      }
      if (typography.align) {
        const headers = doc.querySelectorAll('.auth-header');
        headers.forEach((h) => {
          h.style.textAlign = typography.align;
        });
      }

      // --- BACKGROUND SETTINGS ---
      const bg = currentConfig.background || {};
      const bgType = bg.type || 'color';

      if (bgType === 'color') {
        const c = bg.color || colors.background || '#131315';
        root.style.setProperty('--auth-bg-color', c);
        root.style.setProperty('--auth-bg-image', 'none');
      } else if (bgType === 'gradient') {
        const grad = bg.gradient || {};
        const gType = grad.type || 'linear';
        const gStart = grad.start_color || '#0f172a';
        const gEnd = grad.end_color || '#1e1b4b';
        const gAngle = grad.angle !== undefined ? `${grad.angle}deg` : '135deg';
        const gradCss = gType === 'radial'
          ? `radial-gradient(circle at center, ${gStart} 0%, ${gEnd} 100%)`
          : `linear-gradient(${gAngle}, ${gStart} 0%, ${gEnd} 100%)`;
        root.style.setProperty('--auth-bg-color', gStart);
        root.style.setProperty('--auth-bg-image', gradCss);
      } else if (bgType === 'image') {
        if (bg.image_url) {
          root.style.setProperty('--auth-bg-image', `url("${bg.image_url}")`);
        } else {
          root.style.setProperty('--auth-bg-image', 'none');
        }
      }

      const bgPosMap = {
        center: 'center center',
        top: 'center top',
        bottom: 'center bottom',
        left: 'left center',
        right: 'right center',
        'top-left': 'left top',
        'top left': 'left top',
        'top-right': 'right top',
        'top right': 'right top',
        'bottom-left': 'left bottom',
        'bottom left': 'left bottom',
        'bottom-right': 'right bottom',
        'bottom right': 'right bottom',
      };
      root.style.setProperty('--auth-bg-position', bgPosMap[bg.position] || bg.position || 'center center');
      root.style.setProperty('--auth-bg-size', bg.size || 'cover');
      root.style.setProperty('--auth-bg-repeat', bg.repeat || 'no-repeat');

      // Background Overlay
      const overlay = bg.overlay || {};
      const overlayColor = overlay.color || '#000000';
      const overlayOpacity = (overlay.opacity !== undefined ? overlay.opacity : 40) / 100;
      let overlayRgba = overlayColor;
      if (overlayColor.startsWith('#') && overlayColor.length === 7) {
        const r = parseInt(overlayColor.slice(1, 3), 16);
        const g = parseInt(overlayColor.slice(3, 5), 16);
        const b = parseInt(overlayColor.slice(5, 7), 16);
        overlayRgba = `rgba(${r}, ${g}, ${b}, ${overlayOpacity})`;
      }
      root.style.setProperty('--auth-bg-overlay-color', overlayRgba);

      // Background Effects
      root.style.setProperty('--auth-bg-filter-blur', `${bg.blur || 0}px`);
      root.style.setProperty('--auth-bg-filter-brightness', `${bg.brightness !== undefined ? bg.brightness : 100}%`);
      root.style.setProperty('--auth-bg-filter-saturation', `${bg.saturation !== undefined ? bg.saturation : 100}%`);

      // --- CARD STYLE & TRANSPARENCY SETTINGS ---
      const appearance = card.appearance || (card.preset === 'glass' ? 'glass' : 'opaque');
      root.style.setProperty('--card-appearance', appearance);

      // Card surface color + opacity -> RGBA
      const cardBaseCol = card.background_color || card.card_bg || '#201f22';
      let cardAlpha = 1.0;
      if (card.opacity !== undefined) {
        cardAlpha = Math.max(0, Math.min(100, parseInt(card.opacity, 10))) / 100;
      } else if (appearance === 'translucent') {
        cardAlpha = 0.45;
      } else if (appearance === 'glass') {
        cardAlpha = 0.25;
      }
      const cardBgSurface = hexToRgba(cardBaseCol, cardAlpha);
      root.style.setProperty('--card-bg-surface', cardBgSurface);
      root.style.setProperty('--card-background', cardBgSurface);
      root.style.setProperty('--card-bg-color', cardBgSurface);
      root.style.setProperty('--card-opacity', '1'); // Keeps DOM card elements 100% opaque
      root.style.setProperty('--card-surface-alpha', cardAlpha.toFixed(2));

      // Backdrop blur (only blurs background behind card)
      let cardBlurVal = 0;
      if (card.backdrop_blur !== undefined) {
        cardBlurVal = Math.max(0, Math.min(30, parseInt(card.backdrop_blur, 10) || 0));
      } else if (card.blur !== undefined) {
        cardBlurVal = Math.max(0, Math.min(30, parseInt(card.blur, 10) || 0));
      } else if (appearance === 'glass') {
        cardBlurVal = 14;
      }
      root.style.setProperty('--card-backdrop-blur', `${cardBlurVal}px`);
      root.style.setProperty('--card-blur', `${cardBlurVal}px`);

      // Border settings
      const borderEnabled = card.border_enabled !== false;
      if (!borderEnabled) {
        root.style.setProperty('--card-border-width', '0px');
        root.style.setProperty('--card-border-color', 'transparent');
      } else {
        const bWidth = card.border_width !== undefined ? Math.max(1, Math.min(3, parseInt(card.border_width, 10) || 1)) : 1;
        root.style.setProperty('--card-border-width', `${bWidth}px`);
        const bAlpha = card.border_opacity !== undefined ? (Math.max(0, Math.min(100, parseInt(card.border_opacity, 10))) / 100) : (appearance === 'glass' ? 0.25 : 0.35);
        const bColor = card.border_color || '#ffffff';
        root.style.setProperty('--card-border-color', hexToRgba(bColor, bAlpha));
      }

      if (card.width) root.style.setProperty('--card-width', card.width);
      if (card.padding) root.style.setProperty('--card-padding', card.padding);
      if (card.border_radius) root.style.setProperty('--card-border-radius', card.border_radius);

      // Card Shadow Preset
      const shadowIntensity = card.shadow || (appearance === 'glass' ? 'medium' : 'subtle');
      let shadowCss = '0 12px 40px rgba(0, 0, 0, 0.5)';
      if (shadowIntensity === 'none') shadowCss = 'none';
      else if (shadowIntensity === 'subtle') shadowCss = '0 4px 16px rgba(0, 0, 0, 0.25)';
      else if (shadowIntensity === 'medium') shadowCss = '0 12px 40px rgba(0, 0, 0, 0.5)';
      else if (shadowIntensity === 'strong') shadowCss = '0 24px 60px rgba(0, 0, 0, 0.8), 0 0 0 1px rgba(255, 255, 255, 0.1)';
      root.style.setProperty('--card-shadow', shadowCss);

      // --- CARD POSITIONING & PLACEMENT ---
      const layout = currentConfig.layout || {};
      const cardPos = layout.card_position || card.position || 'center';
      const rawCardX = layout.card_horizontal_position !== undefined ? layout.card_horizontal_position : (card.horizontal_position !== undefined ? card.horizontal_position : 50);
      const rawCardY = layout.card_vertical_position !== undefined ? layout.card_vertical_position : (card.vertical_position !== undefined ? card.vertical_position : 50);
      const parsedCardX = parseInt(rawCardX, 10);
      const cardX = Math.max(0, Math.min(100, isNaN(parsedCardX) ? 50 : parsedCardX));
      const parsedCardY = parseInt(rawCardY, 10);
      const cardY = Math.max(0, Math.min(100, isNaN(parsedCardY) ? 50 : parsedCardY));

      root.style.setProperty('--card-position', cardPos);
      root.style.setProperty('--card-x', `${cardX}%`);
      root.style.setProperty('--card-y', `${cardY}%`);
      root.style.setProperty('--card-x-pct', cardX);
      root.style.setProperty('--card-y-pct', cardY);

      // Card Alignment
      const authWrappers = doc.querySelectorAll('.auth-wrapper');
      authWrappers.forEach((wrap) => {
        if (card.alignment === 'left') {
          wrap.style.margin = '0 auto 0 0';
        } else if (card.alignment === 'right') {
          wrap.style.margin = '0 0 0 auto';
        } else {
          wrap.style.margin = '0 auto';
        }
      });

      // --- CARD ENTRANCE ANIMATIONS ---
      const anims = currentConfig.animations || {};
      const animType = anims.type || 'none';
      const animTypeMap = {
        none: 'none',
        fade: 'animFade',
        slide_up: 'animSlideUp',
        slide_down: 'animSlideDown',
        scale: 'animScale',
        float: 'animFloat',
      };
      root.style.setProperty('--card-animation-name', animTypeMap[animType] || 'none');
      root.style.setProperty('--card-animation-duration', `${anims.duration || 250}ms`);
      root.style.setProperty('--card-animation-delay', `${anims.delay || 0}ms`);

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

      // Fit preview card naturally inside the viewport
      fitPreviewCard();
    } catch (e) {
      if (window.console && window.console.warn) {
        console.warn('[Builder Preview] Error applying live styles to iframe preview:', e);
      }
    }
  }

  // --------------------------------------------------------------------------
  // INTELLIGENT CARD AUTO-FIT FOR PREVIEW VIEWPORT
  // Ensures card always fits naturally within preview frame without scrollbars
  // --------------------------------------------------------------------------
  function fitPreviewCard() {
    try {
      const doc = previewFrame.contentDocument || previewFrame.contentWindow.document;
      if (!doc || !doc.body) return;

      const authWrapper = doc.querySelector('.auth-wrapper');
      const corpSection = doc.querySelector('.corp-form-section');
      const splitContainer = doc.querySelector('.split-container');
      const target = authWrapper || corpSection;

      if (!target && !splitContainer) return;

      const viewportHeight = doc.documentElement.clientHeight || window.innerHeight;

      if (splitContainer) {
        const contentHeight = splitContainer.scrollHeight;
        if (contentHeight > viewportHeight && viewportHeight > 300) {
          const scale = Math.min(1.0, Math.max(0.75, (viewportHeight - 20) / contentHeight));
          splitContainer.style.transform = scale < 0.99 ? `scale(${scale.toFixed(3)})` : '';
          splitContainer.style.transformOrigin = 'top center';
        } else {
          splitContainer.style.transform = '';
        }
        return;
      }

      // Standard card layout: scale inner card element so outer wrapper positioning transform is preserved
      const cardEl = (target && target.querySelector('.auth-card, .corp-auth-card')) || target;
      if (cardEl && cardEl !== target) {
        const cardHeight = cardEl.scrollHeight || cardEl.offsetHeight;
        const availableHeight = viewportHeight - 32;
        if (cardHeight > availableHeight && availableHeight > 250) {
          const scale = Math.min(1.0, Math.max(0.72, availableHeight / cardHeight));
          cardEl.style.transform = scale < 0.99 ? `scale(${scale.toFixed(3)})` : '';
          cardEl.style.transformOrigin = 'center center';
        } else {
          cardEl.style.transform = '';
        }
      }
    } catch (e) {
      // Cross-origin or silent fallback
    }
  }

  previewFrame.addEventListener('load', () => {
    applyLiveStylesToPreview();
    setTimeout(fitPreviewCard, 100);
  });

  // --------------------------------------------------------------------------
  // STATE SIMULATOR (Google Stitch)
  // --------------------------------------------------------------------------
  function applySimulatorState(state) {
    try {
      const doc = previewFrame.contentDocument || previewFrame.contentWindow.document;
      if (!doc) return;
      const submitBtn = doc.querySelector('.btn-primary, .corp-btn-primary, .split-btn-primary, button[type="submit"], #password-submit-btn, #send-otp-btn');
      let alertBox = doc.querySelector('.alert-box:not(.demo-banner), .corp-alert-box, .split-alert-box');
      let alertContainer = doc.querySelector('.alert-container, .corp-form-section, .split-auth-col, .auth-body, form');

      if (!alertContainer) {
        alertContainer = doc.querySelector('.auth-card, .corp-auth-card, .split-auth-card, form') || doc.body;
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
          alertContainer.insertBefore(alertBox, alertContainer.firstChild);
        }
        if (alertBox) {
          alertBox.className = 'alert-box alert-error';
          alertBox.textContent = 'Invalid credentials. Please verify and try again.';
        }
      } else if (state === 'success') {
        if (submitBtn) submitBtn.classList.remove('is-loading');
        if (!alertBox && alertContainer) {
          alertBox = doc.createElement('div');
          alertContainer.insertBefore(alertBox, alertContainer.firstChild);
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

    // 1. DESIGN PRESETS (1-Click Complete Design Systems)
    document.querySelectorAll('#design-presets-container .preset-card').forEach((btn) => {
      btn.addEventListener('click', () => {
        const presetKey = btn.dataset.preset;
        if (!presetKey) return;
        const presets = window.designPresets || {};
        const preset = presets[presetKey];
        if (!preset) return;

        currentConfig.design_preset = presetKey;
        if (preset.theme_mode) {
          currentConfig.theme = currentConfig.theme || {};
          currentConfig.theme.mode = preset.theme_mode;
        }
        if (preset.palette) {
          currentConfig.palette = currentConfig.palette || {};
          currentConfig.palette.preset = preset.palette;
          delete currentConfig.palette.custom_colors;
        }
        if (preset.card) {
          currentConfig.card = Object.assign({}, currentConfig.card || {}, preset.card);
        }
        if (preset.buttons) {
          currentConfig.buttons = Object.assign({}, currentConfig.buttons || {}, preset.buttons);
        }
        if (preset.inputs) {
          currentConfig.inputs = Object.assign({}, currentConfig.inputs || {}, preset.inputs);
        }
        if (preset.typography) {
          currentConfig.typography = Object.assign({}, currentConfig.typography || {}, preset.typography);
        }
        if (preset.spacing) {
          currentConfig.spacing = Object.assign({}, currentConfig.spacing || {}, preset.spacing);
        }
        if (preset.animations) {
          currentConfig.animations = Object.assign({}, currentConfig.animations || {}, preset.animations);
        }

        currentConfig.colors = currentConfig.colors || {};
        delete currentConfig.colors.primary;
        delete currentConfig.colors.background;
        delete currentConfig.colors.card_bg;
        delete currentConfig.colors.text;
        delete currentConfig.colors.muted;
        delete currentConfig.colors.border;

        document.querySelectorAll('#design-presets-container .preset-card').forEach((b) => {
          b.classList.toggle('active', b.dataset.preset === presetKey);
        });

        syncSidebarControlsFromConfig(currentConfig);
        applyLiveStylesToPreview();
        showToast(`Applied "${preset.name}" design preset!`);
      });
    });

    // 2. COLOR PALETTES (10 Curated Palettes)
    document.querySelectorAll('#color-palettes-container .palette-swatch-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const palKey = btn.dataset.palette;
        if (!palKey) return;
        currentConfig.palette = currentConfig.palette || {};
        currentConfig.palette.preset = palKey;
        delete currentConfig.palette.custom_colors;

        currentConfig.colors = currentConfig.colors || {};
        delete currentConfig.colors.primary;
        delete currentConfig.colors.background;
        delete currentConfig.colors.card_bg;
        delete currentConfig.colors.text;
        delete currentConfig.colors.muted;
        delete currentConfig.colors.border;

        document.querySelectorAll('#color-palettes-container .palette-swatch-btn').forEach((b) => {
          b.classList.toggle('active', b.dataset.palette === palKey);
        });

        syncSidebarControlsFromConfig(currentConfig);
        applyLiveStylesToPreview();
      });
    });

    // Reset Primary to Active Palette
    const resetPaletteBtn = document.getElementById('btn-reset-palette-primary');
    if (resetPaletteBtn) {
      resetPaletteBtn.addEventListener('click', () => {
        const palKey = currentConfig.palette?.preset || 'indigo';
        const mode = currentConfig.theme?.mode || 'dark';
        const palettes = window.colorPalettes || {};
        const pal = palettes[palKey] || palettes['indigo'] || {};
        const tokens = mode === 'light' ? pal.light : pal.dark;
        if (tokens && tokens.primary) {
          const picker = document.getElementById('ctrl-color-primary');
          const text = document.getElementById('ctrl-color-primary-text');
          if (picker) picker.value = tokens.primary;
          if (text) text.value = tokens.primary;
          currentConfig.colors = currentConfig.colors || {};
          currentConfig.colors.primary = tokens.primary;
          applyLiveStylesToPreview();
          showToast('Reset primary accent to palette default');
        }
      });
    }

    // 3. GRADIENT PRESETS
    document.querySelectorAll('#gradient-presets-container .gradient-pill-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const start = btn.dataset.start;
        const end = btn.dataset.end;
        const angle = parseInt(btn.dataset.angle, 10) || 135;
        const type = btn.dataset.type || 'linear';

        currentConfig.background = currentConfig.background || {};
        currentConfig.background.type = 'gradient';
        currentConfig.background.gradient = {
          type: type,
          start_color: start,
          end_color: end,
          angle: angle,
        };

        const gradStartPicker = document.getElementById('ctrl-bg-grad-start');
        const gradStartText = document.getElementById('ctrl-bg-grad-start-text');
        if (gradStartPicker) gradStartPicker.value = start;
        if (gradStartText) gradStartText.value = start;

        const gradEndPicker = document.getElementById('ctrl-bg-grad-end');
        const gradEndText = document.getElementById('ctrl-bg-grad-end-text');
        if (gradEndPicker) gradEndPicker.value = end;
        if (gradEndText) gradEndText.value = end;

        const gradAngleSlider = document.getElementById('ctrl-bg-grad-angle');
        const gradAngleVal = document.getElementById('ctrl-bg-grad-angle-val');
        if (gradAngleSlider) gradAngleSlider.value = angle;
        if (gradAngleVal) gradAngleVal.textContent = `${angle}°`;

        const gradTypeSelect = document.getElementById('ctrl-bg-gradient-type');
        if (gradTypeSelect) gradTypeSelect.value = type;

        document.querySelectorAll('#gradient-presets-container .gradient-pill-btn').forEach((b) => {
          b.classList.toggle('active', b === btn);
        });

        applyLiveStylesToPreview();
      });
    });

    // 4. CARD STYLE PRESET
    document.querySelectorAll('#ctrl-card-preset-group .segmented-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const preset = btn.dataset.preset;
        currentConfig.card = currentConfig.card || {};
        currentConfig.card.preset = preset;
        document.querySelectorAll('#ctrl-card-preset-group .segmented-btn').forEach((b) => {
          b.classList.toggle('active', b.dataset.preset === preset);
        });
        applyLiveStylesToPreview();
      });
    });

    // 5. BUTTON STYLE PRESET
    document.querySelectorAll('#ctrl-button-preset-group .segmented-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const preset = btn.dataset.preset;
        currentConfig.buttons = currentConfig.buttons || {};
        currentConfig.buttons.preset = preset;
        document.querySelectorAll('#ctrl-button-preset-group .segmented-btn').forEach((b) => {
          b.classList.toggle('active', b.dataset.preset === preset);
        });
        applyLiveStylesToPreview();
      });
    });

    // 6. INPUT STYLE PRESET
    document.querySelectorAll('#ctrl-input-preset-group .segmented-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const preset = btn.dataset.preset;
        currentConfig.inputs = currentConfig.inputs || {};
        currentConfig.inputs.preset = preset;
        document.querySelectorAll('#ctrl-input-preset-group .segmented-btn').forEach((b) => {
          b.classList.toggle('active', b.dataset.preset === preset);
        });
        applyLiveStylesToPreview();
      });
    });

    // 7. DENSITY / SPACING PRESET
    document.querySelectorAll('#ctrl-density-group .segmented-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const density = btn.dataset.density;
        currentConfig.spacing = currentConfig.spacing || {};
        currentConfig.spacing.density = density;
        document.querySelectorAll('#ctrl-density-group .segmented-btn').forEach((b) => {
          b.classList.toggle('active', b.dataset.density === density);
        });
        applyLiveStylesToPreview();
      });
    });

    // 8. TYPE SCALE PRESET
    document.querySelectorAll('#ctrl-type-scale-group .segmented-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const scale = btn.dataset.scale;
        currentConfig.typography = currentConfig.typography || {};
        currentConfig.typography.scale = scale;
        document.querySelectorAll('#ctrl-type-scale-group .segmented-btn').forEach((b) => {
          b.classList.toggle('active', b.dataset.scale === scale);
        });
        applyLiveStylesToPreview();
      });
    });

    // 9. MOTION PRESET
    document.querySelectorAll('#ctrl-anim-preset-group .segmented-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const preset = btn.dataset.preset;
        currentConfig.animations = currentConfig.animations || {};
        if (preset === 'none') {
          currentConfig.animations.type = 'none';
          currentConfig.animations.duration = 0;
        } else if (preset === 'subtle') {
          currentConfig.animations.type = 'fade';
          currentConfig.animations.duration = 150;
          currentConfig.animations.intensity = 'subtle';
        } else if (preset === 'smooth') {
          currentConfig.animations.type = 'slide_up';
          currentConfig.animations.duration = 250;
          currentConfig.animations.intensity = 'subtle';
        } else if (preset === 'expressive') {
          currentConfig.animations.type = 'slide_up';
          currentConfig.animations.duration = 350;
          currentConfig.animations.intensity = 'normal';
        }
        document.querySelectorAll('#ctrl-anim-preset-group .segmented-btn').forEach((b) => {
          b.classList.toggle('active', b.dataset.preset === preset);
        });
        syncSidebarControlsFromConfig(currentConfig);
        applyLiveStylesToPreview();
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

    // --- BACKGROUND CONTROLS ---
    // Background Elements
    const bgTypeBtns = document.querySelectorAll('#ctrl-bg-type-group .segmented-btn');
    const bgColorRow = document.getElementById('ctrl-bg-color-row');
    const bgGradContainer = document.getElementById('ctrl-bg-gradient-container');
    const bgImgContainer = document.getElementById('ctrl-bg-image-container');

    const bgSourceBtns = document.querySelectorAll('#ctrl-bg-image-source-group .segmented-btn');
    const bgSourceUploadWrap = document.getElementById('ctrl-bg-source-upload-wrap');
    const bgSourceUrlWrap = document.getElementById('ctrl-bg-source-url-wrap');
    const bgUrlInput = document.getElementById('ctrl-bg-image-url');
    const applyBgUrlBtn = document.getElementById('btn-apply-bg-url');
    const removeBgUrlBtn = document.getElementById('btn-remove-bg-url');
    const bgUrlStatus = document.getElementById('ctrl-bg-url-status');

    // 1. Background Type (Solid Color / Gradient / Upload / Image URL)
    bgTypeBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        bgTypeBtns.forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        const type = btn.dataset.bgType;
        currentConfig.background = currentConfig.background || {};

        if (type === 'image-url') {
          currentConfig.background.type = 'image';
          currentConfig.background.source = 'url';
          if (bgColorRow) bgColorRow.style.display = 'none';
          if (bgGradContainer) bgGradContainer.style.display = 'none';
          if (bgImgContainer) bgImgContainer.style.display = 'block';
          if (bgSourceUploadWrap) bgSourceUploadWrap.style.display = 'none';
          if (bgSourceUrlWrap) bgSourceUrlWrap.style.display = 'block';
          bgSourceBtns.forEach((b) => b.classList.toggle('active', b.dataset.source === 'url'));
          setTimeout(() => { if (bgUrlInput) bgUrlInput.focus(); }, 100);
        } else if (type === 'image') {
          currentConfig.background.type = 'image';
          currentConfig.background.source = 'upload';
          if (bgColorRow) bgColorRow.style.display = 'none';
          if (bgGradContainer) bgGradContainer.style.display = 'none';
          if (bgImgContainer) bgImgContainer.style.display = 'block';
          if (bgSourceUploadWrap) bgSourceUploadWrap.style.display = 'block';
          if (bgSourceUrlWrap) bgSourceUrlWrap.style.display = 'none';
          bgSourceBtns.forEach((b) => b.classList.toggle('active', b.dataset.source === 'upload'));
        } else {
          currentConfig.background.type = type;
          if (bgColorRow) bgColorRow.style.display = type === 'color' ? 'flex' : 'none';
          if (bgGradContainer) bgGradContainer.style.display = type === 'gradient' ? 'block' : 'none';
          if (bgImgContainer) bgImgContainer.style.display = 'none';
        }

        applyLiveStylesToPreview();
      });
    });

    // 2. Background Solid Color
    const bgColorPicker = document.getElementById('ctrl-bg-color');
    const bgColorText = document.getElementById('ctrl-bg-color-text');
    if (bgColorPicker && bgColorText) {
      bgColorPicker.addEventListener('input', () => {
        bgColorText.value = bgColorPicker.value;
        currentConfig.background = currentConfig.background || {};
        currentConfig.background.color = bgColorPicker.value;
        applyLiveStylesToPreview();
      });
      bgColorText.addEventListener('input', () => {
        bgColorPicker.value = bgColorText.value;
        currentConfig.background = currentConfig.background || {};
        currentConfig.background.color = bgColorText.value;
        applyLiveStylesToPreview();
      });
    }

    // 3. Gradient Controls
    const gradTypeSelect = document.getElementById('ctrl-bg-gradient-type');
    const gradAngleRow = document.getElementById('ctrl-bg-grad-angle-row');
    const gradAngleSlider = document.getElementById('ctrl-bg-grad-angle');
    const gradAngleVal = document.getElementById('ctrl-bg-grad-angle-val');
    const gradStartPicker = document.getElementById('ctrl-bg-grad-start');
    const gradStartText = document.getElementById('ctrl-bg-grad-start-text');
    const gradEndPicker = document.getElementById('ctrl-bg-grad-end');
    const gradEndText = document.getElementById('ctrl-bg-grad-end-text');

    if (gradTypeSelect) {
      gradTypeSelect.addEventListener('change', () => {
        currentConfig.background = currentConfig.background || {};
        currentConfig.background.gradient = currentConfig.background.gradient || {};
        currentConfig.background.gradient.type = gradTypeSelect.value;
        if (gradAngleRow) gradAngleRow.style.display = gradTypeSelect.value === 'radial' ? 'none' : 'block';
        applyLiveStylesToPreview();
      });
    }

    if (gradStartPicker && gradStartText) {
      gradStartPicker.addEventListener('input', () => {
        gradStartText.value = gradStartPicker.value;
        currentConfig.background = currentConfig.background || {};
        currentConfig.background.gradient = currentConfig.background.gradient || {};
        currentConfig.background.gradient.start_color = gradStartPicker.value;
        applyLiveStylesToPreview();
      });
      gradStartText.addEventListener('input', () => {
        gradStartPicker.value = gradStartText.value;
        currentConfig.background = currentConfig.background || {};
        currentConfig.background.gradient = currentConfig.background.gradient || {};
        currentConfig.background.gradient.start_color = gradStartText.value;
        applyLiveStylesToPreview();
      });
    }

    if (gradEndPicker && gradEndText) {
      gradEndPicker.addEventListener('input', () => {
        gradEndText.value = gradEndPicker.value;
        currentConfig.background = currentConfig.background || {};
        currentConfig.background.gradient = currentConfig.background.gradient || {};
        currentConfig.background.gradient.end_color = gradEndPicker.value;
        applyLiveStylesToPreview();
      });
      gradEndText.addEventListener('input', () => {
        gradEndPicker.value = gradEndText.value;
        currentConfig.background = currentConfig.background || {};
        currentConfig.background.gradient = currentConfig.background.gradient || {};
        currentConfig.background.gradient.end_color = gradEndText.value;
        applyLiveStylesToPreview();
      });
    }

    if (gradAngleSlider && gradAngleVal) {
      gradAngleSlider.addEventListener('input', () => {
        const val = `${gradAngleSlider.value}°`;
        gradAngleVal.textContent = val;
        currentConfig.background = currentConfig.background || {};
        currentConfig.background.gradient = currentConfig.background.gradient || {};
        currentConfig.background.gradient.angle = parseInt(gradAngleSlider.value, 10);
        applyLiveStylesToPreview();
      });
    }

    // 4. Background Image Upload, URL, Dropzone, and Actions
    const bgFileInput = document.getElementById('ctrl-bg-file');
    const bgDropzone = document.getElementById('ctrl-bg-dropzone');
    const replaceBgBtn = document.getElementById('btn-replace-bg');
    const removeBgBtn = document.getElementById('btn-remove-bg');
    const restoreDefaultBgBtn = document.getElementById('btn-restore-default-bg');

    // Source toggle: Upload vs Image URL
    bgSourceBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        bgSourceBtns.forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        const src = btn.dataset.source;
        currentConfig.background = currentConfig.background || {};
        currentConfig.background.source = src;
        if (src === 'url') {
          if (bgSourceUploadWrap) bgSourceUploadWrap.style.display = 'none';
          if (bgSourceUrlWrap) bgSourceUrlWrap.style.display = 'block';
          bgTypeBtns.forEach((b) => b.classList.toggle('active', b.dataset.bgType === 'image-url'));
          setTimeout(() => { if (bgUrlInput) bgUrlInput.focus(); }, 100);
        } else {
          if (bgSourceUploadWrap) bgSourceUploadWrap.style.display = 'block';
          if (bgSourceUrlWrap) bgSourceUrlWrap.style.display = 'none';
          bgTypeBtns.forEach((b) => b.classList.toggle('active', b.dataset.bgType === 'image'));
        }
      });
    });

    // Function to apply and validate background image URL
    function applyBackgroundImageUrl(rawUrl) {
      if (!rawUrl || !rawUrl.trim()) {
        if (bgUrlStatus) {
          bgUrlStatus.style.display = 'block';
          bgUrlStatus.style.color = '#ef4444';
          bgUrlStatus.textContent = 'Please enter an image URL.';
        }
        return;
      }
      const url = rawUrl.trim();

      // Protocol validation: Strictly allow HTTP and HTTPS
      const lower = url.toLowerCase();
      if (!lower.startsWith('http://') && !lower.startsWith('https://')) {
        if (bgUrlStatus) {
          bgUrlStatus.style.display = 'block';
          bgUrlStatus.style.color = '#ef4444';
          bgUrlStatus.textContent = 'Unable to load this image. Check the URL.';
        }
        showToast('Unable to load this image. Check the URL.', true);
        return;
      }

      // Check for dangerous or attribute-breaking characters
      if (/["'<>;\\]/.test(url)) {
        if (bgUrlStatus) {
          bgUrlStatus.style.display = 'block';
          bgUrlStatus.style.color = '#ef4444';
          bgUrlStatus.textContent = 'Unable to load this image. Check the URL.';
        }
        showToast('Unable to load this image. Check the URL.', true);
        return;
      }

      // Feedback while verifying
      if (bgUrlStatus) {
        bgUrlStatus.style.display = 'block';
        bgUrlStatus.style.color = 'var(--builder-text-muted)';
        bgUrlStatus.textContent = 'Loading image...';
      }

      // Client-side direct image load test (no server SSRF)
      const testImg = new Image();
      let finished = false;
      const timeoutId = setTimeout(() => {
        if (finished) return;
        finished = true;
        testImg.src = '';
        if (bgUrlStatus) {
          bgUrlStatus.style.display = 'block';
          bgUrlStatus.style.color = '#ef4444';
          bgUrlStatus.textContent = 'Unable to load this image. Check the URL.';
        }
        showToast('Unable to load this image. Check the URL.', true);
      }, 8000);

      testImg.onload = () => {
        if (finished) return;
        finished = true;
        clearTimeout(timeoutId);
        currentConfig.background = currentConfig.background || {};
        currentConfig.background.type = 'image';
        currentConfig.background.source = 'url';
        currentConfig.background.image_url = url;
        currentConfig.background._bg_filename = url.split('/').pop().split('?')[0] || 'external_image';
        updateBgImageUI(currentConfig.background);
        applyLiveStylesToPreview();
        if (bgUrlStatus) {
          bgUrlStatus.style.display = 'block';
          bgUrlStatus.style.color = '#10b981';
          bgUrlStatus.textContent = '✓ Background image loaded';
        }
        showToast('✓ Background image loaded');
      };

      testImg.onerror = () => {
        if (finished) return;
        finished = true;
        clearTimeout(timeoutId);
        // Do NOT remove existing working background
        if (bgUrlStatus) {
          bgUrlStatus.style.display = 'block';
          bgUrlStatus.style.color = '#ef4444';
          bgUrlStatus.textContent = 'Unable to load this image. Check the URL.';
        }
        showToast('Unable to load this image. Check the URL.', true);
      };

      testImg.src = url;
    }

    if (applyBgUrlBtn) {
      applyBgUrlBtn.addEventListener('click', () => {
        if (bgUrlInput) applyBackgroundImageUrl(bgUrlInput.value);
      });
    }

    if (bgUrlInput) {
      bgUrlInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          applyBackgroundImageUrl(bgUrlInput.value);
        }
      });
      bgUrlInput.addEventListener('paste', () => {
        setTimeout(() => {
          if (bgUrlInput.value && bgUrlInput.value.trim().length > 8) {
            applyBackgroundImageUrl(bgUrlInput.value);
          }
        }, 60);
      });
    }

    if (removeBgUrlBtn) {
      removeBgUrlBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        currentConfig.background = currentConfig.background || {};
        currentConfig.background.image_url = '';
        if (bgUrlInput) bgUrlInput.value = '';
        if (bgUrlStatus) bgUrlStatus.style.display = 'none';
        updateBgImageUI(currentConfig.background);
        applyLiveStylesToPreview();
        showToast('Background image removed.');
      });
    }

    function handleBgFile(file) {
      if (!file) return;
      if (file.size > 1.5 * 1024 * 1024) {
        showToast('Background image exceeds 1.5 MB limit. Please select a smaller image.', true);
        return;
      }
      const validTypes = ['image/png', 'image/jpeg', 'image/webp'];
      if (!validTypes.includes(file.type.toLowerCase())) {
        showToast('Invalid format. Only PNG, JPEG, and WebP are allowed. SVG is strictly prohibited.', true);
        return;
      }

      const reader = new FileReader();
      reader.onload = (e) => {
        currentConfig.background = currentConfig.background || {};
        currentConfig.background.type = 'image';
        currentConfig.background.source = 'upload';
        currentConfig.background.image_url = e.target.result;
        currentConfig.background._bg_filename = file.name;
        currentConfig.background._bg_filesize = `${(file.size / 1024).toFixed(1)} KB`;
        updateBgImageUI(currentConfig.background);
        applyLiveStylesToPreview();
        showToast('Background image uploaded successfully!');
      };
      reader.onerror = () => {
        showToast('Failed to read image file.', true);
      };
      reader.readAsDataURL(file);
    }

    if (bgFileInput) {
      bgFileInput.addEventListener('change', () => {
        if (bgFileInput.files && bgFileInput.files[0]) {
          handleBgFile(bgFileInput.files[0]);
          bgFileInput.value = '';
        }
      });
    }

    if (bgDropzone) {
      bgDropzone.addEventListener('click', (e) => {
        if (!e.target.closest('#btn-replace-bg') && !e.target.closest('#btn-remove-bg')) {
          if (bgFileInput) bgFileInput.click();
        }
      });
      bgDropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        bgDropzone.classList.add('drag-over');
      });
      bgDropzone.addEventListener('dragleave', () => {
        bgDropzone.classList.remove('drag-over');
      });
      bgDropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        bgDropzone.classList.remove('drag-over');
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
          handleBgFile(e.dataTransfer.files[0]);
        }
      });
    }

    if (replaceBgBtn) {
      replaceBgBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (bgFileInput) bgFileInput.click();
      });
    }

    if (removeBgBtn) {
      removeBgBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        currentConfig.background = currentConfig.background || {};
        currentConfig.background.image_url = '';
        delete currentConfig.background._bg_filename;
        delete currentConfig.background._bg_filesize;
        if (bgUrlInput) bgUrlInput.value = '';
        if (bgUrlStatus) bgUrlStatus.style.display = 'none';
        updateBgImageUI(currentConfig.background);
        applyLiveStylesToPreview();
        showToast('Background image removed.');
      });
    }

    if (restoreDefaultBgBtn) {
      restoreDefaultBgBtn.addEventListener('click', () => {
        currentConfig.background = {
          type: 'color',
          color: '#131315',
          gradient: { type: 'linear', start_color: '#0f172a', end_color: '#1e1b4b', angle: 135 },
          image_url: '',
          position: 'center',
          size: 'cover',
          repeat: 'no-repeat',
          overlay: { color: '#000000', opacity: 40 },
          blur: 0,
          brightness: 100,
          saturation: 100,
        };
        syncSidebarControlsFromConfig(currentConfig);
        applyLiveStylesToPreview();
        showToast('Restored default background settings.');
      });
    }

    // 5. Background Position, Size, Repeat
    const bgPosSelect = document.getElementById('ctrl-bg-position');
    if (bgPosSelect) {
      bgPosSelect.addEventListener('change', () => {
        currentConfig.background = currentConfig.background || {};
        currentConfig.background.position = bgPosSelect.value;
        applyLiveStylesToPreview();
      });
    }

    const bgSizeSelect = document.getElementById('ctrl-bg-size');
    if (bgSizeSelect) {
      bgSizeSelect.addEventListener('change', () => {
        currentConfig.background = currentConfig.background || {};
        currentConfig.background.size = bgSizeSelect.value;
        applyLiveStylesToPreview();
      });
    }

    const bgRepeatSelect = document.getElementById('ctrl-bg-repeat');
    if (bgRepeatSelect) {
      bgRepeatSelect.addEventListener('change', () => {
        currentConfig.background = currentConfig.background || {};
        currentConfig.background.repeat = bgRepeatSelect.value;
        applyLiveStylesToPreview();
      });
    }

    // 6. Background Overlay Color & Opacity
    const bgOverlayPicker = document.getElementById('ctrl-bg-overlay-color');
    const bgOverlayText = document.getElementById('ctrl-bg-overlay-color-text');
    const bgOverlayOpacitySlider = document.getElementById('ctrl-bg-overlay-opacity');
    const bgOverlayOpacityVal = document.getElementById('ctrl-bg-overlay-opacity-val');

    if (bgOverlayPicker && bgOverlayText) {
      bgOverlayPicker.addEventListener('input', () => {
        bgOverlayText.value = bgOverlayPicker.value;
        currentConfig.background = currentConfig.background || {};
        currentConfig.background.overlay = currentConfig.background.overlay || {};
        currentConfig.background.overlay.color = bgOverlayPicker.value;
        applyLiveStylesToPreview();
      });
      bgOverlayText.addEventListener('input', () => {
        bgOverlayPicker.value = bgOverlayText.value;
        currentConfig.background = currentConfig.background || {};
        currentConfig.background.overlay = currentConfig.background.overlay || {};
        currentConfig.background.overlay.color = bgOverlayText.value;
        applyLiveStylesToPreview();
      });
    }

    if (bgOverlayOpacitySlider && bgOverlayOpacityVal) {
      bgOverlayOpacitySlider.addEventListener('input', () => {
        const val = `${bgOverlayOpacitySlider.value}%`;
        bgOverlayOpacityVal.textContent = val;
        currentConfig.background = currentConfig.background || {};
        currentConfig.background.overlay = currentConfig.background.overlay || {};
        currentConfig.background.overlay.opacity = parseInt(bgOverlayOpacitySlider.value, 10);
        applyLiveStylesToPreview();
      });
    }

    // 7. Background Effects: Blur, Brightness, Saturation
    const bgBlurSlider = document.getElementById('ctrl-bg-blur');
    const bgBlurVal = document.getElementById('ctrl-bg-blur-val');
    if (bgBlurSlider && bgBlurVal) {
      bgBlurSlider.addEventListener('input', () => {
        const val = `${bgBlurSlider.value}px`;
        bgBlurVal.textContent = val;
        currentConfig.background = currentConfig.background || {};
        currentConfig.background.blur = parseInt(bgBlurSlider.value, 10);
        applyLiveStylesToPreview();
      });
    }

    const bgBrightnessSlider = document.getElementById('ctrl-bg-brightness');
    const bgBrightnessVal = document.getElementById('ctrl-bg-brightness-val');
    if (bgBrightnessSlider && bgBrightnessVal) {
      bgBrightnessSlider.addEventListener('input', () => {
        const val = `${bgBrightnessSlider.value}%`;
        bgBrightnessVal.textContent = val;
        currentConfig.background = currentConfig.background || {};
        currentConfig.background.brightness = parseInt(bgBrightnessSlider.value, 10);
        applyLiveStylesToPreview();
      });
    }

    const bgSaturationSlider = document.getElementById('ctrl-bg-saturation');
    const bgSaturationVal = document.getElementById('ctrl-bg-saturation-val');
    if (bgSaturationSlider && bgSaturationVal) {
      bgSaturationSlider.addEventListener('input', () => {
        const val = `${bgSaturationSlider.value}%`;
        bgSaturationVal.textContent = val;
        currentConfig.background = currentConfig.background || {};
        currentConfig.background.saturation = parseInt(bgSaturationSlider.value, 10);
        applyLiveStylesToPreview();
      });
    }

    // --- THEME MODE CONTROLS ---
    const themeModeBtns = document.querySelectorAll('#ctrl-theme-mode-group .segmented-btn');
    themeModeBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        themeModeBtns.forEach((b) => {
          b.classList.remove('active');
          b.setAttribute('aria-pressed', 'false');
        });
        btn.classList.add('active');
        btn.setAttribute('aria-pressed', 'true');
        const mode = btn.dataset.mode || 'dark';
        currentConfig.theme = currentConfig.theme || {};
        currentConfig.theme.mode = mode;

        // If card does not have custom background color, update card picker to reflect theme default
        if (!currentConfig.card?._has_custom_bg && !currentConfig.card?.background_color) {
          const defaultCardBg = mode === 'light' ? '#FFFFFF' : '#1B1D21';
          const cardBgPicker = document.getElementById('ctrl-card-bg-color');
          const cardBgText = document.getElementById('ctrl-card-bg-color-text');
          if (cardBgPicker) cardBgPicker.value = defaultCardBg;
          if (cardBgText) cardBgText.value = defaultCardBg;
        }

        applyLiveStylesToPreview();
      });
    });

    // --- CARD STYLE CONTROLS ---
    const cardWidthSlider = document.getElementById('ctrl-card-width');
    const cardWidthVal = document.getElementById('ctrl-card-width-val');
    if (cardWidthSlider && cardWidthVal) {
      cardWidthSlider.addEventListener('input', () => {
        const val = `${cardWidthSlider.value}px`;
        cardWidthVal.textContent = val;
        currentConfig.card = currentConfig.card || {};
        currentConfig.card.width = val;
        applyLiveStylesToPreview();
      });
    }

    const cardPaddingSlider = document.getElementById('ctrl-card-padding');
    const cardPaddingVal = document.getElementById('ctrl-card-padding-val');
    if (cardPaddingSlider && cardPaddingVal) {
      cardPaddingSlider.addEventListener('input', () => {
        const val = `${cardPaddingSlider.value}px`;
        cardPaddingVal.textContent = val;
        currentConfig.card = currentConfig.card || {};
        currentConfig.card.padding = val;
        applyLiveStylesToPreview();
      });
    }

    const cardBgPicker = document.getElementById('ctrl-card-bg-color');
    const cardBgText = document.getElementById('ctrl-card-bg-color-text');
    const resetCardBgBtn = document.getElementById('btn-reset-card-bg');

    if (cardBgPicker && cardBgText) {
      cardBgPicker.addEventListener('input', () => {
        cardBgText.value = cardBgPicker.value;
        currentConfig.card = currentConfig.card || {};
        currentConfig.card.background_color = cardBgPicker.value;
        currentConfig.card._has_custom_bg = true;
        applyLiveStylesToPreview();
      });
      cardBgText.addEventListener('input', () => {
        cardBgPicker.value = cardBgText.value;
        currentConfig.card = currentConfig.card || {};
        currentConfig.card.background_color = cardBgText.value;
        currentConfig.card._has_custom_bg = true;
        applyLiveStylesToPreview();
      });
    }

    if (resetCardBgBtn) {
      resetCardBgBtn.addEventListener('click', () => {
        if (currentConfig.card) {
          delete currentConfig.card.background_color;
          delete currentConfig.card._has_custom_bg;
        }
        if (currentConfig.colors) {
          delete currentConfig.colors.card_bg;
        }
        const themeMode = (currentConfig.theme?.mode || 'dark').toLowerCase();
        const defaultCardBg = themeMode === 'light' ? '#FFFFFF' : '#1B1D21';
        if (cardBgPicker) cardBgPicker.value = defaultCardBg;
        if (cardBgText) cardBgText.value = defaultCardBg;
        applyLiveStylesToPreview();
        showToast('Card background reset to theme default.');
      });
    }

    // Card Appearance (Opaque / Translucent / Glass)
    const cardAppearanceBtns = document.querySelectorAll('#ctrl-card-appearance-group .segmented-btn');
    cardAppearanceBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        cardAppearanceBtns.forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        const appearance = btn.dataset.appearance || 'opaque';
        currentConfig.card = currentConfig.card || {};
        currentConfig.card.appearance = appearance;

        if (appearance === 'opaque') {
          currentConfig.card.opacity = 100;
          currentConfig.card.blur = 0;
          currentConfig.card.backdrop_blur = 0;
          currentConfig.card.border_enabled = true;
          currentConfig.card.border_opacity = 100;
          currentConfig.card.shadow = 'subtle';
        } else if (appearance === 'translucent') {
          currentConfig.card.opacity = 45;
          currentConfig.card.blur = 0;
          currentConfig.card.backdrop_blur = 0;
          currentConfig.card.border_enabled = true;
          currentConfig.card.border_opacity = 30;
          currentConfig.card.shadow = 'subtle';
        } else if (appearance === 'glass') {
          currentConfig.card.opacity = 25;
          currentConfig.card.blur = 14;
          currentConfig.card.backdrop_blur = 14;
          currentConfig.card.border_enabled = true;
          currentConfig.card.border_opacity = 25;
          currentConfig.card.border_width = 1;
          currentConfig.card.shadow = 'medium';
        }

        if (cardOpacitySlider) {
          cardOpacitySlider.value = currentConfig.card.opacity;
          if (cardOpacityVal) cardOpacityVal.textContent = `${currentConfig.card.opacity}%`;
        }
        if (cardBackdropBlurSlider) {
          cardBackdropBlurSlider.value = currentConfig.card.blur;
          if (cardBackdropBlurVal) cardBackdropBlurVal.textContent = `${currentConfig.card.blur}px`;
        }
        const cardBorderToggle = document.getElementById('ctrl-card-border-toggle');
        if (cardBorderToggle) cardBorderToggle.checked = currentConfig.card.border_enabled;
        const cardBorderControls = document.getElementById('ctrl-card-border-controls');
        if (cardBorderControls) cardBorderControls.style.display = currentConfig.card.border_enabled ? 'block' : 'none';
        const cardBorderOpacitySlider = document.getElementById('ctrl-card-border-opacity');
        const cardBorderOpacityVal = document.getElementById('ctrl-card-border-opacity-val');
        if (cardBorderOpacitySlider) {
          cardBorderOpacitySlider.value = currentConfig.card.border_opacity;
          if (cardBorderOpacityVal) cardBorderOpacityVal.textContent = `${currentConfig.card.border_opacity}%`;
        }
        const shadowBtns = document.querySelectorAll('#ctrl-card-shadow-group .segmented-btn');
        shadowBtns.forEach((sb) => sb.classList.toggle('active', sb.dataset.shadow === currentConfig.card.shadow));

        applyLiveStylesToPreview();
      });
    });

    const cardOpacitySlider = document.getElementById('ctrl-card-opacity');
    const cardOpacityVal = document.getElementById('ctrl-card-opacity-val');
    if (cardOpacitySlider && cardOpacityVal) {
      cardOpacitySlider.addEventListener('input', () => {
        const val = `${cardOpacitySlider.value}%`;
        cardOpacityVal.textContent = val;
        currentConfig.card = currentConfig.card || {};
        currentConfig.card.opacity = parseInt(cardOpacitySlider.value, 10);
        applyLiveStylesToPreview();
      });
    }

    // Card Border Toggle & Opacity
    const cardBorderToggle = document.getElementById('ctrl-card-border-toggle');
    const cardBorderControls = document.getElementById('ctrl-card-border-controls');
    if (cardBorderToggle) {
      cardBorderToggle.addEventListener('change', () => {
        currentConfig.card = currentConfig.card || {};
        currentConfig.card.border_enabled = cardBorderToggle.checked;
        if (cardBorderControls) {
          cardBorderControls.style.display = cardBorderToggle.checked ? 'block' : 'none';
        }
        applyLiveStylesToPreview();
      });
    }

    const cardBorderOpacitySlider = document.getElementById('ctrl-card-border-opacity');
    const cardBorderOpacityVal = document.getElementById('ctrl-card-border-opacity-val');
    if (cardBorderOpacitySlider && cardBorderOpacityVal) {
      cardBorderOpacitySlider.addEventListener('input', () => {
        const val = `${cardBorderOpacitySlider.value}%`;
        cardBorderOpacityVal.textContent = val;
        currentConfig.card = currentConfig.card || {};
        currentConfig.card.border_opacity = parseInt(cardBorderOpacitySlider.value, 10);
        applyLiveStylesToPreview();
      });
    }

    const cardRadiusSlider = document.getElementById('ctrl-card-radius');
    const cardRadiusVal = document.getElementById('ctrl-card-radius-val');
    if (cardRadiusSlider && cardRadiusVal) {
      cardRadiusSlider.addEventListener('input', () => {
        const val = `${cardRadiusSlider.value}px`;
        cardRadiusVal.textContent = val;
        currentConfig.card = currentConfig.card || {};
        currentConfig.card.border_radius = val;
        applyLiveStylesToPreview();
      });
    }

    const cardBorderWidthInput = document.getElementById('ctrl-card-border-width');
    if (cardBorderWidthInput) {
      cardBorderWidthInput.addEventListener('input', () => {
        const val = Math.max(0, Math.min(4, parseInt(cardBorderWidthInput.value, 10) || 0));
        currentConfig.card = currentConfig.card || {};
        currentConfig.card.border_width = val;
        applyLiveStylesToPreview();
      });
    }

    const cardBorderColorPicker = document.getElementById('ctrl-card-border-color');
    const cardBorderColorText = document.getElementById('ctrl-card-border-color-text');
    if (cardBorderColorPicker && cardBorderColorText) {
      cardBorderColorPicker.addEventListener('input', () => {
        cardBorderColorText.value = cardBorderColorPicker.value;
        currentConfig.card = currentConfig.card || {};
        currentConfig.card.border_color = cardBorderColorPicker.value;
        applyLiveStylesToPreview();
      });
      cardBorderColorText.addEventListener('input', () => {
        cardBorderColorPicker.value = cardBorderColorText.value;
        currentConfig.card = currentConfig.card || {};
        currentConfig.card.border_color = cardBorderColorText.value;
        applyLiveStylesToPreview();
      });
    }

    // Card Shadow Intensity
    const cardShadowBtns = document.querySelectorAll('#ctrl-card-shadow-group .segmented-btn');
    cardShadowBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        cardShadowBtns.forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        currentConfig.card = currentConfig.card || {};
        currentConfig.card.shadow = btn.dataset.shadow;
        applyLiveStylesToPreview();
      });
    });

    const cardBackdropBlurSlider = document.getElementById('ctrl-card-backdrop-blur');
    const cardBackdropBlurVal = document.getElementById('ctrl-card-backdrop-blur-val');
    if (cardBackdropBlurSlider && cardBackdropBlurVal) {
      cardBackdropBlurSlider.addEventListener('input', () => {
        const val = `${cardBackdropBlurSlider.value}px`;
        cardBackdropBlurVal.textContent = val;
        currentConfig.card = currentConfig.card || {};
        currentConfig.card.blur = parseInt(cardBackdropBlurSlider.value, 10);
        currentConfig.card.backdrop_blur = parseInt(cardBackdropBlurSlider.value, 10);
        applyLiveStylesToPreview();
      });
    }

    // Card Alignment (Legacy 1D)
    const cardAlignBtns = document.querySelectorAll('#ctrl-card-align-group .segmented-btn');
    cardAlignBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        cardAlignBtns.forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        currentConfig.card = currentConfig.card || {};
        currentConfig.card.alignment = btn.dataset.align;
        applyLiveStylesToPreview();
      });
    });

    // Card Position & Placement (3x3 Grid & Fine Sliders)
    const posMatrixBtns = document.querySelectorAll('#ctrl-card-pos-matrix .pos-cell-btn');
    const cardPosXSlider = document.getElementById('ctrl-card-x');
    const cardPosXVal = document.getElementById('ctrl-card-x-val');
    const cardPosYSlider = document.getElementById('ctrl-card-y');
    const cardPosYVal = document.getElementById('ctrl-card-y-val');
    const cardPosName = document.getElementById('ctrl-card-pos-name');

    const posPresetMap = {
      '0,0': { pos: 'top-left', label: 'Top Left' },
      '50,0': { pos: 'top-center', label: 'Top Center' },
      '100,0': { pos: 'top-right', label: 'Top Right' },
      '0,50': { pos: 'center-left', label: 'Center Left' },
      '50,50': { pos: 'center', label: 'Center' },
      '100,50': { pos: 'center-right', label: 'Center Right' },
      '0,100': { pos: 'bottom-left', label: 'Bottom Left' },
      '50,100': { pos: 'bottom-center', label: 'Bottom Center' },
      '100,100': { pos: 'bottom-right', label: 'Bottom Right' },
    };

    function updateCardPositionFromValues(x, y, posKey = null) {
      x = Math.max(0, Math.min(100, parseInt(x, 10) || 0));
      y = Math.max(0, Math.min(100, parseInt(y, 10) || 0));

      currentConfig.layout = currentConfig.layout || {};
      currentConfig.card = currentConfig.card || {};

      const key = `${x},${y}`;
      const matched = posPresetMap[key];
      const finalPos = posKey || (matched ? matched.pos : 'custom');

      currentConfig.layout.card_position = finalPos;
      currentConfig.card.position = finalPos;
      currentConfig.layout.card_horizontal_position = x;
      currentConfig.layout.card_vertical_position = y;
      currentConfig.card.horizontal_position = x;
      currentConfig.card.vertical_position = y;

      if (cardPosXSlider) cardPosXSlider.value = x;
      if (cardPosXVal) cardPosXVal.textContent = `${x}%`;
      if (cardPosYSlider) cardPosYSlider.value = y;
      if (cardPosYVal) cardPosYVal.textContent = `${y}%`;

      if (cardPosName) {
        cardPosName.textContent = matched ? `${matched.label} (${x}%, ${y}%)` : `Custom (${x}%, ${y}%)`;
      }

      posMatrixBtns.forEach((btn) => {
        const btnX = parseInt(btn.dataset.x, 10);
        const btnY = parseInt(btn.dataset.y, 10);
        btn.classList.toggle('active', btnX === x && btnY === y);
      });

      applyLiveStylesToPreview();
    }

    posMatrixBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        const x = parseInt(btn.dataset.x, 10) || 0;
        const y = parseInt(btn.dataset.y, 10) || 0;
        const pos = btn.dataset.pos || 'center';
        updateCardPositionFromValues(x, y, pos);
      });
    });

    if (cardPosXSlider) {
      cardPosXSlider.addEventListener('input', () => {
        const x = parseInt(cardPosXSlider.value, 10) || 0;
        const y = parseInt(cardPosYSlider?.value, 10) || 50;
        updateCardPositionFromValues(x, y);
      });
    }

    if (cardPosYSlider) {
      cardPosYSlider.addEventListener('input', () => {
        const x = parseInt(cardPosXSlider?.value, 10) || 50;
        const y = parseInt(cardPosYSlider.value, 10) || 0;
        updateCardPositionFromValues(x, y);
      });
    }

    // --- ANIMATIONS CONTROLS ---
    const animTypeSelect = document.getElementById('ctrl-anim-type');
    if (animTypeSelect) {
      animTypeSelect.addEventListener('change', () => {
        currentConfig.animations = currentConfig.animations || {};
        currentConfig.animations.type = animTypeSelect.value;
        applyLiveStylesToPreview();
      });
    }

    const animDurationSlider = document.getElementById('ctrl-anim-duration');
    const animDurationVal = document.getElementById('ctrl-anim-duration-val');
    if (animDurationSlider && animDurationVal) {
      animDurationSlider.addEventListener('input', () => {
        const val = `${animDurationSlider.value}ms`;
        animDurationVal.textContent = val;
        currentConfig.animations = currentConfig.animations || {};
        currentConfig.animations.duration = parseInt(animDurationSlider.value, 10);
        applyLiveStylesToPreview();
      });
    }

    const animDelaySlider = document.getElementById('ctrl-anim-delay');
    const animDelayVal = document.getElementById('ctrl-anim-delay-val');
    if (animDelaySlider && animDelayVal) {
      animDelaySlider.addEventListener('input', () => {
        const val = `${animDelaySlider.value}ms`;
        animDelayVal.textContent = val;
        currentConfig.animations = currentConfig.animations || {};
        currentConfig.animations.delay = parseInt(animDelaySlider.value, 10);
        applyLiveStylesToPreview();
      });
    }

    const animIntensityBtns = document.querySelectorAll('#ctrl-anim-intensity-group .segmented-btn');
    animIntensityBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        animIntensityBtns.forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        currentConfig.animations = currentConfig.animations || {};
        currentConfig.animations.intensity = btn.dataset.intensity;
        applyLiveStylesToPreview();
      });
    });

    // Typography: Body Size & Alignment
    const bodySizeSlider = document.getElementById('ctrl-body-size');
    const bodySizeVal = document.getElementById('ctrl-body-size-val');
    if (bodySizeSlider && bodySizeVal) {
      bodySizeSlider.addEventListener('input', () => {
        const val = `${bodySizeSlider.value}px`;
        bodySizeVal.textContent = val;
        currentConfig.typography = currentConfig.typography || {};
        currentConfig.typography.body_size = val;
        applyLiveStylesToPreview();
      });
    }

    const typoAlignBtns = document.querySelectorAll('#ctrl-typography-align-group .segmented-btn');
    typoAlignBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        typoAlignBtns.forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        currentConfig.typography = currentConfig.typography || {};
        currentConfig.typography.align = btn.dataset.align;
        applyLiveStylesToPreview();
      });
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

  function updateBgImageUI(bg) {
    bg = bg || {};
    const uploadPreviewBox = document.getElementById('dropzone-bg-preview-box');
    const uploadEmptyPrompt = document.getElementById('dropzone-bg-prompt');
    const uploadPreviewImg = document.getElementById('bg-preview-img');
    const uploadPreviewName = document.getElementById('bg-preview-name');
    const uploadPreviewSize = document.getElementById('bg-preview-size');

    const urlWrap = document.getElementById('ctrl-bg-source-url-wrap');
    const uploadWrap = document.getElementById('ctrl-bg-source-upload-wrap');
    const urlInput = document.getElementById('ctrl-bg-image-url');
    const urlPreviewBox = document.getElementById('bg-url-preview-box');
    const urlPreviewThumb = document.getElementById('bg-url-preview-thumb');
    const urlPreviewName = document.getElementById('bg-url-preview-name');
    const urlStatus = document.getElementById('ctrl-bg-url-status');

    const isUrl = bg.image_url && (bg.image_url.startsWith('http://') || bg.image_url.startsWith('https://'));
    const source = bg.source || (isUrl ? 'url' : 'upload');

    // Update source segmented buttons
    document.querySelectorAll('#ctrl-bg-image-source-group .segmented-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.source === source);
    });

    // Update top background type buttons if in image mode
    if (bg.type === 'image') {
      document.querySelectorAll('#ctrl-bg-type-group .segmented-btn').forEach((btn) => {
        if (btn.dataset.bgType === 'image-url') {
          btn.classList.toggle('active', source === 'url');
        } else if (btn.dataset.bgType === 'image') {
          btn.classList.toggle('active', source !== 'url');
        } else {
          btn.classList.remove('active');
        }
      });
    }

    if (source === 'url') {
      if (urlWrap) urlWrap.style.display = 'block';
      if (uploadWrap) uploadWrap.style.display = 'none';
    } else {
      if (urlWrap) urlWrap.style.display = 'none';
      if (uploadWrap) uploadWrap.style.display = 'block';
    }

    if (bg.image_url) {
      if (isUrl) {
        if (urlInput && urlInput.value !== bg.image_url) urlInput.value = bg.image_url;
        if (urlPreviewBox) urlPreviewBox.style.display = 'flex';
        if (urlPreviewThumb) urlPreviewThumb.src = bg.image_url;
        if (urlPreviewName) {
          try {
            const parsed = new URL(bg.image_url);
            const pathSegments = parsed.pathname.split('/').filter(Boolean);
            urlPreviewName.textContent = pathSegments.pop() || 'External Image';
          } catch(e) {
            urlPreviewName.textContent = bg._bg_filename || 'External Image';
          }
        }
        if (uploadPreviewBox) uploadPreviewBox.style.display = 'none';
        if (uploadEmptyPrompt) uploadEmptyPrompt.style.display = 'flex';
      } else {
        if (uploadPreviewBox) uploadPreviewBox.style.display = 'flex';
        if (uploadEmptyPrompt) uploadEmptyPrompt.style.display = 'none';
        if (uploadPreviewImg) uploadPreviewImg.src = bg.image_url;
        if (uploadPreviewName) uploadPreviewName.textContent = bg._bg_filename || 'Custom Background Image';
        if (uploadPreviewSize) uploadPreviewSize.textContent = bg._bg_filesize || 'Active';
        if (urlPreviewBox) urlPreviewBox.style.display = 'none';
      }
    } else {
      if (uploadPreviewBox) uploadPreviewBox.style.display = 'none';
      if (uploadEmptyPrompt) uploadEmptyPrompt.style.display = 'flex';
      if (uploadPreviewImg) uploadPreviewImg.src = '';
      if (urlPreviewBox) urlPreviewBox.style.display = 'none';
      if (urlPreviewThumb) urlPreviewThumb.src = '';
      if (urlInput) urlInput.value = '';
      if (urlStatus) urlStatus.style.display = 'none';
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

    // Theme Mode Sync
    const themeMode = (config.theme?.mode || 'dark').toLowerCase();
    document.querySelectorAll('#ctrl-theme-mode-group .segmented-btn').forEach((btn) => {
      const isActive = btn.dataset.mode === themeMode;
      btn.classList.toggle('active', isActive);
      btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });

    // 1. Design Preset Sync
    const activePreset = config.design_preset || '';
    document.querySelectorAll('#design-presets-container .preset-card').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.preset === activePreset);
    });

    // 2. Color Palette Sync
    const activePal = config.palette?.preset || 'indigo';
    document.querySelectorAll('#color-palettes-container .palette-swatch-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.palette === activePal);
    });

    // 3. Card Style Preset Sync
    const cardPreset = config.card?.preset || 'default';
    document.querySelectorAll('#ctrl-card-preset-group .segmented-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.preset === cardPreset);
    });

    // 4. Button Style Preset Sync
    const btnPreset = config.buttons?.preset || 'solid';
    document.querySelectorAll('#ctrl-button-preset-group .segmented-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.preset === btnPreset);
    });

    // 5. Input Style Preset Sync
    const inputPreset = config.inputs?.preset || 'minimal';
    document.querySelectorAll('#ctrl-input-preset-group .segmented-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.preset === inputPreset);
    });

    // 6. Density / Spacing Sync
    const density = config.spacing?.density || 'comfortable';
    document.querySelectorAll('#ctrl-density-group .segmented-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.density === density);
    });

    // 7. Type Scale Sync
    const typeScale = config.typography?.scale || 'modern';
    document.querySelectorAll('#ctrl-type-scale-group .segmented-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.scale === typeScale);
    });

    // 8. Motion Preset Sync
    const anims = config.animations || {};
    let motionPreset = 'subtle';
    if (anims.type === 'none') motionPreset = 'none';
    else if (anims.type === 'slide_up' && anims.intensity === 'normal') motionPreset = 'expressive';
    else if (anims.type === 'slide_up') motionPreset = 'smooth';
    else if (anims.type === 'fade') motionPreset = 'subtle';
    document.querySelectorAll('#ctrl-anim-preset-group .segmented-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.preset === motionPreset);
    });

    // Background Controls Sync
    const bg = config.background || {};
    const bgType = bg.type || 'color';
    const isUrl = bg.image_url && (bg.image_url.startsWith('http://') || bg.image_url.startsWith('https://'));
    const source = bg.source || (isUrl ? 'url' : 'upload');

    document.querySelectorAll('#ctrl-bg-type-group .segmented-btn').forEach((btn) => {
      if (bgType === 'image') {
        if (btn.dataset.bgType === 'image-url') {
          btn.classList.toggle('active', source === 'url');
        } else if (btn.dataset.bgType === 'image') {
          btn.classList.toggle('active', source !== 'url');
        } else {
          btn.classList.remove('active');
        }
      } else {
        btn.classList.toggle('active', btn.dataset.bgType === bgType);
      }
    });

    const bgColorRow = document.getElementById('ctrl-bg-color-row');
    const bgGradContainer = document.getElementById('ctrl-bg-gradient-container');
    const bgImgContainer = document.getElementById('ctrl-bg-image-container');

    if (bgColorRow) bgColorRow.style.display = bgType === 'color' ? 'flex' : 'none';
    if (bgGradContainer) bgGradContainer.style.display = bgType === 'gradient' ? 'block' : 'none';
    if (bgImgContainer) bgImgContainer.style.display = bgType === 'image' ? 'block' : 'none';

    // Background Color
    const bgCol = bg.color || config.colors?.background || '#131315';
    const bgColPicker = document.getElementById('ctrl-bg-color');
    const bgColText = document.getElementById('ctrl-bg-color-text');
    if (bgColPicker) bgColPicker.value = bgCol;
    if (bgColText) bgColText.value = bgCol;

    // Gradient
    const grad = bg.gradient || {};
    const gradTypeSelect = document.getElementById('ctrl-bg-gradient-type');
    if (gradTypeSelect && grad.type) gradTypeSelect.value = grad.type;

    const gradAngleRow = document.getElementById('ctrl-bg-grad-angle-row');
    if (gradAngleRow) gradAngleRow.style.display = grad.type === 'radial' ? 'none' : 'block';

    const gradStartPicker = document.getElementById('ctrl-bg-grad-start');
    const gradStartText = document.getElementById('ctrl-bg-grad-start-text');
    if (gradStartPicker && grad.start_color) gradStartPicker.value = grad.start_color;
    if (gradStartText && grad.start_color) gradStartText.value = grad.start_color;

    const gradEndPicker = document.getElementById('ctrl-bg-grad-end');
    const gradEndText = document.getElementById('ctrl-bg-grad-end-text');
    if (gradEndPicker && grad.end_color) gradEndPicker.value = grad.end_color;
    if (gradEndText && grad.end_color) gradEndText.value = grad.end_color;

    const gradAngleSlider = document.getElementById('ctrl-bg-grad-angle');
    const gradAngleVal = document.getElementById('ctrl-bg-grad-angle-val');
    if (gradAngleSlider && grad.angle !== undefined) {
      gradAngleSlider.value = grad.angle;
      if (gradAngleVal) gradAngleVal.textContent = `${grad.angle}°`;
    }

    // Background Image
    updateBgImageUI(bg);

    const bgPosSelect = document.getElementById('ctrl-bg-position');
    if (bgPosSelect && bg.position) bgPosSelect.value = bg.position;

    const bgSizeSelect = document.getElementById('ctrl-bg-size');
    if (bgSizeSelect && bg.size) bgSizeSelect.value = bg.size;

    const bgRepeatSelect = document.getElementById('ctrl-bg-repeat');
    if (bgRepeatSelect && bg.repeat) bgRepeatSelect.value = bg.repeat;

    // Overlay
    const overlay = bg.overlay || {};
    const bgOverlayPicker = document.getElementById('ctrl-bg-overlay-color');
    const bgOverlayText = document.getElementById('ctrl-bg-overlay-color-text');
    if (bgOverlayPicker && overlay.color) bgOverlayPicker.value = overlay.color;
    if (bgOverlayText && overlay.color) bgOverlayText.value = overlay.color;

    const bgOverlayOpacitySlider = document.getElementById('ctrl-bg-overlay-opacity');
    const bgOverlayOpacityVal = document.getElementById('ctrl-bg-overlay-opacity-val');
    if (bgOverlayOpacitySlider && overlay.opacity !== undefined) {
      bgOverlayOpacitySlider.value = overlay.opacity;
      if (bgOverlayOpacityVal) bgOverlayOpacityVal.textContent = `${overlay.opacity}%`;
    }

    // Effects
    const bgBlurSlider = document.getElementById('ctrl-bg-blur');
    const bgBlurVal = document.getElementById('ctrl-bg-blur-val');
    if (bgBlurSlider && bg.blur !== undefined) {
      bgBlurSlider.value = bg.blur;
      if (bgBlurVal) bgBlurVal.textContent = `${bg.blur}px`;
    }

    const bgBrightnessSlider = document.getElementById('ctrl-bg-brightness');
    const bgBrightnessVal = document.getElementById('ctrl-bg-brightness-val');
    if (bgBrightnessSlider && bg.brightness !== undefined) {
      bgBrightnessSlider.value = bg.brightness;
      if (bgBrightnessVal) bgBrightnessVal.textContent = `${bg.brightness}%`;
    }

    const bgSaturationSlider = document.getElementById('ctrl-bg-saturation');
    const bgSaturationVal = document.getElementById('ctrl-bg-saturation-val');
    if (bgSaturationSlider && bg.saturation !== undefined) {
      bgSaturationSlider.value = bg.saturation;
      if (bgSaturationVal) bgSaturationVal.textContent = `${bg.saturation}%`;
    }

    // Card Style Sync
    const card = config.card || {};
    const cardWidthSlider = document.getElementById('ctrl-card-width');
    const cardWidthVal = document.getElementById('ctrl-card-width-val');
    if (cardWidthSlider && card.width) {
      const num = parseInt(card.width, 10);
      cardWidthSlider.value = num;
      if (cardWidthVal) cardWidthVal.textContent = card.width;
    }

    const cardPaddingSlider = document.getElementById('ctrl-card-padding');
    const cardPaddingVal = document.getElementById('ctrl-card-padding-val');
    if (cardPaddingSlider && card.padding) {
      const num = parseInt(card.padding, 10);
      cardPaddingSlider.value = num;
      if (cardPaddingVal) cardPaddingVal.textContent = card.padding;
    }

    // Card Appearance Sync
    const appearanceVal = card.appearance || (card.preset === 'glass' ? 'glass' : 'opaque');
    document.querySelectorAll('#ctrl-card-appearance-group .segmented-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.appearance === appearanceVal);
    });

    const cardBgPicker = document.getElementById('ctrl-card-bg-color');
    const cardBgText = document.getElementById('ctrl-card-bg-color-text');
    const defaultCardBg = themeMode === 'light' ? '#FFFFFF' : '#1B1D21';
    const effectiveCardBg = card.background_color || defaultCardBg;
    if (cardBgPicker) cardBgPicker.value = effectiveCardBg;
    if (cardBgText) cardBgText.value = effectiveCardBg;

    const cardOpacitySlider = document.getElementById('ctrl-card-opacity');
    const cardOpacityVal = document.getElementById('ctrl-card-opacity-val');
    const opVal = card.opacity !== undefined ? card.opacity : (appearanceVal === 'glass' ? 25 : (appearanceVal === 'translucent' ? 45 : 100));
    if (cardOpacitySlider) {
      cardOpacitySlider.value = opVal;
      if (cardOpacityVal) cardOpacityVal.textContent = `${opVal}%`;
    }

    // Border Settings Sync
    const cardBorderToggle = document.getElementById('ctrl-card-border-toggle');
    const cardBorderControls = document.getElementById('ctrl-card-border-controls');
    const isBorderEnabled = card.border_enabled !== false;
    if (cardBorderToggle) cardBorderToggle.checked = isBorderEnabled;
    if (cardBorderControls) cardBorderControls.style.display = isBorderEnabled ? 'block' : 'none';

    const cardBorderOpacitySlider = document.getElementById('ctrl-card-border-opacity');
    const cardBorderOpacityVal = document.getElementById('ctrl-card-border-opacity-val');
    const borderOpVal = card.border_opacity !== undefined ? card.border_opacity : (appearanceVal === 'glass' ? 25 : 30);
    if (cardBorderOpacitySlider) {
      cardBorderOpacitySlider.value = borderOpVal;
      if (cardBorderOpacityVal) cardBorderOpacityVal.textContent = `${borderOpVal}%`;
    }

    const cardRadiusSlider = document.getElementById('ctrl-card-radius');
    const cardRadiusVal = document.getElementById('ctrl-card-radius-val');
    if (cardRadiusSlider && card.border_radius) {
      const num = parseInt(card.border_radius, 10);
      cardRadiusSlider.value = num;
      if (cardRadiusVal) cardRadiusVal.textContent = card.border_radius;
    }

    const cardBorderWidthInput = document.getElementById('ctrl-card-border-width');
    if (cardBorderWidthInput && card.border_width !== undefined) cardBorderWidthInput.value = card.border_width;

    const cardBorderColorPicker = document.getElementById('ctrl-card-border-color');
    const cardBorderColorText = document.getElementById('ctrl-card-border-color-text');
    if (cardBorderColorPicker && card.border_color) cardBorderColorPicker.value = card.border_color;
    if (cardBorderColorText && card.border_color) cardBorderColorText.value = card.border_color;

    const shadowVal = card.shadow || (appearanceVal === 'glass' ? 'medium' : 'subtle');
    document.querySelectorAll('#ctrl-card-shadow-group .segmented-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.shadow === shadowVal);
    });

    const cardBackdropBlurSlider = document.getElementById('ctrl-card-backdrop-blur');
    const cardBackdropBlurVal = document.getElementById('ctrl-card-backdrop-blur-val');
    const blurNum = card.backdrop_blur !== undefined ? card.backdrop_blur : (card.blur !== undefined ? card.blur : (appearanceVal === 'glass' ? 14 : 0));
    if (cardBackdropBlurSlider) {
      cardBackdropBlurSlider.value = blurNum;
      if (cardBackdropBlurVal) cardBackdropBlurVal.textContent = `${blurNum}px`;
    }

    const alignVal = card.alignment || 'center';
    document.querySelectorAll('#ctrl-card-align-group .segmented-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.align === alignVal);
    });

    // Card Position Sync (3x3 Matrix & Fine Sliders)
    const layout = config.layout || {};
    const cardPos = layout.card_position || card.position || 'center';
    let cardX = layout.card_horizontal_position !== undefined ? layout.card_horizontal_position : (card.horizontal_position !== undefined ? card.horizontal_position : 50);
    let cardY = layout.card_vertical_position !== undefined ? layout.card_vertical_position : (card.vertical_position !== undefined ? card.vertical_position : 50);

    const parsedSyncX = parseInt(cardX, 10);
    cardX = Math.max(0, Math.min(100, isNaN(parsedSyncX) ? 50 : parsedSyncX));
    const parsedSyncY = parseInt(cardY, 10);
    cardY = Math.max(0, Math.min(100, isNaN(parsedSyncY) ? 50 : parsedSyncY));

    const cardPosXSlider = document.getElementById('ctrl-card-x');
    const cardPosXVal = document.getElementById('ctrl-card-x-val');
    const cardPosYSlider = document.getElementById('ctrl-card-y');
    const cardPosYVal = document.getElementById('ctrl-card-y-val');
    const cardPosName = document.getElementById('ctrl-card-pos-name');

    if (cardPosXSlider) cardPosXSlider.value = cardX;
    if (cardPosXVal) cardPosXVal.textContent = `${cardX}%`;
    if (cardPosYSlider) cardPosYSlider.value = cardY;
    if (cardPosYVal) cardPosYVal.textContent = `${cardY}%`;

    const posPresetMapSync = {
      '0,0': 'Top Left',
      '50,0': 'Top Center',
      '100,0': 'Top Right',
      '0,50': 'Center Left',
      '50,50': 'Center',
      '100,50': 'Center Right',
      '0,100': 'Bottom Left',
      '50,100': 'Bottom Center',
      '100,100': 'Bottom Right',
    };
    const key = `${cardX},${cardY}`;
    const matchedLabel = posPresetMapSync[key];
    if (cardPosName) {
      cardPosName.textContent = matchedLabel ? `${matchedLabel} (${cardX}%, ${cardY}%)` : `Custom (${cardX}%, ${cardY}%)`;
    }

    document.querySelectorAll('#ctrl-card-pos-matrix .pos-cell-btn').forEach((btn) => {
      const btnX = parseInt(btn.dataset.x, 10);
      const btnY = parseInt(btn.dataset.y, 10);
      btn.classList.toggle('active', btnX === cardX && btnY === cardY);
    });

    // Animations Sync (uses anims declared above)
    const animTypeSelect = document.getElementById('ctrl-anim-type');
    if (animTypeSelect && anims.type) animTypeSelect.value = anims.type;

    const animDurationSlider = document.getElementById('ctrl-anim-duration');
    const animDurationVal = document.getElementById('ctrl-anim-duration-val');
    if (animDurationSlider && anims.duration !== undefined) {
      animDurationSlider.value = anims.duration;
      if (animDurationVal) animDurationVal.textContent = `${anims.duration}ms`;
    }

    const animDelaySlider = document.getElementById('ctrl-anim-delay');
    const animDelayVal = document.getElementById('ctrl-anim-delay-val');
    if (animDelaySlider && anims.delay !== undefined) {
      animDelaySlider.value = anims.delay;
      if (animDelayVal) animDelayVal.textContent = `${anims.delay}ms`;
    }

    const intensityVal = anims.intensity || 'subtle';
    document.querySelectorAll('#ctrl-anim-intensity-group .segmented-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.intensity === intensityVal);
    });

    // Typography Body Size & Align Sync
    const bodySizeSlider = document.getElementById('ctrl-body-size');
    const bodySizeVal = document.getElementById('ctrl-body-size-val');
    if (bodySizeSlider && config.typography?.body_size) {
      const num = parseInt(config.typography.body_size, 10);
      bodySizeSlider.value = num;
      if (bodySizeVal) bodySizeVal.textContent = config.typography.body_size;
    }

    const typoAlignVal = config.typography?.align || 'center';
    document.querySelectorAll('#ctrl-typography-align-group .segmented-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.align === typoAlignVal);
    });

    // Colors
    const colors = config.colors || {};
    ['primary', 'secondary', 'text', 'muted', 'border'].forEach((colorKey) => {
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

    // Sliders for inputs and buttons
    const sliders = [
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

    // Typography Font Family
    if (config.typography?.font_family) {
      const ff = document.getElementById('ctrl-font-family');
      if (ff) {
        ff.value = config.typography.font_family;
        if (!ff.value) {
          const valLower = String(config.typography.font_family).toLowerCase();
          for (let opt of ff.options) {
            if (valLower.includes('jakarta') && opt.value.toLowerCase().includes('jakarta')) { opt.selected = true; break; }
            if (valLower.includes('roboto') && opt.value.toLowerCase().includes('roboto')) { opt.selected = true; break; }
            if (valLower.includes('inter') && opt.value.toLowerCase().includes('inter')) { opt.selected = true; break; }
            if (valLower.includes('system') && opt.value.toLowerCase().includes('system')) { opt.selected = true; break; }
          }
        }
      }
    }
    if (config.typography?.heading_size) {
      const hs = document.getElementById('ctrl-heading-size');
      const hsVal = document.getElementById('ctrl-heading-size-val');
      const hsNum = parseInt(config.typography.heading_size, 10);
      if (hs && !isNaN(hsNum)) hs.value = hsNum;
      if (hsVal) hsVal.textContent = config.typography.heading_size;
    }

    // Template Architecture Sync
    const tpl = config.template || 'modern';
    if (tplSelect) tplSelect.value = tpl;
    document.querySelectorAll('.style-pill-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.template === tpl);
    });

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
        window.currentConfig = currentConfig;
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
          branding: {
            brand_name: 'Auth Platform',
            logo_url: '',
            logo_width: '120px',
            logo_height: '36px',
            logo_scale: 100,
            logo_align: 'center',
            maintain_aspect_ratio: true,
          },
          background: {
            type: 'color',
            color: '#131315',
            gradient: { type: 'linear', start_color: '#0f172a', end_color: '#1e1b4b', angle: 135 },
            image_url: '',
            position: 'center',
            size: 'cover',
            repeat: 'no-repeat',
            overlay: { color: '#000000', opacity: 40 },
            blur: 0,
            brightness: 100,
            saturation: 100,
          },
          theme: {
            mode: 'dark',
          },
          card: {
            width: '420px',
            padding: '32px',
            background_color: '#1B1D21',
            opacity: 100,
            border_radius: '12px',
            border_width: 1,
            border_color: 'rgba(255, 255, 255, 0.08)',
            shadow: 'medium',
            blur: 0,
            alignment: 'center',
          },
          animations: {
            type: 'fade',
            duration: 250,
            delay: 0,
            intensity: 'subtle',
          },
          typography: {
            font_family: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
            heading_size: '24px',
            body_size: '14px',
            align: 'center',
          },
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
        window.currentConfig = currentConfig;
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
