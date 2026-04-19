import i18n from 'i18next'

/**
 * Server error-code contract (US-M7.3).
 *
 * Every API error response shape:
 *   { error: { code: "reading.passage.not_found", params: {...}, http_status: 404 } }
 */
export interface ApiErrorBody {
  code: string
  params: Record<string, unknown>
  http_status: number
}

export class ApiError extends Error {
  readonly code: string
  readonly params: Record<string, unknown>
  readonly httpStatus: number

  constructor(body: ApiErrorBody) {
    super(body.code)
    this.name = 'ApiError'
    this.code = body.code
    this.params = body.params ?? {}
    this.httpStatus = body.http_status
  }

  /** Resolve the code against the `errors` bundle in the active locale.
   *  Unknown codes fall back to `errors:common.unknown_error` and log a
   *  warning so missing keys surface in dev (AC3).
   */
  localize(): string {
    const key = this.code
    if (!i18n.exists(key, { ns: 'errors' })) {
      if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        console.warn(`[apiError] missing errors.${key}; falling back to common.unknown_error`)
      }
      return i18n.t('common.unknown_error', { ns: 'errors' })
    }
    return i18n.t(key, { ns: 'errors', ...this.params })
  }
}

/**
 * Accepts either the new `{error: {code,...}}` shape or the legacy
 * `{error: {code, message}}` / plain-text / no-body cases, and returns
 * an ApiError. Preserves the original message in `params.message` when
 * the legacy shape is encountered so log inspection still works.
 */
export function parseApiError(raw: unknown, httpStatus: number): ApiError {
  if (raw && typeof raw === 'object' && 'error' in raw) {
    const err = (raw as { error: unknown }).error
    if (err && typeof err === 'object') {
      const e = err as Partial<ApiErrorBody> & { message?: string }
      if (typeof e.code === 'string') {
        return new ApiError({
          code: e.code,
          params: (e.params as Record<string, unknown>) ?? (e.message ? { message: e.message } : {}),
          http_status: e.http_status ?? httpStatus,
        })
      }
    }
  }
  return new ApiError({
    code: 'common.unknown_error',
    params: {},
    http_status: httpStatus,
  })
}
