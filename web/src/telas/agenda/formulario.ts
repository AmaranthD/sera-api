export const LEMBRETES = [0, 5, 10, 15, 30, 60, 120, 1440]

export interface Formulario {
  titulo: string
  descricao: string
  inicio: string
  fim: string
  lembrete: number
}

export function paraEntradaLocal(iso: string): string {
  const data = new Date(iso)
  if (Number.isNaN(data.getTime())) return ''
  const local = new Date(data.getTime() - data.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 16)
}

export function deEntradaLocal(valor: string): string {
  return new Date(valor).toISOString()
}

function inicioPadrao(): string {
  const agora = new Date()
  agora.setMinutes(agora.getMinutes() + (15 - (agora.getMinutes() % 15 || 15)))
  agora.setSeconds(0, 0)
  return paraEntradaLocal(agora.toISOString())
}

export function fimPadrao(inicio: string): string {
  const data = new Date(deEntradaLocal(inicio))
  data.setHours(data.getHours() + 1)
  return paraEntradaLocal(data.toISOString())
}

export function novoFormulario(): Formulario {
  const inicio = inicioPadrao()
  return {
    titulo: '',
    descricao: '',
    inicio,
    fim: fimPadrao(inicio),
    lembrete: 10,
  }
}

export function rotuloLembrete(minutos: number): string {
  if (minutos === 0) return 'na hora'
  if (minutos < 60) return `${minutos} min antes`
  if (minutos === 60) return '1 hora antes'
  if (minutos === 1440) return '1 dia antes'
  return `${minutos / 60} horas antes`
}
