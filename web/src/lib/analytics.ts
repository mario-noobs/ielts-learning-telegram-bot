export function track(event: string, props: Record<string, unknown> = {}) {
  if (import.meta.env.DEV) console.debug('[analytics]', event, props)
}
