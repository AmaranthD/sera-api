import { useEffect, useRef, useState } from 'react'
import { Botao } from '../../componentes/Botao'
import { Icone } from '../../componentes/Icone'
import { mensagemDeErroVoz, ouvir, reconhecimentoSuportado, type Ouvinte } from '../../voz/ouvir'
import {
  consultarPermissaoMicrofone,
  pedirPermissaoMicrofone,
  type EstadoPermissao,
} from '../../voz/permissao'
import estilos from './Conta.module.css'

const ROTULOS: Record<EstadoPermissao, string> = {
  granted: 'Liberado',
  denied: 'Negado',
  prompt: 'Ainda não pedido',
  desconhecido: 'Não verificado',
}

export function SecaoMicrofone() {
  const [estado, setEstado] = useState<EstadoPermissao>('desconhecido')
  const [pedindo, setPedindo] = useState(false)
  const [testando, setTestando] = useState(false)
  const [transcricao, setTranscricao] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const ouvinteRef = useRef<Ouvinte | null>(null)
  const suporta = reconhecimentoSuportado()

  useEffect(() => {
    let ativo = true
    void consultarPermissaoMicrofone().then((valor) => {
      if (ativo) setEstado(valor)
    })
    return () => {
      ativo = false
      ouvinteRef.current?.parar()
    }
  }, [])

  const permitir = async () => {
    setPedindo(true)
    setErro(null)
    const resultado = await pedirPermissaoMicrofone()
    setPedindo(false)
    if (!resultado.ok) {
      setErro(resultado.erro ?? 'Não foi possível liberar o microfone.')
      setEstado('denied')
      return
    }
    setEstado('granted')
  }

  const testar = () => {
    if (testando) {
      ouvinteRef.current?.parar()
      ouvinteRef.current = null
      setTestando(false)
      return
    }
    setErro(null)
    setTranscricao('')
    setTestando(true)
    const ouvinte = ouvir({
      aoTexto: (texto) => setTranscricao(texto),
      aoErro: (falha) => {
        setErro(mensagemDeErroVoz(falha))
        setTestando(false)
      },
      aoFim: () => {
        ouvinteRef.current = null
        setTestando(false)
      },
    })
    if (!ouvinte) {
      setTestando(false)
      setErro('Reconhecimento de voz indisponível neste navegador.')
      return
    }
    ouvinteRef.current = ouvinte
  }

  return (
    <section className={estilos.secao} aria-labelledby="microfone-titulo">
      <h2 className={estilos.secaoTitulo} id="microfone-titulo">
        Microfone e voz
      </h2>
      <p className={estilos.secaoTexto}>
        Libere o microfone neste navegador para ditar mensagens no chat. A Sera
        não grava nem guarda o áudio; o navegador pode enviá-lo ao serviço de
        reconhecimento dele.
      </p>

      <div className={estilos.linha}>
        <span className={estilos.rotulo}>Permissão</span>
        <span className={estilos.estado}>
          <span
            className={
              estado === 'granted'
                ? estilos.pontoOk
                : estado === 'denied'
                  ? estilos.pontoFalha
                  : estilos.pontoEspera
            }
            aria-hidden="true"
          />
          {ROTULOS[estado]}
        </span>
      </div>

      {!suporta ? (
        <p className={estilos.secaoTexto}>
          Este navegador não oferece ditado por voz. No iPhone, use o microfone
          do teclado; no Android, use o Chrome atualizado.
        </p>
      ) : null}

      {erro ? <p className={estilos.secaoTexto}>{erro}</p> : null}
      {transcricao ? (
        <p className={estilos.secaoTexto}>
          <strong>Ouvi:</strong> {transcricao}
        </p>
      ) : null}

      <div className={estilos.acoes}>
        <Botao
          variante={estado === 'granted' ? 'secundario' : 'primario'}
          carregando={pedindo}
          icone={<Icone nome="microfone" tamanho={17} />}
          onClick={() => void permitir()}
        >
          {estado === 'granted' ? 'Revalidar microfone' : 'Permitir microfone'}
        </Botao>

        {suporta ? (
          <Botao
            variante="fantasma"
            icone={
              <Icone nome={testando ? 'parar' : 'ouvir'} tamanho={17} />
            }
            onClick={testar}
          >
            {testando ? 'Parar teste' : 'Testar ditado'}
          </Botao>
        ) : null}
      </div>
    </section>
  )
}
