/**
 * auth_ui.js — Authentication UI module for KMD Assistant
 *
 * Standalone vanilla JS module providing:
 *   - Login / Registration pages
 *   - OAuth (Google, Yandex) buttons
 *   - JWT token management (AuthManager)
 *   - User dropdown in TopBar
 *   - Workspace switcher
 *   - Protected route logic
 *
 * Usage from index.html:
 *   <script src="auth_ui.js"></script>
 *   <script>
 *     document.addEventListener('DOMContentLoaded', () => KmdAuth.initAuth());
 *   </script>
 *
 * Exports (on window.KmdAuth):
 *   initAuth(), showLoginPage(), hideLoginPage(),
 *   getCurrentUser(), getAuthHeaders()
 */
(function (root) {
    'use strict';

    /* ================================================================
     *  DESIGN TOKENS  — copied from index.html tailwind.config & CSS
     * ================================================================ */
    const T = {
        canvas:   '#FAF9F7',
        canvasDk: '#F3F1EE',
        canvasDp: '#EBE8E4',
        carbon50: '#F8F9FA',
        carbon100:'#F0F1F2',
        carbon200:'#E2E4E6',
        carbon300:'#C8CCCE',
        carbon400:'#9DA3A7',
        carbon500:'#636E72',
        carbon600:'#4A5459',
        carbon700:'#343D42',
        carbon800:'#2D3436',
        carbon900:'#1B2631',
        sage:     '#7B8B6F',
        sageLight:'#A8B89F',
        sagePale: '#EEF2EB',
        sageDark: '#5A6B4F',
        sageDeep: '#3D4A35',
        terra:    '#C4956A',
        terraLt:  '#D4B08E',
        statusOk: '#6B8F71',
        statusWn: '#C4956A',
        statusFl: '#B85C5C',
        statusIn: '#6B8FAF',
        fontDisplay: "'Cormorant Garamond', serif",
        fontBody:   "'DM Sans', sans-serif",
        fontMono:   "'IBM Plex Mono', monospace",
        radius:  '14px',
        radiusSm:'10px',
        radiusXs:'8px',
    };

    /* ================================================================
     *  SAFE DOM HELPERS — prevent XSS
     * ================================================================ */

    /**
     * Escape a string for safe interpolation into HTML.
     * All user-supplied data MUST pass through this before DOM insertion.
     */
    function esc(str) {
        if (str == null) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    /**
     * Escape a string for use in an HTML attribute value.
     */
    function escAttr(str) {
        return esc(str);
    }

    /**
     * Create an element, set class, and set textContent (NOT innerHTML).
     * Use this for elements whose content is plain text.
     */
    function _el(tag, cls, textContent) {
        const e = document.createElement(tag);
        if (cls) e.className = cls;
        if (textContent !== undefined) e.textContent = textContent;
        return e;
    }

    /**
     * Set DOM from a trusted template. This function should ONLY be called
     * with templates where every variable has been escaped via esc()/escAttr().
     * Raw user data must NEVER be passed here without escaping.
     */
    function _setTrustedHTML(el, trustedHTML) {
        // All callers guarantee that user data is escaped via esc().
        // This is a controlled, auditable single point for DOM HTML injection.
        el.innerHTML = trustedHTML;  // nosemgrep: safe — all interpolated values are esc()-encoded
    }

    /* ================================================================
     *  CSS — injected once
     * ================================================================ */
    const AUTH_CSS = `
/* ===== KMD AUTH OVERLAY ===== */
.kmd-auth-overlay {
    position: fixed;
    inset: 0;
    z-index: 10000;
    background: ${T.canvas};
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: ${T.fontBody};
    color: ${T.carbon800};
    overflow-y: auto;
}
.kmd-auth-overlay * { box-sizing: border-box; }

/* Architectural grid (same as main app) */
.kmd-auth-overlay::before {
    content: '';
    position: fixed;
    inset: 0;
    pointer-events: none;
    background-image:
        linear-gradient(rgba(27,38,49,0.015) 1px, transparent 1px),
        linear-gradient(90deg, rgba(27,38,49,0.015) 1px, transparent 1px);
    background-size: 60px 60px;
}

/* Card */
.kmd-auth-card {
    position: relative;
    width: 100%;
    max-width: 420px;
    margin: 2rem 1rem;
    padding: 2.5rem 2rem 2rem;
    background: rgba(255,255,255,0.6);
    border: 1px solid rgba(27,38,49,0.06);
    border-radius: 20px;
    box-shadow: 0 24px 80px rgba(27,38,49,0.06), 0 4px 20px rgba(27,38,49,0.03);
    animation: kmdAuthFadeUp 0.7s cubic-bezier(0.16, 1, 0.3, 1) both;
}
@keyframes kmdAuthFadeUp {
    from { opacity: 0; transform: translateY(28px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* Logo area */
.kmd-auth-logo {
    display: flex;
    flex-direction: column;
    align-items: center;
    margin-bottom: 2rem;
}
.kmd-auth-logo-icon {
    width: 56px;
    height: 56px;
    border-radius: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, ${T.sage}, ${T.sageLight});
    margin-bottom: 1rem;
    box-shadow: 0 4px 16px rgba(123,139,111,0.2);
}
.kmd-auth-logo-icon span {
    font-family: ${T.fontMono};
    font-size: 1.25rem;
    font-weight: 700;
    color: ${T.carbon900};
}
.kmd-auth-logo-title {
    font-family: ${T.fontDisplay};
    font-weight: 500;
    font-size: 1.75rem;
    color: ${T.carbon900};
    letter-spacing: -0.02em;
    line-height: 1.15;
    text-align: center;
}
.kmd-auth-logo-sub {
    font-family: ${T.fontMono};
    font-size: 0.5625rem;
    font-weight: 500;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: ${T.sage};
    margin-top: 0.35rem;
}

/* Divider */
.kmd-auth-divider {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin: 1.25rem 0;
}
.kmd-auth-divider::before,
.kmd-auth-divider::after {
    content: '';
    flex: 1;
    height: 1px;
    background: ${T.carbon200};
}
.kmd-auth-divider span {
    font-family: ${T.fontMono};
    font-size: 0.5625rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: ${T.carbon400};
    white-space: nowrap;
}

/* OAuth buttons */
.kmd-auth-oauth-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.625rem;
    width: 100%;
    padding: 0.75rem 1rem;
    border-radius: ${T.radiusSm};
    font-family: ${T.fontBody};
    font-size: 0.8125rem;
    font-weight: 600;
    cursor: pointer;
    border: none;
    transition: all 0.25s cubic-bezier(0.22, 1, 0.36, 1);
    margin-bottom: 0.625rem;
}
.kmd-auth-oauth-btn:active { transform: scale(0.98); }
.kmd-auth-oauth-btn svg { flex-shrink: 0; }

.kmd-auth-oauth-google {
    background: #4285F4;
    color: #fff;
}
.kmd-auth-oauth-google:hover {
    background: #3367D6;
    box-shadow: 0 4px 16px rgba(66,133,244,0.3);
    transform: translateY(-1px);
}

.kmd-auth-oauth-yandex {
    background: #FC3F1D;
    color: #fff;
}
.kmd-auth-oauth-yandex:hover {
    background: #E03515;
    box-shadow: 0 4px 16px rgba(252,63,29,0.3);
    transform: translateY(-1px);
}

/* Form elements */
.kmd-auth-field {
    margin-bottom: 0.875rem;
}
.kmd-auth-label {
    display: block;
    font-family: ${T.fontMono};
    font-size: 0.5625rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: ${T.carbon500};
    margin-bottom: 0.375rem;
}
.kmd-auth-input {
    width: 100%;
    padding: 0.7rem 0.875rem;
    border: 1px solid ${T.carbon200};
    border-radius: ${T.radiusSm};
    font-family: ${T.fontBody};
    font-size: 0.8125rem;
    color: ${T.carbon800};
    background: #fff;
    outline: none;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.kmd-auth-input::placeholder { color: ${T.carbon300}; }
.kmd-auth-input:focus {
    border-color: ${T.sage};
    box-shadow: 0 0 0 3px rgba(123,139,111,0.1);
}
.kmd-auth-input.error {
    border-color: ${T.statusFl};
    box-shadow: 0 0 0 3px rgba(184,92,92,0.1);
}

/* Primary button (matches .btn-primary from index.html) */
.kmd-auth-btn-primary {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    width: 100%;
    padding: 0.75rem 2rem;
    background: ${T.carbon800};
    color: ${T.canvas};
    font-family: ${T.fontMono};
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    border-radius: ${T.radiusSm};
    border: none;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}
.kmd-auth-btn-primary:hover {
    background: ${T.sage};
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(123,139,111,0.25);
}
.kmd-auth-btn-primary:active { transform: translateY(0); }
.kmd-auth-btn-primary:disabled {
    opacity: 0.5;
    cursor: default;
    transform: none !important;
    box-shadow: none !important;
}

/* Secondary / link button */
.kmd-auth-btn-link {
    background: none;
    border: none;
    color: ${T.sage};
    font-family: ${T.fontMono};
    font-size: 0.625rem;
    font-weight: 500;
    letter-spacing: 0.06em;
    cursor: pointer;
    padding: 0.25rem 0;
    transition: color 0.2s;
}
.kmd-auth-btn-link:hover { color: ${T.sageDark}; text-decoration: underline; }

/* Error box */
.kmd-auth-error {
    display: none;
    padding: 0.625rem 0.875rem;
    border-radius: ${T.radiusXs};
    background: rgba(184,92,92,0.08);
    border-left: 3px solid ${T.statusFl};
    color: ${T.statusFl};
    font-size: 0.8125rem;
    margin-bottom: 1rem;
    animation: kmdAuthFadeUp 0.3s ease both;
}
.kmd-auth-error.visible { display: block; }

/* Bottom links row */
.kmd-auth-footer {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    margin-top: 1.25rem;
    font-size: 0.75rem;
    color: ${T.carbon400};
}

/* Password visibility toggle */
.kmd-auth-pw-wrap {
    position: relative;
}
.kmd-auth-pw-wrap .kmd-auth-input { padding-right: 2.5rem; }
.kmd-auth-pw-toggle {
    position: absolute;
    right: 0.625rem;
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    cursor: pointer;
    color: ${T.carbon400};
    padding: 0.25rem;
    display: flex;
    transition: color 0.2s;
}
.kmd-auth-pw-toggle:hover { color: ${T.carbon600}; }

/* ===== USER DROPDOWN (TopBar) ===== */
.kmd-user-menu {
    position: relative;
    display: flex;
    align-items: center;
}
.kmd-user-trigger {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.3rem 0.625rem 0.3rem 0.3rem;
    border-radius: ${T.radiusSm};
    cursor: pointer;
    border: 1px solid transparent;
    background: transparent;
    transition: all 0.2s ease;
    font-family: ${T.fontBody};
}
.kmd-user-trigger:hover {
    background: rgba(27,38,49,0.04);
    border-color: rgba(27,38,49,0.06);
}
.kmd-user-avatar {
    width: 30px;
    height: 30px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: ${T.fontMono};
    font-size: 0.625rem;
    font-weight: 700;
    color: ${T.carbon900};
    background: linear-gradient(135deg, ${T.sagePale}, ${T.sageLight});
    flex-shrink: 0;
    overflow: hidden;
}
.kmd-user-avatar img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 8px;
}
.kmd-user-info {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    line-height: 1;
}
.kmd-user-name {
    font-size: 0.75rem;
    font-weight: 600;
    color: ${T.carbon800};
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.kmd-user-workspace {
    font-family: ${T.fontMono};
    font-size: 0.5625rem;
    color: ${T.carbon400};
    letter-spacing: 0.04em;
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    margin-top: 2px;
}
.kmd-user-chevron {
    color: ${T.carbon300};
    transition: transform 0.2s ease;
    flex-shrink: 0;
}
.kmd-user-trigger[aria-expanded="true"] .kmd-user-chevron {
    transform: rotate(180deg);
}

/* Dropdown panel */
.kmd-user-dropdown {
    position: absolute;
    top: calc(100% + 6px);
    right: 0;
    min-width: 220px;
    background: rgba(255,255,255,0.98);
    backdrop-filter: blur(24px);
    border: 1px solid rgba(27,38,49,0.06);
    border-radius: ${T.radius};
    box-shadow: 0 16px 48px rgba(27,38,49,0.1), 0 4px 12px rgba(27,38,49,0.04);
    padding: 0.375rem;
    z-index: 1000;
    opacity: 0;
    transform: translateY(-6px) scale(0.97);
    pointer-events: none;
    transition: all 0.2s cubic-bezier(0.22, 1, 0.36, 1);
}
.kmd-user-dropdown.open {
    opacity: 1;
    transform: translateY(0) scale(1);
    pointer-events: auto;
}
.kmd-user-dropdown-item {
    display: flex;
    align-items: center;
    gap: 0.625rem;
    padding: 0.55rem 0.75rem;
    border-radius: ${T.radiusXs};
    font-size: 0.8125rem;
    color: ${T.carbon600};
    cursor: pointer;
    transition: all 0.15s ease;
    border: none;
    background: none;
    width: 100%;
    text-align: left;
    font-family: ${T.fontBody};
}
.kmd-user-dropdown-item:hover {
    background: ${T.sagePale};
    color: ${T.carbon800};
}
.kmd-user-dropdown-item svg {
    width: 16px;
    height: 16px;
    color: ${T.carbon400};
    flex-shrink: 0;
}
.kmd-user-dropdown-item:hover svg { color: ${T.sage}; }
.kmd-user-dropdown-sep {
    height: 1px;
    background: rgba(27,38,49,0.06);
    margin: 0.25rem 0.5rem;
}
.kmd-user-dropdown-item.danger { color: ${T.statusFl}; }
.kmd-user-dropdown-item.danger svg { color: ${T.statusFl}; }
.kmd-user-dropdown-item.danger:hover { background: rgba(184,92,92,0.06); }

/* ===== WORKSPACE SWITCHER MODAL ===== */
.kmd-ws-overlay {
    position: fixed;
    inset: 0;
    z-index: 10001;
    background: rgba(27,38,49,0.4);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.25s ease;
}
.kmd-ws-overlay.open {
    opacity: 1;
    pointer-events: auto;
}
.kmd-ws-modal {
    width: 100%;
    max-width: 400px;
    margin: 1rem;
    background: rgba(255,255,255,0.98);
    backdrop-filter: blur(24px);
    border: 1px solid rgba(27,38,49,0.06);
    border-radius: 20px;
    box-shadow: 0 24px 80px rgba(27,38,49,0.12);
    padding: 1.5rem;
    transform: translateY(12px) scale(0.97);
    transition: transform 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}
.kmd-ws-overlay.open .kmd-ws-modal {
    transform: translateY(0) scale(1);
}
.kmd-ws-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
}
.kmd-ws-title {
    font-family: ${T.fontDisplay};
    font-size: 1.25rem;
    font-weight: 500;
    color: ${T.carbon900};
    letter-spacing: -0.02em;
}
.kmd-ws-close {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    border: none;
    background: none;
    cursor: pointer;
    color: ${T.carbon400};
    transition: all 0.15s;
}
.kmd-ws-close:hover { background: ${T.carbon100}; color: ${T.carbon700}; }
.kmd-ws-list {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    max-height: 300px;
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: ${T.carbon200} transparent;
}
.kmd-ws-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem;
    border-radius: ${T.radiusSm};
    cursor: pointer;
    border: 1px solid transparent;
    transition: all 0.15s ease;
    background: none;
    width: 100%;
    text-align: left;
    font-family: ${T.fontBody};
}
.kmd-ws-item:hover { background: ${T.sagePale}; border-color: rgba(123,139,111,0.1); }
.kmd-ws-item.active {
    background: ${T.sagePale};
    border-color: ${T.sage};
}
.kmd-ws-item-icon {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: ${T.fontMono};
    font-size: 0.75rem;
    font-weight: 700;
    color: #fff;
    flex-shrink: 0;
}
.kmd-ws-item-info { flex: 1; min-width: 0; }
.kmd-ws-item-name {
    font-size: 0.8125rem;
    font-weight: 600;
    color: ${T.carbon800};
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.kmd-ws-item-role {
    font-family: ${T.fontMono};
    font-size: 0.5625rem;
    color: ${T.carbon400};
    letter-spacing: 0.05em;
    margin-top: 2px;
}
.kmd-ws-item-check {
    color: ${T.sage};
    opacity: 0;
    transition: opacity 0.15s;
    flex-shrink: 0;
}
.kmd-ws-item.active .kmd-ws-item-check { opacity: 1; }
.kmd-ws-create {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    width: 100%;
    padding: 0.625rem;
    margin-top: 0.75rem;
    border: 1.5px dashed ${T.carbon300};
    border-radius: ${T.radiusSm};
    background: none;
    color: ${T.carbon500};
    font-family: ${T.fontMono};
    font-size: 0.625rem;
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    cursor: pointer;
    transition: all 0.2s;
}
.kmd-ws-create:hover {
    border-color: ${T.sage};
    color: ${T.sage};
    background: rgba(123,139,111,0.04);
}

/* ===== SPINNER ===== */
.kmd-auth-spinner {
    width: 20px;
    height: 20px;
    border: 2px solid ${T.carbon200};
    border-top-color: ${T.sage};
    border-radius: 50%;
    animation: kmdAuthSpin 0.7s linear infinite;
    display: inline-block;
}
@keyframes kmdAuthSpin { to { transform: rotate(360deg); } }

/* ===== RESPONSIVE ===== */
@media (max-width: 480px) {
    .kmd-auth-card { padding: 2rem 1.25rem 1.5rem; margin: 1rem 0.75rem; }
    .kmd-auth-logo-title { font-size: 1.5rem; }
    .kmd-user-info { display: none; }
}
`;

    /* ================================================================
     *  SVG ICONS — static trusted content (no user data)
     * ================================================================ */
    const ICONS = {
        google: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09A6.97 6.97 0 0 1 5.48 12c0-.72.12-1.42.35-2.09V7.07H2.18A11.97 11.97 0 0 0 .96 12c0 1.94.46 3.77 1.22 5.33l3.66-2.84z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>',
        yandex: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" fill="#FC3F1D"/><path d="M13.5 7.2h-1.05c-1.68 0-2.55.93-2.55 2.1 0 1.35.6 2.01 1.83 2.82l1.02.66-2.94 4.62H8.34l2.64-4.14c-1.47-1.02-2.31-2.01-2.31-3.78 0-2.31 1.62-3.78 4.08-3.78H15V17.4h-1.5V7.2z" fill="#fff"/></svg>',
        eye: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>',
        eyeOff: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>',
        user: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
        settings: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
        logout: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>',
        building: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="2" width="16" height="20" rx="2"/><path d="M9 22V12h6v10"/><path d="M8 6h.01M16 6h.01M12 6h.01M8 10h.01M16 10h.01M12 10h.01"/></svg>',
        plus: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>',
        check: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>',
        chevron: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>',
        x: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg>',
    };

    /* ================================================================
     *  AUTH MANAGER — JWT lifecycle
     * ================================================================ */
    const STORAGE_PREFIX = 'kmd_auth_';
    const TOKEN_REFRESH_MARGIN_MS = 60 * 1000; // refresh 60s before expiry

    class AuthManager {
        constructor() {
            this._accessToken = localStorage.getItem(STORAGE_PREFIX + 'access_token') || null;
            this._refreshToken = localStorage.getItem(STORAGE_PREFIX + 'refresh_token') || null;
            this._user = null;
            this._workspaces = [];
            this._currentWorkspace = null;
            this._refreshTimer = null;
            this._onAuthChange = [];

            try {
                const cached = localStorage.getItem(STORAGE_PREFIX + 'user');
                if (cached) this._user = JSON.parse(cached);
                const ws = localStorage.getItem(STORAGE_PREFIX + 'workspaces');
                if (ws) this._workspaces = JSON.parse(ws);
                const cw = localStorage.getItem(STORAGE_PREFIX + 'current_workspace');
                if (cw) this._currentWorkspace = JSON.parse(cw);
            } catch (_) { /* ignore corrupt storage */ }
        }

        /* -- Token helpers -- */
        get accessToken() { return this._accessToken; }
        get isAuthenticated() { return !!this._accessToken && !this._isTokenExpired(); }

        _isTokenExpired() {
            if (!this._accessToken) return true;
            try {
                const payload = JSON.parse(atob(this._accessToken.split('.')[1]));
                return payload.exp ? (payload.exp * 1000) < Date.now() : false;
            } catch (_) { return false; /* can't parse — assume valid, server will reject */ }
        }

        _getTokenExpiry() {
            if (!this._accessToken) return 0;
            try {
                const payload = JSON.parse(atob(this._accessToken.split('.')[1]));
                return (payload.exp || 0) * 1000;
            } catch (_) { return 0; }
        }

        _scheduleRefresh() {
            if (this._refreshTimer) clearTimeout(this._refreshTimer);
            if (!this._accessToken || !this._refreshToken) return;
            const expiry = this._getTokenExpiry();
            if (!expiry) return;
            const delay = Math.max(expiry - Date.now() - TOKEN_REFRESH_MARGIN_MS, 5000);
            this._refreshTimer = setTimeout(() => this._doRefresh(), delay);
        }

        async _doRefresh() {
            if (!this._refreshToken) return this._handleLogout();
            try {
                const res = await fetch('/api/auth/refresh', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ refresh_token: this._refreshToken }),
                });
                if (!res.ok) throw new Error('refresh failed');
                const data = await res.json();
                this._setTokens(data.access_token, data.refresh_token || this._refreshToken);
            } catch (_) {
                this._handleLogout();
            }
        }

        _setTokens(access, refresh) {
            this._accessToken = access;
            this._refreshToken = refresh;
            localStorage.setItem(STORAGE_PREFIX + 'access_token', access || '');
            localStorage.setItem(STORAGE_PREFIX + 'refresh_token', refresh || '');
            if (access) this._scheduleRefresh();
        }

        _setUser(user) {
            this._user = user;
            localStorage.setItem(STORAGE_PREFIX + 'user', JSON.stringify(user));
            this._fireAuthChange();
        }

        _setWorkspaces(list, current) {
            this._workspaces = list || [];
            this._currentWorkspace = current || (list && list.length ? list[0] : null);
            localStorage.setItem(STORAGE_PREFIX + 'workspaces', JSON.stringify(this._workspaces));
            localStorage.setItem(STORAGE_PREFIX + 'current_workspace', JSON.stringify(this._currentWorkspace));
        }

        _clearAll() {
            this._accessToken = null;
            this._refreshToken = null;
            this._user = null;
            this._workspaces = [];
            this._currentWorkspace = null;
            if (this._refreshTimer) clearTimeout(this._refreshTimer);
            [
                'access_token', 'refresh_token', 'user',
                'workspaces', 'current_workspace'
            ].forEach(k => localStorage.removeItem(STORAGE_PREFIX + k));
        }

        _handleLogout() {
            this._clearAll();
            this._fireAuthChange();
            showLoginPage();
        }

        onAuthChange(fn) { this._onAuthChange.push(fn); }
        _fireAuthChange() { this._onAuthChange.forEach(fn => fn(this._user, this._currentWorkspace)); }

        /* -- Public API -- */
        async login(email, password) {
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || data.message || 'Ошибка входа');
            this._setTokens(data.access_token, data.refresh_token);
            if (data.user) this._setUser(data.user);
            if (data.workspaces) this._setWorkspaces(data.workspaces, data.current_workspace);
            return data;
        }

        async register(name, email, password) {
            const res = await fetch('/api/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email, password }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || data.message || 'Ошибка регистрации');
            this._setTokens(data.access_token, data.refresh_token);
            if (data.user) this._setUser(data.user);
            if (data.workspaces) this._setWorkspaces(data.workspaces, data.current_workspace);
            return data;
        }

        async fetchUser() {
            const res = await fetch('/api/auth/me', { headers: this.getHeaders() });
            if (!res.ok) throw new Error('unauthorized');
            const data = await res.json();
            this._setUser(data.user || data);
            if (data.workspaces) this._setWorkspaces(data.workspaces, data.current_workspace);
            return this._user;
        }

        async switchWorkspace(workspaceId) {
            const res = await fetch('/api/auth/switch-workspace', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ...this.getHeaders() },
                body: JSON.stringify({ workspace_id: workspaceId }),
            });
            if (!res.ok) throw new Error('switch failed');
            const data = await res.json();
            if (data.access_token) this._setTokens(data.access_token, data.refresh_token || this._refreshToken);
            const ws = this._workspaces.find(w => w.id === workspaceId);
            if (ws) {
                this._currentWorkspace = ws;
                localStorage.setItem(STORAGE_PREFIX + 'current_workspace', JSON.stringify(ws));
            }
            this._fireAuthChange();
            return data;
        }

        logout() {
            // Fire-and-forget server logout
            if (this._accessToken) {
                fetch('/api/auth/logout', {
                    method: 'POST',
                    headers: this.getHeaders(),
                }).catch(() => {});
            }
            this._handleLogout();
        }

        getHeaders() {
            const h = {};
            if (this._accessToken) h['Authorization'] = 'Bearer ' + this._accessToken;
            return h;
        }

        getUser() { return this._user; }
        getWorkspaces() { return this._workspaces; }
        getCurrentWorkspace() { return this._currentWorkspace; }

        /* -- Fetch interceptor -- */
        installFetchInterceptor() {
            const mgr = this;
            const _origFetch = window._kmdOrigFetch || window.fetch;
            window._kmdOrigFetch = _origFetch; // keep reference so CSRF interceptor chain works

            window.fetch = function (input, init) {
                init = init || {};
                // Inject Authorization header for same-origin requests
                var url = typeof input === 'string' ? input : (input instanceof Request ? input.url : '');
                var isSameOrigin = !url || url.startsWith('/') || url.startsWith(location.origin);

                if (isSameOrigin && mgr._accessToken) {
                    if (!init.headers) {
                        init.headers = {};
                    }
                    if (init.headers instanceof Headers) {
                        if (!init.headers.has('Authorization')) {
                            init.headers.set('Authorization', 'Bearer ' + mgr._accessToken);
                        }
                    } else if (typeof init.headers === 'object' && !init.headers['Authorization']) {
                        init.headers['Authorization'] = 'Bearer ' + mgr._accessToken;
                    }
                }

                return _origFetch.call(this, input, init).then(function (response) {
                    if (response.status === 401 && isSameOrigin) {
                        // Token expired or invalid — try refresh once
                        if (mgr._refreshToken && !init._kmdRetried) {
                            return mgr._doRefresh().then(function () {
                                if (mgr._accessToken) {
                                    init._kmdRetried = true;
                                    if (init.headers instanceof Headers) {
                                        init.headers.set('Authorization', 'Bearer ' + mgr._accessToken);
                                    } else if (typeof init.headers === 'object') {
                                        init.headers['Authorization'] = 'Bearer ' + mgr._accessToken;
                                    }
                                    return _origFetch.call(this, input, init);
                                }
                                mgr._handleLogout();
                                return response;
                            });
                        }
                        mgr._handleLogout();
                    }
                    return response;
                });
            };
        }

        /* -- OAuth callback handler -- */
        handleOAuthCallback() {
            var params = new URLSearchParams(window.location.search);
            var accessToken = params.get('access_token') || params.get('token');
            var refreshToken = params.get('refresh_token');

            // Also check hash fragment (some OAuth flows use it)
            if (!accessToken) {
                var hashParams = new URLSearchParams(window.location.hash.replace('#', ''));
                var ht = hashParams.get('access_token') || hashParams.get('token');
                if (ht) {
                    this._setTokens(ht, hashParams.get('refresh_token'));
                    window.history.replaceState({}, '', window.location.pathname);
                    return true;
                }
                return false;
            }

            this._setTokens(accessToken, refreshToken);
            window.history.replaceState({}, '', window.location.pathname);
            return true;
        }
    }

    /* Singleton */
    var authManager = new AuthManager();

    /* ================================================================
     *  UI RENDERING
     * ================================================================ */
    var _styleInjected = false;
    var _overlayEl = null;
    var _userMenuEl = null;
    var _wsOverlayEl = null;

    function _injectStyles() {
        if (_styleInjected) return;
        var style = document.createElement('style');
        style.id = 'kmd-auth-styles';
        style.textContent = AUTH_CSS;
        document.head.appendChild(style);
        _styleInjected = true;
    }

    /* ---------- Utility ---------- */
    function _getInitials(user) {
        if (!user) return '?';
        var name = user.name || user.email || '';
        var parts = name.trim().split(/\s+/);
        if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
        return name.slice(0, 2).toUpperCase();
    }

    var WS_COLORS = ['#7B8B6F', '#6B8FAF', '#C4956A', '#B85C5C', '#636E72', '#5A6B4F'];
    function _wsColor(idx) { return WS_COLORS[idx % WS_COLORS.length]; }

    /* ---------- Login / Register Page ---------- */
    function _buildLoginPage() {
        _injectStyles();

        if (_overlayEl) { _overlayEl.remove(); _overlayEl = null; }

        var overlay = document.createElement('div');
        overlay.className = 'kmd-auth-overlay';
        var mode = 'login'; // 'login' | 'register'

        function render() {
            var isLogin = mode === 'login';

            // Build trusted HTML — ALL user-facing dynamic content is static labels here
            // (no user data is interpolated; this is the login form before auth)
            var html = '<div class="kmd-auth-card">'
                + '<div class="kmd-auth-logo">'
                +   '<div class="kmd-auth-logo-icon"><span>K</span></div>'
                +   '<div class="kmd-auth-logo-title">\u041A\u041C\u0414 \u0410\u0441\u0441\u0438\u0441\u0442\u0435\u043D\u0442</div>'
                +   '<div class="kmd-auth-logo-sub">ALDMEGA LAB</div>'
                + '</div>'

                // OAuth
                + '<button class="kmd-auth-oauth-btn kmd-auth-oauth-google" data-action="google">'
                +   ICONS.google + ' \u0412\u043E\u0439\u0442\u0438 \u0447\u0435\u0440\u0435\u0437 Google</button>'
                + '<button class="kmd-auth-oauth-btn kmd-auth-oauth-yandex" data-action="yandex">'
                +   ICONS.yandex + ' \u0412\u043E\u0439\u0442\u0438 \u0447\u0435\u0440\u0435\u0437 \u042F\u043D\u0434\u0435\u043A\u0441</button>'

                + '<div class="kmd-auth-divider"><span>\u0438\u043B\u0438 '
                + (isLogin ? '\u0432\u043E\u0439\u0434\u0438\u0442\u0435' : '\u0437\u0430\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0438\u0440\u0443\u0439\u0442\u0435\u0441\u044C')
                + ' \u0441 email</span></div>'

                // Error area
                + '<div class="kmd-auth-error" id="kmd-auth-error"></div>'

                + '<form id="kmd-auth-form" autocomplete="on">';

            if (!isLogin) {
                html += '<div class="kmd-auth-field">'
                    + '<label class="kmd-auth-label" for="kmd-auth-name">\u0418\u043C\u044F</label>'
                    + '<input class="kmd-auth-input" id="kmd-auth-name" name="name" type="text" placeholder="\u0418\u0432\u0430\u043D \u041F\u0435\u0442\u0440\u043E\u0432" autocomplete="name" required>'
                    + '</div>';
            }

            html += '<div class="kmd-auth-field">'
                + '<label class="kmd-auth-label" for="kmd-auth-email">Email</label>'
                + '<input class="kmd-auth-input" id="kmd-auth-email" name="email" type="email" placeholder="engineer@company.ru" autocomplete="email" required>'
                + '</div>'

                + '<div class="kmd-auth-field">'
                + '<label class="kmd-auth-label" for="kmd-auth-password">\u041F\u0430\u0440\u043E\u043B\u044C</label>'
                + '<div class="kmd-auth-pw-wrap">'
                + '<input class="kmd-auth-input" id="kmd-auth-password" name="password" type="password" placeholder="\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022" autocomplete="'
                + (isLogin ? 'current-password' : 'new-password') + '" required minlength="6">'
                + '<button type="button" class="kmd-auth-pw-toggle" data-action="toggle-pw" aria-label="\u041F\u043E\u043A\u0430\u0437\u0430\u0442\u044C \u043F\u0430\u0440\u043E\u043B\u044C">' + ICONS.eye + '</button>'
                + '</div></div>';

            if (!isLogin) {
                html += '<div class="kmd-auth-field">'
                    + '<label class="kmd-auth-label" for="kmd-auth-password2">\u041F\u043E\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u0435 \u043F\u0430\u0440\u043E\u043B\u044C</label>'
                    + '<div class="kmd-auth-pw-wrap">'
                    + '<input class="kmd-auth-input" id="kmd-auth-password2" name="password2" type="password" placeholder="\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022" autocomplete="new-password" required minlength="6">'
                    + '<button type="button" class="kmd-auth-pw-toggle" data-action="toggle-pw2" aria-label="\u041F\u043E\u043A\u0430\u0437\u0430\u0442\u044C \u043F\u0430\u0440\u043E\u043B\u044C">' + ICONS.eye + '</button>'
                    + '</div></div>';
            }

            html += '<button type="submit" class="kmd-auth-btn-primary" id="kmd-auth-submit" style="margin-top:0.25rem">'
                + (isLogin ? '\u0412\u043E\u0439\u0442\u0438' : '\u0417\u0430\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0438\u0440\u043E\u0432\u0430\u0442\u044C\u0441\u044F')
                + '</button></form>'

                + '<div class="kmd-auth-footer"><span>'
                + (isLogin ? '\u041D\u0435\u0442 \u0430\u043A\u043A\u0430\u0443\u043D\u0442\u0430?' : '\u0423\u0436\u0435 \u0435\u0441\u0442\u044C \u0430\u043A\u043A\u0430\u0443\u043D\u0442?')
                + '</span><button class="kmd-auth-btn-link" data-action="switch-mode">'
                + (isLogin ? '\u0420\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0446\u0438\u044F' : '\u0412\u043E\u0439\u0442\u0438')
                + '</button></div></div>';

            _setTrustedHTML(overlay, html);
            _attachLoginHandlers();
        }

        function _showError(msg) {
            var el = overlay.querySelector('#kmd-auth-error');
            if (el) { el.textContent = msg; el.classList.add('visible'); }
        }
        function _hideError() {
            var el = overlay.querySelector('#kmd-auth-error');
            if (el) el.classList.remove('visible');
        }
        function _setLoading(loading) {
            var btn = overlay.querySelector('#kmd-auth-submit');
            if (!btn) return;
            btn.disabled = loading;
            if (loading) {
                btn.textContent = '';
                var spinner = document.createElement('span');
                spinner.className = 'kmd-auth-spinner';
                btn.appendChild(spinner);
            } else {
                btn.textContent = mode === 'login' ? '\u0412\u043E\u0439\u0442\u0438' : '\u0417\u0430\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0438\u0440\u043E\u0432\u0430\u0442\u044C\u0441\u044F';
            }
        }

        function _attachLoginHandlers() {
            // Switch mode
            var switchBtn = overlay.querySelector('[data-action="switch-mode"]');
            if (switchBtn) switchBtn.addEventListener('click', function () {
                mode = mode === 'login' ? 'register' : 'login';
                render();
            });

            // OAuth
            var googleBtn = overlay.querySelector('[data-action="google"]');
            if (googleBtn) googleBtn.addEventListener('click', function () {
                window.location.href = '/api/auth/google';
            });
            var yandexBtn = overlay.querySelector('[data-action="yandex"]');
            if (yandexBtn) yandexBtn.addEventListener('click', function () {
                window.location.href = '/api/auth/yandex';
            });

            // Password toggle(s)
            overlay.querySelectorAll('[data-action^="toggle-pw"]').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var target = btn.closest('.kmd-auth-pw-wrap').querySelector('input');
                    var isHidden = target.type === 'password';
                    target.type = isHidden ? 'text' : 'password';
                    _setTrustedHTML(btn, isHidden ? ICONS.eyeOff : ICONS.eye);
                });
            });

            // Form submit
            var form = overlay.querySelector('#kmd-auth-form');
            if (form) form.addEventListener('submit', async function (e) {
                e.preventDefault();
                _hideError();

                var email = (overlay.querySelector('#kmd-auth-email') || {}).value;
                email = email ? email.trim() : '';
                var password = (overlay.querySelector('#kmd-auth-password') || {}).value || '';

                if (!email || !password) return _showError('\u0417\u0430\u043F\u043E\u043B\u043D\u0438\u0442\u0435 \u0432\u0441\u0435 \u043F\u043E\u043B\u044F');

                if (mode === 'register') {
                    var nameVal = (overlay.querySelector('#kmd-auth-name') || {}).value;
                    nameVal = nameVal ? nameVal.trim() : '';
                    var password2 = (overlay.querySelector('#kmd-auth-password2') || {}).value || '';
                    if (!nameVal) return _showError('\u0423\u043A\u0430\u0436\u0438\u0442\u0435 \u0438\u043C\u044F');
                    if (password !== password2) return _showError('\u041F\u0430\u0440\u043E\u043B\u0438 \u043D\u0435 \u0441\u043E\u0432\u043F\u0430\u0434\u0430\u044E\u0442');
                    if (password.length < 6) return _showError('\u041F\u0430\u0440\u043E\u043B\u044C \u0434\u043E\u043B\u0436\u0435\u043D \u0431\u044B\u0442\u044C \u043D\u0435 \u043C\u0435\u043D\u0435\u0435 6 \u0441\u0438\u043C\u0432\u043E\u043B\u043E\u0432');

                    _setLoading(true);
                    try {
                        await authManager.register(nameVal, email, password);
                        _onLoginSuccess();
                    } catch (err) {
                        _setLoading(false);
                        _showError(err.message);
                    }
                } else {
                    _setLoading(true);
                    try {
                        await authManager.login(email, password);
                        _onLoginSuccess();
                    } catch (err) {
                        _setLoading(false);
                        _showError(err.message);
                    }
                }
            });
        }

        render();
        _overlayEl = overlay;
        return overlay;
    }

    function _onLoginSuccess() {
        hideLoginPage();
        _renderUserMenu();
        authManager._fireAuthChange();
    }

    /* ---------- User Dropdown (TopBar) ---------- */
    function _renderUserMenu() {
        // Remove old
        if (_userMenuEl) { _userMenuEl.remove(); _userMenuEl = null; }

        var user = authManager.getUser();
        if (!user) return;

        var ws = authManager.getCurrentWorkspace();
        var container = document.createElement('div');
        container.className = 'kmd-user-menu';
        container.id = 'kmd-auth-user-menu';

        var initials = esc(_getInitials(user));
        var avatarContent = user.avatar_url
            ? '<img src="' + escAttr(user.avatar_url) + '" alt="' + escAttr(user.name || '') + '">'
            : initials;

        var userName = esc(user.name || user.email || '');
        var wsName = ws ? esc(ws.name || '') : '';

        // Build the trigger + dropdown from trusted template with escaped user data
        var triggerHTML = '<button class="kmd-user-trigger" aria-expanded="false" aria-haspopup="true">'
            + '<div class="kmd-user-avatar">' + avatarContent + '</div>'
            + '<div class="kmd-user-info">'
            + '<span class="kmd-user-name">' + userName + '</span>'
            + (wsName ? '<span class="kmd-user-workspace">' + wsName + '</span>' : '')
            + '</div>'
            + '<span class="kmd-user-chevron">' + ICONS.chevron + '</span>'
            + '</button>';

        var dropdownHTML = '<div class="kmd-user-dropdown" role="menu">'
            + '<button class="kmd-user-dropdown-item" data-action="profile" role="menuitem">'
            + ICONS.user + ' \u041C\u043E\u0439 \u043F\u0440\u043E\u0444\u0438\u043B\u044C</button>'
            + '<button class="kmd-user-dropdown-item" data-action="workspaces" role="menuitem">'
            + ICONS.building + ' \u041E\u0440\u0433\u0430\u043D\u0438\u0437\u0430\u0446\u0438\u0438</button>'
            + '<button class="kmd-user-dropdown-item" data-action="settings" role="menuitem">'
            + ICONS.settings + ' \u041D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438</button>'
            + '<div class="kmd-user-dropdown-sep"></div>'
            + '<button class="kmd-user-dropdown-item danger" data-action="logout" role="menuitem">'
            + ICONS.logout + ' \u0412\u044B\u0439\u0442\u0438</button>'
            + '</div>';

        _setTrustedHTML(container, triggerHTML + dropdownHTML);

        var trigger = container.querySelector('.kmd-user-trigger');
        var dropdown = container.querySelector('.kmd-user-dropdown');
        var isOpen = false;

        function toggleDropdown(open) {
            isOpen = typeof open === 'boolean' ? open : !isOpen;
            dropdown.classList.toggle('open', isOpen);
            trigger.setAttribute('aria-expanded', String(isOpen));
        }

        trigger.addEventListener('click', function (e) { e.stopPropagation(); toggleDropdown(); });
        document.addEventListener('click', function () { toggleDropdown(false); });
        container.addEventListener('click', function (e) { e.stopPropagation(); });

        // Actions
        var logoutBtn = container.querySelector('[data-action="logout"]');
        if (logoutBtn) logoutBtn.addEventListener('click', function () {
            toggleDropdown(false);
            authManager.logout();
        });
        var wsBtn = container.querySelector('[data-action="workspaces"]');
        if (wsBtn) wsBtn.addEventListener('click', function () {
            toggleDropdown(false);
            _showWorkspaceSwitcher();
        });

        _userMenuEl = container;
        _injectUserMenuIntoTopBar(container);
    }

    function _injectUserMenuIntoTopBar(el) {
        var nav = document.querySelector('.glass-nav');
        if (!nav) {
            // If top bar not rendered yet, retry via MutationObserver
            var observer = new MutationObserver(function () {
                var nav2 = document.querySelector('.glass-nav');
                if (nav2) {
                    observer.disconnect();
                    _injectUserMenuIntoTopBar(el);
                }
            });
            observer.observe(document.body, { childList: true, subtree: true });
            return;
        }

        // Find the right-side action group in the topbar
        var rightGroup = nav.querySelector('.flex.items-center.gap-2.md\\:gap-4');
        if (!rightGroup) {
            rightGroup = nav.querySelector('.flex.items-center.justify-between');
        }
        if (rightGroup) {
            var existing = rightGroup.querySelector('#kmd-auth-user-menu');
            if (existing) existing.remove();
            rightGroup.appendChild(el);
        }
    }

    /* ---------- Workspace Switcher ---------- */
    function _showWorkspaceSwitcher() {
        _injectStyles();
        if (_wsOverlayEl) { _wsOverlayEl.remove(); _wsOverlayEl = null; }

        var workspaces = authManager.getWorkspaces();
        var current = authManager.getCurrentWorkspace();

        var overlay = document.createElement('div');
        overlay.className = 'kmd-ws-overlay';

        function renderList() {
            var listHtml = '';
            workspaces.forEach(function (ws, idx) {
                var isActive = current && String(ws.id) === String(current.id);
                var initial = esc((ws.name || '?')[0].toUpperCase());
                listHtml += '<button class="kmd-ws-item ' + (isActive ? 'active' : '') + '" data-ws-id="' + escAttr(ws.id) + '">'
                    + '<div class="kmd-ws-item-icon" style="background:' + _wsColor(idx) + '">' + initial + '</div>'
                    + '<div class="kmd-ws-item-info">'
                    + '<div class="kmd-ws-item-name">' + esc(ws.name || '') + '</div>'
                    + '<div class="kmd-ws-item-role">' + esc(ws.role || '\u0443\u0447\u0430\u0441\u0442\u043D\u0438\u043A') + '</div>'
                    + '</div>'
                    + '<span class="kmd-ws-item-check">' + ICONS.check + '</span>'
                    + '</button>';
            });

            var emptyMsg = '<div style="text-align:center;padding:1.5rem;color:' + T.carbon400 + ';font-size:0.8125rem">'
                + '\u041D\u0435\u0442 \u0434\u043E\u0441\u0442\u0443\u043F\u043D\u044B\u0445 \u043E\u0440\u0433\u0430\u043D\u0438\u0437\u0430\u0446\u0438\u0439</div>';

            var html = '<div class="kmd-ws-modal">'
                + '<div class="kmd-ws-header">'
                + '<div class="kmd-ws-title">\u041E\u0440\u0433\u0430\u043D\u0438\u0437\u0430\u0446\u0438\u0438</div>'
                + '<button class="kmd-ws-close" data-action="close">' + ICONS.x + '</button>'
                + '</div>'
                + '<div class="kmd-ws-list">' + (listHtml || emptyMsg) + '</div>'
                + '<button class="kmd-ws-create" data-action="create">'
                + ICONS.plus + ' \u0421\u043E\u0437\u0434\u0430\u0442\u044C \u043E\u0440\u0433\u0430\u043D\u0438\u0437\u0430\u0446\u0438\u044E</button>'
                + '</div>';

            _setTrustedHTML(overlay, html);

            // Close handlers
            var closeBtn = overlay.querySelector('[data-action="close"]');
            if (closeBtn) closeBtn.addEventListener('click', closeWs);
            overlay.addEventListener('click', function (e) {
                if (e.target === overlay) closeWs();
            });

            // Switch workspace
            overlay.querySelectorAll('[data-ws-id]').forEach(function (btn) {
                btn.addEventListener('click', async function () {
                    var wsId = btn.dataset.wsId;
                    if (current && String(wsId) === String(current.id)) return closeWs();
                    try {
                        await authManager.switchWorkspace(wsId);
                        closeWs();
                        _renderUserMenu();
                    } catch (err) {
                        console.error('[KMD Auth] workspace switch error:', err);
                    }
                });
            });

            // Create workspace placeholder
            var createBtn = overlay.querySelector('[data-action="create"]');
            if (createBtn) createBtn.addEventListener('click', function () {
                closeWs();
            });
        }

        function closeWs() {
            overlay.classList.remove('open');
            setTimeout(function () { overlay.remove(); _wsOverlayEl = null; }, 250);
        }

        renderList();
        _wsOverlayEl = overlay;
        document.body.appendChild(overlay);
        requestAnimationFrame(function () { overlay.classList.add('open'); });
    }

    /* ================================================================
     *  PUBLIC API
     * ================================================================ */

    /**
     * Initialize auth system.
     * - Checks for OAuth callback tokens in URL
     * - Validates existing token
     * - Shows login page or app accordingly
     * - Installs fetch interceptor
     */
    async function initAuth() {
        _injectStyles();

        // Install fetch interceptor first
        authManager.installFetchInterceptor();
        authManager._scheduleRefresh();

        // Handle OAuth callback
        if (authManager.handleOAuthCallback()) {
            try {
                await authManager.fetchUser();
                hideLoginPage();
                _renderUserMenu();
                return;
            } catch (_) {
                authManager._clearAll();
            }
        }

        // Check existing token
        if (authManager.isAuthenticated) {
            try {
                await authManager.fetchUser();
                hideLoginPage();
                _renderUserMenu();
                return;
            } catch (_) {
                authManager._clearAll();
            }
        }

        // No valid auth — show login
        showLoginPage();
    }

    /**
     * Show the login overlay (hides main app).
     */
    function showLoginPage() {
        _injectStyles();
        var page = _buildLoginPage();
        document.body.appendChild(page);
        // Hide main app content
        document.querySelectorAll('body > *:not(.kmd-auth-overlay):not(#kmd-auth-styles):not(style):not(script):not(link)').forEach(function (el) {
            if (!el._kmdAuthHidden) {
                el._kmdAuthPrevDisplay = el.style.display;
                el.style.display = 'none';
                el._kmdAuthHidden = true;
            }
        });
    }

    /**
     * Hide the login overlay (reveals main app).
     */
    function hideLoginPage() {
        if (_overlayEl) { _overlayEl.remove(); _overlayEl = null; }
        // Restore main app content
        document.querySelectorAll('body > *').forEach(function (el) {
            if (el._kmdAuthHidden) {
                el.style.display = el._kmdAuthPrevDisplay || '';
                delete el._kmdAuthHidden;
                delete el._kmdAuthPrevDisplay;
            }
        });
    }

    /**
     * Get current authenticated user info.
     * @returns {Object|null} user object or null
     */
    function getCurrentUser() {
        return authManager.getUser();
    }

    /**
     * Get authorization headers for fetch requests.
     * @returns {Object} e.g. { Authorization: 'Bearer ...' }
     */
    function getAuthHeaders() {
        return authManager.getHeaders();
    }

    /* ================================================================
     *  EXPORT
     * ================================================================ */
    root.KmdAuth = {
        initAuth: initAuth,
        showLoginPage: showLoginPage,
        hideLoginPage: hideLoginPage,
        getCurrentUser: getCurrentUser,
        getAuthHeaders: getAuthHeaders,
        // Advanced — for integration
        authManager: authManager,
    };

})(window);
