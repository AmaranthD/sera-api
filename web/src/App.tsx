import { BrowserRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { SessaoProvider } from './auth/SessaoProvider'
import { useSessao } from './auth/contexto'
import { ChatProvider } from './chat/ChatProvider'
import { AtualizacaoPwa } from './componentes/AtualizacaoPwa'
import { Banner } from './componentes/Banner'
import { Botao } from './componentes/Botao'
import { CarregandoTela } from './componentes/Carregando'
import { Marca } from './componentes/Marca'
import type { Ambiente } from './env'
import { PessoaProvider } from './pessoa/PessoaProvider'
import { usePessoa } from './pessoa/contexto'
import { ChatTela } from './telas/chat/ChatTela'
import { Conta } from './telas/conta/Conta'
import { Login } from './telas/login/Login'
import { Onboarding } from './telas/onboarding/Onboarding'
import estilos from './App.module.css'

function Protegido() {
  const { sessao, carregando, sair } = useSessao()
  const { pessoa, carregando: carregandoPessoa, erro, recarregar } = usePessoa()

  if (carregando || carregandoPessoa) {
    return <CarregandoTela />
  }
  if (!sessao) return <Navigate to="/login" replace />
  if (erro && !pessoa) {
    return (
      <div className={estilos.falha}>
        <div className={estilos.falhaCartao}>
          <Marca legenda="conexão" />
          <h1 className={estilos.falhaTitulo}>Não consegui abrir seu perfil.</h1>
          <Banner tipo="erro">{erro}</Banner>
          <div className={estilos.falhaAcoes}>
            <Botao onClick={() => void recarregar()}>Tentar de novo</Botao>
            <Botao variante="fantasma" onClick={() => void sair()}>
              Sair
            </Botao>
          </div>
        </div>
      </div>
    )
  }
  if (!pessoa) return <Navigate to="/onboarding" replace />
  return <Outlet />
}

export function App({ ambiente }: { ambiente: Ambiente }) {
  return (
    <BrowserRouter>
      <SessaoProvider ambiente={ambiente}>
        <PessoaProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/onboarding" element={<Onboarding />} />
            <Route element={<Protegido />}>
              <Route path="/conta" element={<Conta />} />
              <Route
                element={
                  <ChatProvider>
                    <Outlet />
                  </ChatProvider>
                }
              >
                <Route path="/" element={<ChatTela />} />
                <Route path="/c/:conversaId" element={<ChatTela />} />
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <AtualizacaoPwa />
        </PessoaProvider>
      </SessaoProvider>
    </BrowserRouter>
  )
}
