import { afterEach, describe, expect, it, vi } from 'vitest'
import { externalBrowserUrl, isInAppBrowser, shouldUseRedirectAuth } from './browser'

function stubUserAgent(userAgent: string) {
  vi.stubGlobal('navigator', { userAgent })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('browser auth helpers', () => {
  it('keeps popup auth for normal mobile browsers', () => {
    stubUserAgent('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile/15E148 Safari/604.1')

    expect(isInAppBrowser()).toBe(false)
    expect(shouldUseRedirectAuth()).toBe(false)
  })

  it('avoids redirect auth for in-app browsers', () => {
    stubUserAgent('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Instagram 300.0')

    expect(isInAppBrowser()).toBe(true)
    expect(shouldUseRedirectAuth()).toBe(false)
  })

  it('detects Zalo and Messenger browsers', () => {
    stubUserAgent('Mozilla/5.0 (Linux; Android 14) Zalo/24.05')
    expect(isInAppBrowser()).toBe(true)

    stubUserAgent('Mozilla/5.0 (Linux; Android 14) FB_IAB/MESSENGER')
    expect(isInAppBrowser()).toBe(true)
  })

  it('keeps popup auth for desktop browsers', () => {
    stubUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15')

    expect(isInAppBrowser()).toBe(false)
    expect(shouldUseRedirectAuth()).toBe(false)
  })

  it('builds a Chrome intent URL on Android', () => {
    stubUserAgent('Mozilla/5.0 (Linux; Android 14) Chrome/125.0')

    expect(externalBrowserUrl('https://ielts.example.com/login?next=%2Fdaily')).toBe(
      'intent://ielts.example.com/login?next=%2Fdaily#Intent;scheme=https;package=com.android.chrome;S.browser_fallback_url=https%3A%2F%2Fielts.example.com%2Flogin%3Fnext%3D%252Fdaily;end',
    )
  })

  it('does not build Chrome intents outside Android', () => {
    stubUserAgent('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/604.1')

    expect(externalBrowserUrl('https://ielts.example.com/login')).toBeNull()
  })
})
