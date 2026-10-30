import { ErroApi, erroDaResposta, erroDeRede } from './erros'

export type Metodo = 'GET' | 'POST' | 'DELETE' | 'PATCH'

export interface OpcoesHttp {
  metodo?: Metodo
  corpo?: unknown
  sinal?: AbortSignal
  tempoLimiteMs?: number
}

export interface ConfiguracaoHttp {
  baseUrl: string
  obterToken: () => Promise<string>
  renovarToken?: () => Promise<string | null>
  tempoLimiteMs?: number
}

async function corpoJson(resposta: Response): Promise<unknown> {
  if (resposta.status === 204) return null
  const texto = await resposta.text()
  if (!texto) return null
  try {
    return JSON.parse(texto)
  } catch {
    return texto
  }
}

export class ClienteHttp {
  private readonly baseUrl: string
  private readonly tempoLimiteMs: number

  constructor(private readonly config: ConfiguracaoHttp) {
    this.baseUrl = config.baseUrl.replace(/\/+$/, '')
    this.tempoLimiteMs = config.tempoLimiteMs ?? 120_000
  }

  private async executar(
    caminho: string,
    opcoes: OpcoesHttp,
    token: string,
  ): Promise<Response> {
    const controlador = new AbortController()
    const tempoLimite = opcoes.tempoLimiteMs ?? this.tempoLimiteMs
    const temporizador = setTimeout(() => {
      controlador.abort(
        new DOMException('A Sera demorou para responder.', 'TimeoutError'),
      )
    }, tempoLimite)

    const sinalOriginal = opcoes.sinal
    const repassarAborto = () => controlador.abort(sinalOriginal?.reason)
    if (sinalOriginal?.aborted) {
      repassarAborto()
    } else {
      sinalOriginal?.addEventListener('abort', repassarAborto, { once: true })
    }

    const cabecalhos: Record<string, string> = {
      Accept: 'application/json, text/event-stream',
      Authorization: `Bearer ${token}`,
    }
    if (opcoes.corpo !== undefined) {
      cabecalhos['Content-Type'] = 'application/json'
    }

    try {
      return await fetch(`${this.baseUrl}${caminho}`, {
        method: opcoes.metodo ?? 'GET',
        headers: cabecalhos,
        body: opcoes.corpo === undefined ? undefined : JSON.stringify(opcoes.corpo),
        signal: controlador.signal,
        credentials: 'omit',
      })
    } catch (erro) {
      if (erro instanceof DOMException && erro.name === 'AbortError') {
        throw erro
      }
      throw erroDeRede(erro)
    } finally {
      clearTimeout(temporizador)
    }
  }

  private async comToken(caminho: string, opcoes: OpcoesHttp): Promise<Response> {
    let token = await this.config.obterToken()
    let resposta = await this.executar(caminho, opcoes, token)
    if (resposta.status === 401 && this.config.renovarToken) {
      const renovado = await this.config.renovarToken()
      if (renovado) {
        token = renovado
        resposta = await this.executar(caminho, opcoes, token)
      }
    }
    return resposta
  }

  async abrir(caminho: string, opcoes: OpcoesHttp = {}): Promise<Response> {
    const resposta = await this.comToken(caminho, opcoes)
    if (!resposta.ok) {
      const corpo = await corpoJson(resposta)
      throw erroDaResposta(resposta.status, corpo)
    }
    return resposta
  }

  async json<T>(caminho: string, opcoes: OpcoesHttp = {}): Promise<T> {
    const resposta = await this.abrir(caminho, opcoes)
    const corpo = await corpoJson(resposta)
    return corpo as T
  }
}

export { ErroApi }
