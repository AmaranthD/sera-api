export class ErroApi extends Error {
  constructor(
    readonly status: number,
    readonly codigo: string,
    mensagem: string,
  ) {
    super(mensagem)
    this.name = 'ErroApi'
  }
}

const MENSAGENS: Record<number, { codigo: string; mensagem: string }> = {
  401: {
    codigo: 'sessao_expirada',
    mensagem: 'Sua sessão expirou. Entre de novo para continuar.',
  },
  403: {
    codigo: 'sem_acesso',
    mensagem: 'Sua conta não tem acesso a esta conversa.',
  },
  404: {
    codigo: 'nao_encontrado',
    mensagem: 'Não encontramos o que você procurava.',
  },
  409: {
    codigo: 'conflito',
    mensagem: 'Isso já foi criado em outro lugar.',
  },
  422: {
    codigo: 'invalido',
    mensagem: 'Confira os dados e tente de novo.',
  },
  429: {
    codigo: 'muitas_mensagens',
    mensagem: 'Muitas mensagens em pouco tempo. Espere um instante.',
  },
  502: {
    codigo: 'llm_falhou',
    mensagem: 'A Sera não conseguiu responder agora. Tente de novo.',
  },
  503: {
    codigo: 'indisponivel',
    mensagem: 'A Sera está indisponível no momento. Tente daqui a pouco.',
  },
}

function detalheDoCorpo(corpo: unknown): string | null {
  if (!corpo || typeof corpo !== 'object') return null
  const detalhe = (corpo as { detail?: unknown }).detail
  if (typeof detalhe === 'string' && detalhe.trim()) return detalhe.trim()
  if (Array.isArray(detalhe)) {
    const partes = detalhe
      .map((item) => {
        if (item && typeof item === 'object') {
          const msg = (item as { msg?: unknown }).msg
          return typeof msg === 'string' ? msg : null
        }
        return null
      })
      .filter((item): item is string => Boolean(item))
    if (partes.length > 0) return partes.join(' ')
  }
  return null
}

export function erroDaResposta(status: number, corpo: unknown): ErroApi {
  const padrao = MENSAGENS[status]
  const detalhe = detalheDoCorpo(corpo)
  if (padrao) {
    const mensagem = status === 422 && detalhe ? detalhe : padrao.mensagem
    return new ErroApi(status, padrao.codigo, mensagem)
  }
  if (status >= 500) {
    return new ErroApi(
      status,
      'servidor',
      'A Sera teve um problema. Tente de novo em instantes.',
    )
  }
  return new ErroApi(status, 'erro', detalhe ?? 'Não foi possível completar o pedido.')
}

export function erroDeRede(erro: unknown): ErroApi {
  if (erro instanceof ErroApi) return erro
  if (erro instanceof DOMException && erro.name === 'TimeoutError') {
    return new ErroApi(
      0,
      'tempo_esgotado',
      'A Sera demorou demais para responder. Tente de novo.',
    )
  }
  return new ErroApi(
    0,
    'rede',
    'Sem conexão com a Sera. Confira sua internet e tente de novo.',
  )
}

export function ehSessaoExpirada(erro: unknown): boolean {
  return erro instanceof ErroApi && erro.status === 401
}
