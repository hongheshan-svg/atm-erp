import DOMPurify from 'dompurify'

/**
 * Sanitize an untrusted HTML string before binding it with `v-html`.
 *
 * Any user-provided rich/plain content that is later rendered as HTML
 * (announcements, knowledge-base articles, templates, ...) must be passed
 * through this helper to prevent stored / reflected XSS.
 *
 * Uses the DOMPurify "html" profile: standard formatting tags are kept while
 * <script>, inline event handlers (onclick=...), <iframe>, etc. are removed.
 */
export function sanitizeHtml(html: string | null | undefined): string {
  if (html === null || html === undefined || html === '') {
    return ''
  }
  return DOMPurify.sanitize(String(html), {
    USE_PROFILES: { html: true },
  })
}

export default sanitizeHtml
