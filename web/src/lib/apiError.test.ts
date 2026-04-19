import { describe, expect, it } from 'vitest'
import i18n from 'i18next'
import ICU from 'i18next-icu'
import { initReactI18next } from 'react-i18next'

import { ApiError, parseApiError } from './apiError'
import enErrors from '../../public/locales/en/errors.json'
import viErrors from '../../public/locales/vi/errors.json'

await i18n.use(ICU).use(initReactI18next).init({
  lng: 'en',
  fallbackLng: 'en',
  ns: ['errors'],
  defaultNS: 'errors',
  resources: {
    en: { errors: enErrors },
    vi: { errors: viErrors },
  },
  interpolation: { escapeValue: false },
})

describe('parseApiError (US-M7.3)', () => {
  it('parses the new {error: {code, params, http_status}} shape', () => {
    const err = parseApiError(
      { error: { code: 'reading.passage.not_found', params: { passage_id: 'p001' }, http_status: 404 } },
      404,
    )
    expect(err).toBeInstanceOf(ApiError)
    expect(err.code).toBe('reading.passage.not_found')
    expect(err.params.passage_id).toBe('p001')
    expect(err.httpStatus).toBe(404)
  })

  it('handles the legacy {error: {code, message}} shape', () => {
    const err = parseApiError(
      { error: { code: 'common.validation', message: 'Add more words' } },
      400,
    )
    expect(err.code).toBe('common.validation')
    expect(err.params.message).toBe('Add more words')
  })

  it('falls back to common.unknown_error when no code', () => {
    const err = parseApiError(null, 500)
    expect(err.code).toBe('common.unknown_error')
  })
})

describe('ApiError.localize (AC3)', () => {
  it('resolves a registered code with params interpolation', async () => {
    await i18n.changeLanguage('en')
    const err = new ApiError({
      code: 'reading.passage.not_found',
      params: { passage_id: 'p001' },
      http_status: 404,
    })
    expect(err.localize()).toBe('Passage "p001" is not available.')
  })

  it('interpolates in Vietnamese', async () => {
    await i18n.changeLanguage('vi')
    const err = new ApiError({
      code: 'writing.text.too_short',
      params: { min_words: 20, got: 7 },
      http_status: 400,
    })
    expect(err.localize()).toBe('Bài viết phải có ít nhất 20 từ (hiện tại 7).')
  })

  it('falls back to common.unknown_error for unknown codes', async () => {
    await i18n.changeLanguage('en')
    const err = new ApiError({
      code: 'definitely.not.registered',
      params: {},
      http_status: 500,
    })
    expect(err.localize()).toBe('Something went wrong. Please try again.')
  })
})
