import { useCallback, useEffect, useMemo, useState } from 'react'
import { ErroApi, ehSessaoExpirada } from '../api/erros'
import { useSessao } from '../auth/contexto'
import type { EntradaPessoa, Pessoa } from '../dominios/tipos'
import { PessoaContext } from './contexto'

const CHAVE_CACHE = 'sera.pessoa.v1'

interface CachePessoa {
  usuarioId: string
  pessoa: Pessoa
}

function lerPessoaDoCache(usuarioId: string): Pessoa | null {
  try {
    const bruto = window.localStorage.getItem(CHAVE_CACHE)
    if (!bruto) return null
    const dados = JSON.parse(bruto) as Partial<CachePessoa>
    if (dados.usuarioId !== usuarioId) return null
    const pessoa = dados.pessoa
    if (!pessoa || typeof pessoa.id !== 'string') return null
    return pessoa
  } catch {
    return null
  }
}

function guardarPessoaNoCache(usuarioId: string, pessoa: Pessoa) {
  try {
    window.localStorage.setItem(
      CHAVE_CACHE,
      JSON.stringify({ usuarioId, pessoa } satisfies CachePessoa),
    )
  } catch {
    // Sem localStorage (modo privado restrito): segue sem cache.
  }
}

function limparPessoaDoCache() {
  try {
    window.localStorage.removeItem(CHAVE_CACHE)
  } catch {
    // idem
  }
}

export function PessoaProvider({ children }: { children: React.ReactNode }) {
  const { sessao, carregando: carregandoSessao, api, sair } = useSessao()
  const idDaSessao = sessao?.user.id ?? null
  const [pessoa, setPessoa] = useState<Pessoa | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)

  const recarregar = useCallback(async () => {
    // Enquanto o Supabase lê a sessão salva, "sem sessão" ainda não é uma
    // resposta: concluir agora levaria a rota para /onboarding por engano.
    if (carregandoSessao) return
    if (!idDaSessao) {
      limparPessoaDoCache()
      setPessoa(null)
      setCarregando(false)
      return
    }
    // Perfil mínimo para o shell abrir offline; conversas nunca são cacheadas.
    const cache = lerPessoaDoCache(idDaSessao)
    setPessoa(cache)
    setCarregando(true)
    setErro(null)
    try {
      const pessoas = await api.listarPessoas()
      const atual = pessoas[0] ?? null
      setPessoa(atual)
      if (atual) {
        guardarPessoaNoCache(idDaSessao, atual)
      } else {
        limparPessoaDoCache()
      }
    } catch (falha) {
      if (ehSessaoExpirada(falha)) {
        limparPessoaDoCache()
        await sair()
        return
      }
      setErro(
        falha instanceof Error
          ? falha.message
          : 'Não foi possível carregar seu perfil.',
      )
    } finally {
      setCarregando(false)
    }
  }, [api, carregandoSessao, idDaSessao, sair])

  useEffect(() => {
    void recarregar()
  }, [recarregar])

  const criarPessoa = useCallback(
    async (entrada: EntradaPessoa) => {
      try {
        const criada = await api.criarPessoa(entrada)
        setPessoa(criada)
        if (idDaSessao) guardarPessoaNoCache(idDaSessao, criada)
        return criada
      } catch (falha) {
        if (falha instanceof ErroApi && falha.status === 409) {
          const pessoas = await api.listarPessoas()
          const existente = pessoas[0]
          if (existente) {
            setPessoa(existente)
            if (idDaSessao) guardarPessoaNoCache(idDaSessao, existente)
            return existente
          }
        }
        if (ehSessaoExpirada(falha)) {
          limparPessoaDoCache()
          await sair()
        }
        throw falha
      }
    },
    [api, idDaSessao, sair],
  )

  const valor = useMemo(
    () => ({ pessoa, carregando, erro, recarregar, criarPessoa }),
    [pessoa, carregando, erro, recarregar, criarPessoa],
  )

  return <PessoaContext.Provider value={valor}>{children}</PessoaContext.Provider>
}
