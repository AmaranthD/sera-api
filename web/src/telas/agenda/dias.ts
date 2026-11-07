const DIA_MS = 24 * 60 * 60 * 1000

function inicioDoDia(data: Date): number {
  return new Date(data.getFullYear(), data.getMonth(), data.getDate()).getTime()
}

export function chaveDoDia(data: Date): string {
  const mes = String(data.getMonth() + 1).padStart(2, '0')
  const dia = String(data.getDate()).padStart(2, '0')
  return `${data.getFullYear()}-${mes}-${dia}`
}

export function diferencaEmDias(iso: string, referencia: number): number {
  const data = new Date(iso)
  if (Number.isNaN(data.getTime())) return Number.POSITIVE_INFINITY
  return Math.round((inicioDoDia(data) - inicioDoDia(new Date(referencia))) / DIA_MS)
}

export function rotuloDoGrupo(iso: string, referencia: number): string {
  const dias = diferencaEmDias(iso, referencia)
  if (dias < 0) return 'Em andamento'
  if (dias === 0) return 'Hoje'
  if (dias === 1) return 'Amanhã'
  if (dias < 7) return 'Esta semana'
  return 'Depois'
}

export function contagemRegressiva(
  inicio: string,
  fim: string,
  referencia: number,
): string {
  const inicioMs = new Date(inicio).getTime()
  const fimMs = new Date(fim).getTime()
  if (Number.isNaN(inicioMs) || Number.isNaN(fimMs)) return ''
  if (inicioMs <= referencia && fimMs >= referencia) return 'agora'
  if (fimMs < referencia) return ''

  const minutos = Math.ceil((inicioMs - referencia) / 60_000)
  if (minutos <= 1) return 'em instantes'
  if (minutos < 60) return `em ${minutos} min`

  const horas = Math.floor(minutos / 60)
  const resto = minutos % 60
  if (horas < 24) {
    return resto === 0 ? `em ${horas}h` : `em ${horas}h ${resto}min`
  }

  const dias = Math.floor(horas / 24)
  return dias === 1 ? 'em 1 dia' : `em ${dias} dias`
}

export function faixaDeDias(referencia: number): Date[] {
  const base = new Date(referencia)
  base.setHours(0, 0, 0, 0)
  return Array.from({ length: 7 }, (_, indice) => {
    const data = new Date(base)
    data.setDate(base.getDate() + indice)
    return data
  })
}

export function rotuloCurtoDoDia(data: Date): string {
  return new Intl.DateTimeFormat('pt-BR', { weekday: 'short' })
    .format(data)
    .replace('.', '')
}
