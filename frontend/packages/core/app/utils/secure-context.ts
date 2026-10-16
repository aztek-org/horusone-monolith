/**
 * Browser secure-context detection (#73).
 *
 * Browsers only expose `crypto.subtle` (PKCE S256 challenge, used for sign-in)
 * and `navigator.mediaDevices.getUserMedia` (microphone capture, used for voice)
 * in a *secure context*: HTTPS, or `localhost`. Serving Horus over plain HTTP on
 * a LAN address silently disables both, which surfaces as a cryptic
 * `crypto.subtle is undefined` or a misleading "microphone denied" error.
 *
 * Callers use this to fail with an actionable message instead. Environments
 * that do not expose `isSecureContext` (SSR, unit tests) are treated as secure,
 * so this only ever reports a genuinely insecure page.
 */
export function isInsecureContext(): boolean {
  if (typeof window === 'undefined') return false
  return window.isSecureContext === false
}
