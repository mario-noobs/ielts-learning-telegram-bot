/**
 * Returns true when running inside an in-app browser (Instagram, Facebook,
 * TikTok, Line, WeChat, etc.) where Google OAuth popups are blocked.
 */
export function isInAppBrowser(): boolean {
  if (typeof navigator === 'undefined') return false
  const ua = navigator.userAgent
  if (/FBAN|FBAV|Instagram|Line\/|Twitter|MicroMessenger|BytedanceWebview|musical_ly|LinkedInApp|Snapchat|Pinterest/.test(ua)) {
    return true
  }
  // iOS WebView: has AppleWebKit but no Safari token
  if (/(iPhone|iPod|iPad)/.test(ua) && !/Safari\//.test(ua)) return true
  // Android WebView: contains "wv" marker
  if (/Android/.test(ua) && /; wv\)/.test(ua)) return true
  return false
}

export function shouldUseRedirectAuth(): boolean {
  // Firebase redirect auth depends on browser sessionStorage to restore the
  // OAuth state. Several mobile in-app browsers partition or clear that
  // storage, which leaves users on a firebaseapp.com "missing initial state"
  // error page. Prefer popup and surface the existing in-app-browser warning
  // when the environment blocks it.
  return false
}
