import type { Pessoa } from '../dominios/tipos'

/**
 * Escolhe a pessoa dona da sessão.
 *
 * Nunca use `pessoas[0]`: com mais de uma conta no mesmo ambiente (ou uma
 * resposta antiga em cache), isso faz a Sera assumir o perfil de outra pessoa
 * e o chat responde "sem acesso a esta conversa".
 */
export function selecionarPessoa(
  pessoas: Pessoa[],
  usuarioId: string | null,
): Pessoa | null {
  if (!usuarioId) return null

  const propria = pessoas.find((pessoa) => pessoa.id === usuarioId)
  if (propria) return propria

  // Compatibilidade com ambientes sem auth (SERA_DEV) e bases antigas: só
  // aceita o fallback quando existe exatamente uma pessoa. Com duas ou mais,
  // é melhor voltar ao onboarding do que usar o perfil errado.
  return pessoas.length === 1 ? (pessoas[0] ?? null) : null
}
