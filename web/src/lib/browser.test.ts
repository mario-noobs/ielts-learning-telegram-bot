import { afterEach, describe, expect, it, vi } from 'vitest'
import { isInAppBrowser, shouldUseRedirectAuth } from './browser'

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

  it('keeps popup auth for desktop browsers', () => {
    stubUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15')

    expect(isInAppBrowser()).toBe(false)
    expect(shouldUseRedirectAuth()).toBe(false)
  })
})
