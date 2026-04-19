import { describe, expect, it } from 'vitest'
import i18n from 'i18next'
import ICU from 'i18next-icu'
import { initReactI18next } from 'react-i18next'

import enCommon from '../../public/locales/en/common.json'
import viCommon from '../../public/locales/vi/common.json'
import enDashboard from '../../public/locales/en/dashboard.json'
import viDashboard from '../../public/locales/vi/dashboard.json'

// A standalone i18next instance that pre-loads the real bundles from
// /public/locales so the assertions check the production strings, not
// a hand-typed fixture.
const instance = i18n.createInstance()
await instance.use(ICU).use(initReactI18next).init({
  lng: 'en',
  fallbackLng: 'en',
  ns: ['common', 'dashboard'],
  defaultNS: 'common',
  resources: {
    en: { common: enCommon, dashboard: enDashboard },
    vi: { common: viCommon, dashboard: viDashboard },
  },
  interpolation: { escapeValue: false },
})

describe('i18n AC1 — ICU pluralization', () => {
  it('pluralizes EN days', async () => {
    await instance.changeLanguage('en')
    expect(instance.t('time.daysUntilExam', { count: 1 })).toBe('1 day until your exam')
    expect(instance.t('time.daysUntilExam', { count: 12 })).toBe('12 days until your exam')
  })

  it('interpolates VN days', async () => {
    await instance.changeLanguage('vi')
    expect(instance.t('time.daysUntilExam', { count: 7 })).toBe('Còn 7 ngày đến kỳ thi')
  })

  it('pluralizes EN streak from the dashboard namespace', async () => {
    await instance.changeLanguage('en')
    expect(
      instance.t('profilePanel.streakDays', { count: 1, ns: 'dashboard' }),
    ).toBe('1 day')
    expect(
      instance.t('profilePanel.streakDays', { count: 5, ns: 'dashboard' }),
    ).toBe('5 days')
  })
})

describe('i18n AC3 — EN default; missing VN key falls back to EN', () => {
  it('falls back to EN when VN bundle lacks a key', async () => {
    // Temporarily register an EN-only key to simulate a translation gap.
    instance.addResourceBundle('en', 'dashboard', { __only_en__: 'only-en' }, true, true)
    await instance.changeLanguage('vi')
    expect(instance.t('__only_en__', { ns: 'dashboard' })).toBe('only-en')
  })

  it('returns the key itself when no bundle carries it', async () => {
    await instance.changeLanguage('en')
    // i18next's default fallback when a key is missing is to return the key.
    expect(instance.t('definitely.not.a.real.key')).toBe('definitely.not.a.real.key')
  })
})
