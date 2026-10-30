import type {
  Conversa,
  EntradaChat,
  EntradaPessoa,
  EventoChat,
  Mensagem,
  Pessoa,
} from '../dominios/tipos'
import { transmitirChat } from './chat'
import type { ClienteHttp } from './http'

export class ApiSera {
  constructor(private readonly http: ClienteHttp) {}

  listarPessoas(): Promise<Pessoa[]> {
    return this.http.json<Pessoa[]>('/pessoas')
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
