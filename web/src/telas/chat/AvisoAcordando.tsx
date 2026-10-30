import { useEffect, useState } from 'react'
import { Banner } from '../../componentes/Banner'
import { CarregandoLinha } from '../../componentes/Carregando'

export function AvisoAcordando({ ativo }: { ativo: boolean }) {
  const [segundos, setSegundos] = useState(0)

  useEffect(() => {
    if (!ativo) {
      setSegundos(0)
      return
    }
    const inicio = Date.now()
    const temporizador = window.setInterval(() => {
      setSegundos(Math.floor((Date.now() - inicio) / 1000))
    }, 1000)
    return () => window.clearInterval(temporizador)
  }, [ativo])

  if (!ativo || segundos < 8) return null

  return (
    <Banner tipo="aviso">
      A Sera está acordando. O servidor pode levar até um minuto na primeira mensagem do
      dia. <CarregandoLinha texto={`${segundos}s`} />
    </Banner>
  )
}
