import type {
  Ajuste,
  AtualizacaoAjuste,
  AtualizacaoCompromisso,
  AtualizacaoMemoria,
  Compromisso,
  Conversa,
  DadosExportados,
  EntradaChat,
  EntradaCompromisso,
  EntradaInscricaoPush,
  EntradaPessoa,
  EventoChat,
  InscricaoPush,
  Memoria,
  Mensagem,
  Pessoa,
  TrabalhoChat,
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

  /** Cria a resposta em segundo plano; o app acompanha por polling. */
  iniciarChat(entrada: EntradaChat): Promise<TrabalhoChat> {
    return this.http.json<TrabalhoChat>('/chat/job', {
      metodo: 'POST',
      corpo: {
        mensagem: entrada.mensagem,
        conversa_id: entrada.conversaId,
        ...(entrada.fonte ? { fonte: entrada.fonte } : {}),
      },
    })
  }

  cancelarChat(respostaId: string): Promise<null> {
    return this.http.json<null>(
      `/chat/job/${encodeURIComponent(respostaId)}/cancelar`,
      { metodo: 'POST' },
    )
  }

  estadoChat(respostaId: string): Promise<Mensagem> {
    return this.http.json<Mensagem>(`/chat/job/${encodeURIComponent(respostaId)}`)
  }

  listarCompromissos(pessoaId: string): Promise<Compromisso[]> {
    return this.http.json<Compromisso[]>(
      `/pessoas/${encodeURIComponent(pessoaId)}/compromissos`,
    )
  }

  criarCompromisso(pessoaId: string, dados: EntradaCompromisso): Promise<Compromisso> {
    return this.http.json<Compromisso>(
      `/pessoas/${encodeURIComponent(pessoaId)}/compromissos`,
      { metodo: 'POST', corpo: dados },
    )
  }

  atualizarCompromisso(
    pessoaId: string,
    compromissoId: string,
    dados: AtualizacaoCompromisso,
  ): Promise<Compromisso> {
    return this.http.json<Compromisso>(
      `/pessoas/${encodeURIComponent(pessoaId)}/compromissos/${encodeURIComponent(compromissoId)}`,
      { metodo: 'PATCH', corpo: dados },
    )
  }

  apagarCompromisso(pessoaId: string, compromissoId: string): Promise<null> {
    return this.http.json<null>(
      `/pessoas/${encodeURIComponent(pessoaId)}/compromissos/${encodeURIComponent(compromissoId)}`,
      { metodo: 'DELETE' },
    )
  }

  chaveNotificacoes(): Promise<{ chave: string }> {
    return this.http.json<{ chave: string }>('/notificacoes/chave')
  }

  listarInscricoes(pessoaId: string): Promise<InscricaoPush[]> {
    return this.http.json<InscricaoPush[]>(
      `/pessoas/${encodeURIComponent(pessoaId)}/notificacoes/inscricoes`,
    )
  }

  inscreverNotificacoes(
    pessoaId: string,
    dados: EntradaInscricaoPush,
  ): Promise<InscricaoPush> {
    return this.http.json<InscricaoPush>(
      `/pessoas/${encodeURIComponent(pessoaId)}/notificacoes/inscricoes`,
      { metodo: 'POST', corpo: dados },
    )
  }

  removerNotificacoes(pessoaId: string, endpoint: string): Promise<null> {
    return this.http.json<null>(
      `/pessoas/${encodeURIComponent(pessoaId)}/notificacoes/inscricoes?endpoint=${encodeURIComponent(endpoint)}`,
      { metodo: 'DELETE' },
    )
  }

  testarNotificacao(
    pessoaId: string,
  ): Promise<{ enviados: number; dispositivos: number }> {
    return this.http.json<{ enviados: number; dispositivos: number }>(
      `/pessoas/${encodeURIComponent(pessoaId)}/notificacoes/teste`,
      { metodo: 'POST' },
    )
  }
}
