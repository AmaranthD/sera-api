# Relógio e memória da Sera

> **Status em 2026-11-01:** relógio, memória/preferências e a tela de
> gerenciamento em `/conta` implementados. A Sera também consegue esquecer
> algo a pedido, com confirmação.

## 0. Visão geral

| Peça | Onde fica |
|---|---|
| Relógio e datas relativas | `sera/api/relogio.py` |
| Ferramentas de memória | `sera/api/ferramentas.py` |
| Rotas de CRUD e exportação | `sera/api/rotas.py` |
| Tela de gerenciamento | `web/src/telas/conta/` |

## 1. Relógio interno

O modelo não tem relógio. A cada requisição, `sera/api/rotas.py` injeta um
bloco `# AGORA` no system prompt, gerado por `sera/api/relogio.py`:

```
# AGORA
Data e hora: domingo, 01/11/2026, 10:32 (America/Sao_Paulo).
Referências:
- "hoje" = 01/11/2026
- "ontem" = 31/10/2026
- "esta semana" = 26/10/2026 a 01/11/2026
- "última semana" / "últimos 7 dias" = 26/10/2026 a 01/11/2026
- "semana passada" = 19/10/2026 a 25/10/2026
- "este mês" = novembro de 2026
- "mês passado" = outubro de 2026
```

- Fuso configurável em `SERA_FUSO` (padrão `America/Sao_Paulo`).
- O bloco é gerado por request; nunca é cacheado.
- O Render roda em UTC, por isso o fuso explícito é obrigatório.

### Datas na busca

Antes de chamar a Tavily, referências relativas são trocadas por datas
absolutas em `normalizar_consulta()`:

- `"previsão do tempo hoje"` → `"previsão do tempo 01/11/2026"`
- `"notícias da última semana"` → `"notícias da 26/10/2026 a 01/11/2026"`
- `"hoje em dia"` → `"atualmente"` (não é data)

O bloco de resultados também avisa a data de hoje e pede para sinalizar
fontes antigas.

## 2. Memória e preferências

Duas ferramentas novas, disponíveis quando `SERA_APRENDIZADO=true` e o
provedor aceita tool calling (`LLM_PROVIDER=openai`):

| Ferramenta | O que faz | Onde grava |
|---|---|---|
| `lembrar(texto, categoria)` | guarda um fato durável | tabela `memorias` |
| `ajustar_preferencia(tipo, texto/valor)` | muda apelido, formato, assunto ou níveis | tabela `ajustes` |
| `esquecer(texto, confirmado)` | apaga uma memória, com confirmação | tabela `memorias` |

As duas já existiam no banco, no prompt (`# SOBRE A PESSOA` e
`# AJUSTES APRENDIDOS`) e na API. O que faltava era o modelo conseguir
escrever.

### Categorias de memória

`familia`, `trabalho`, `gostos`, `rotina`, `saude`, `outro`.

### Tipos de ajuste

- Texto: `apelido`, `piada_interna`, `formato`, `assunto`.
- Nível: `nivel_sarcasmo`, `formalidade`, `nivel_tecnico`, `toque_yandere`.
- Knobs são substituídos ao mudar o mesmo tipo; texto é deduplicado.
- Teto de 20 ajustes por pessoa (o mesmo do prompt).

### Proteções

- `contem_segredo` recusa CPF, cartão, senha, token e afins.
- Memórias duplicadas não são gravadas de novo.
- Memórias de `saude` só são gravadas com `confirmado=true` **e** um pedido
  explícito ("lembre que...", "anota isso") ou um sim claro na mensagem
  atual da pessoa. O modelo não consegue autorizar sozinho.
- `esquecer` também é em dois passos: primeiro devolve o que encontrou,
  depois apaga com `confirmado=true`. Se houver mais de uma memória
  parecida, devolve as candidatas em vez de apagar.
- Limite de 100 memórias e 20 ajustes por pessoa. As mais novas têm
  prioridade no prompt quando o orçamento aperta.
- O prompt proíbe prometer lembretes futuros: a Sera não tem agenda nem
  notificações.
- Cada pessoa só enxerga a própria memória (RLS no Supabase; `pessoa_id` no
  SQLite).

## 3. Tela em `/conta`

A tela de conta ganhou três blocos:

- **O que a Sera sabe sobre você:** lista as memórias com categoria, edição
  no lugar e exclusão com confirmação.
- **Ajustes aprendidos:** lista apelido, formato, assunto e níveis; edição
  por texto ou select, exclusão com confirmação.
- **Seus dados:** botão “Baixar meus dados (JSON)” com perfil, memórias,
  ajustes, conversas e mensagens.

As rotas usadas:

| Método | Rota |
|---|---|
| `PATCH` | `/pessoas/{id}/memorias/{memoria_id}` |
| `DELETE` | `/pessoas/{id}/memorias/{memoria_id}` |
| `PATCH` | `/pessoas/{id}/ajustes/{ajuste_id}` |
| `DELETE` | `/pessoas/{id}/ajustes/{ajuste_id}` |
| `GET` | `/pessoas/{id}/dados` (JSON com `Content-Disposition`) |

O download é montado no navegador a partir do JSON; nenhum dado passa por
outro serviço.

### Por que não extrair memória automaticamente

Extração a cada mensagem custa tokens, gera memória falsa e fica invasiva.
O modelo só grava quando percebe um fato durável ou um pedido explícito.
Se um dia houver resumo automático, o lugar certo é um job noturno, não o
caminho do chat.

## 4. SQLite ou Supabase

O projeto já abstrai os dois backends:

- **SQLite** (`sera/api/db.py`): desenvolvimento local e testes.
- **Supabase** (`sera/api/db_supabase.py`): produção, via PostgREST + RLS.

Memória e ajustes usam as mesmas tabelas nos dois. Não criar um SQLite
separado para o aprendizado: o disco do Render free é efêmero e não
sincroniza entre dispositivos.

## Pendente (próximas fases)

- Confirmação em dois passos também para finanças (hoje o código cobre
  `saude`; finanças ficam na regra do prompt).
- Expiração ou arquivamento de memórias antigas.
- Notificações/agenda, se um dia a Sera for lembrar de datas sozinha.
- Criptografia em repouso extra para memórias sensíveis, se o produto
  exigir.
