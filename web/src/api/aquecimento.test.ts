import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ApiSera } from './sera'

type AquecerApi = typeof import('./aquecimento').aquecerApi

let aquecerApi: AquecerApi
let online = true

function apiFalsa() {
  return {
    aquecer: vi.fn().mockResolvedValue(undefined),
  } as unknown as ApiSera & { aquecer: ReturnType<typeof vi.fn> }
}

beforeEach(async () => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-10-31T12:00:00Z'))
  vi.resetModules()
  online = true
  Object.defineProperty(window.navigator, 'onLine', {
    configurable: true,
    get: () => online,
  })
  ;({ aquecerApi } = await import('./aquecimento'))
})

afterEach(() => {
  vi.useRealTimers()
})

describe('aquecerApi', () => {
  it('reaproveita a chamada em andamento', async () => {
    const api = apiFalsa()
    const primeira = aquecerApi(api)
    const segunda = aquecerApi(api)

    expect(api.aquecer).toHaveBeenCalledTimes(1)
    await Promise.all([primeira, segunda])
  })

  it('não repete antes de cinco minutos', async () => {
    const api = apiFalsa()
    await aquecerApi(api)
    await aquecerApi(api)
    expect(api.aquecer).toHaveBeenCalledTimes(1)

    vi.advanceTimersByTime(5 * 60 * 1000 + 1)
    await aquecerApi(api)
    expect(api.aquecer).toHaveBeenCalledTimes(2)
  })

  it('não tenta aquecer sem conexão', async () => {
    online = false
    const api = apiFalsa()
    await aquecerApi(api)
    expect(api.aquecer).not.toHaveBeenCalled()
  })
})
