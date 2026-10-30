import { useCallback, useEffect, useMemo, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import { ClienteHttp } from '../api/http'
import { ErroApi } from '../api/erros'
import { ApiSera } from '../api/sera'
import type { Ambiente } from '../env'
import { SessaoContext } from './contexto'
import { criarSupabase, traduzirErroAuth } from './supabase'

interface Props {
  ambiente: Ambiente
  children: React.ReactNode
}

export function SessaoProvider({ ambiente, children }: Props) {
  const [supabase] = useState(() => criarSupabase(ambiente))
  const [sessao, setSessao] = useState<Session | null>(null)
  const [carregando, setCarregando] = useState(true)

  useEffect(() => {
    let ativo = true
    supabase.auth.getSession().then(({ data }) => {
      if (!ativo) return
      setSessao(data.session)
      setCarregando(false)
    })
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_evento, novaSessao) => {
      if (!ativo) return
      setSessao(novaSessao)
      setCarregando(false)
    })
    return () => {
      ativo = false
      subscription.unsubscribe()
    }
  }, [supabase])

  const obterToken = useCallback(async () => {
    const { data, error } = await supabase.auth.getSession()
    if (error || !data.session) {
      throw new ErroApi(401, 'sessao_expirada', 'Sua sessão expirou.')
    }
    return data.session.access_token
  }, [supabase])

  const renovarToken = useCallback(async () => {
    const { data, error } = await supabase.auth.refreshSession()
    if (error || !data.session) return null
    return data.session.access_token
  }, [supabase])

  const api = useMemo(() => {
    const http = new ClienteHttp({
      baseUrl: ambiente.apiUrl,
      obterToken,
      renovarToken,
    })
    return new ApiSera(http)
  }, [ambiente.apiUrl, obterToken, renovarToken])

  const entrarComEmail = useCallback(
    async (email: string) => {
      const { error } = await supabase.auth.signInWithOtp({
        email: email.trim(),
        options: {
          emailRedirectTo: `${window.location.origin}/`,
        },
      })
      if (error) throw traduzirErroAuth(error.message)
    },
    [supabase],
  )

  const verificarCodigo = useCallback(
    async (email: string, codigo: string) => {
      const { error } = await supabase.auth.verifyOtp({
        email: email.trim(),
        token: codigo.trim(),
        type: 'email',
      })
      if (error) throw traduzirErroAuth(error.message)
    },
    [supabase],
  )

  const sair = useCallback(async () => {
    await supabase.auth.signOut()
    setSessao(null)
  }, [supabase])

  const valor = useMemo(
    () => ({
      sessao,
      carregando,
      api,
      entrarComEmail,
      verificarCodigo,
      sair,
    }),
    [sessao, carregando, api, entrarComEmail, verificarCodigo, sair],
  )

  return <SessaoContext.Provider value={valor}>{children}</SessaoContext.Provider>
}
