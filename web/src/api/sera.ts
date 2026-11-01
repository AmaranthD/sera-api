import type {
  Ajuste,
  AtualizacaoAjuste,
  AtualizacaoMemoria,
  Conversa,
  DadosExportados,
  EntradaChat,
  EntradaPessoa,
  EventoChat,
  Memoria,
  Mensagem,
  Pessoa,
} from '../dominios/tipos'
import { transmitirChat } from './chat'
import type { ClienteHttp } from './http'

export class ApiSera {
  constructor(
    private readonly http: ClienteHttp,
    private readonly baseUrl: string,
  ) {}

  /**
   * Acorda o Render sem autenticação e sem bloquear a UI. O /health não
   * consulta banco nem LLM; serve só para tirar o serviço do sono.
   */
  aquecer(): Promise<void> {
    return fetch(`${this.baseUrl}/health`, {
      cache: 'no-store',
      credentials: 'omit',
      signal: AbortSignal.timeout(90_000),
    })
      .then(() => undefined)
      .catch(() => undefined)
  }

  listarPessoas(): Promise<Pessoa[]> {
    return this.http.json<Pessoa[]>('/pessoas')
  }

  obterPessoa(pessoaId: string): Promise<Pessoa> {
    return this.http.json<Pessoa>(`/pessoas/${encodeURIComponent(pessoaId)}`)
  }

  criarPessoa(entrada: EntradaPessoa): Promise<Pessoa> {
    return this.http.json<Pessoa>('/pessoas', {
      metodo: 'POST',
      corpo: entrada,
    })
  }

  listarConversas(pessoaId: string): Promise<Conversa[]> {
    return this.http.json<Conversa[]>(
      `/pessoas/${encodeURIComponent(pessoaId)}/conversas`,
    )
  }

  listarMemorias(pessoaId: string): Promise<Memoria[]> {
    return this.http.json<Memoria[]>(
      `/pessoas/${encodeURIComponent(pessoaId)}/memorias`,
    )
  }

  atualizarMemoria(
    pessoaId: string,
    memoriaId: string,
    dados: AtualizacaoMemoria,
  ): Promise<Memoria> {
    return this.http.json<Memoria>(
      `/pessoas/${encodeURIComponent(pessoaId)}/memorias/${encodeURIComponent(memoriaId)}`,
      { metodo: 'PATCH', corpo: dados },
    )
  }

  apagarMemoria(pessoaId: string, memoriaId: string): Promise<null> {
    return this.http.json<null>(
      `/pessoas/${encodeURIComponent(pessoaId)}/memorias/${encodeURIComponent(memoriaId)}`,
      { metodo: 'DELETE' },
    )
  }

  listarAjustes(pessoaId: string): Promise<Ajuste[]> {
    return this.http.json<Ajuste[]>(`/pessoas/${encodeURIComponent(pessoaId)}/ajustes`)
  }

  atualizarAjuste(
    pessoaId: string,
    ajusteId: string,
    dados: AtualizacaoAjuste,
  ): Promise<Ajuste> {
    return this.http.json<Ajuste>(
      `/pessoas/${encodeURIComponent(pessoaId)}/ajustes/${encodeURIComponent(ajusteId)}`,
      { metodo: 'PATCH', corpo: dados },
    )
  }

  apagarAjuste(pessoaId: string, ajusteId: string): Promise<null> {
    return this.http.json<null>(
      `/pessoas/${encodeURIComponent(pessoaId)}/ajustes/${encodeURIComponent(ajusteId)}`,
      { metodo: 'DELETE' },
    )
  }

  exportarDados(pessoaId: string): Promise<DadosExportados> {
    return this.http.json<DadosExportados>(
      `/pessoas/${encodeURIComponent(pessoaId)}/dados`,
    )
  }

  listarMensagens(conversaId: string): Promise<Mensagem[]> {
    return this.http.json<Mensagem[]>(
      `/conversas/${encodeURIComponent(conversaId)}/mensagens`,
    )
  }

  saude(): Promise<{ status: string }> {
    return this.http.json<{ status: string }>('/health')
  }

  transmitirChat(
    entrada: EntradaChat,
    aoEvento: (evento: EventoChat) => void,
    sinal?: AbortSignal,
  ): Promise<void> {
    return transmitirChat(this.http, entrada, aoEvento, sinal)
  }
}
