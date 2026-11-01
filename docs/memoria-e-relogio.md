# Relógio e memória da Sera

> **Status em 2026-11-01:** relógio e ferramentas de memória/preferências
> implementados. Falta a tela para a pessoa ver, editar e apagar o que foi
> guardado (fase 3).

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
- Assunto sensível deve ser confirmado antes de guardar (regra do prompt).
- O prompt proíbe prometer lembretes futuros: a Sera não tem agenda nem
  notificações.
- Cada pessoa só enxerga a própria memória (RLS no Supabase; `pessoa_id` no
  SQLite).

### Por que não extrair memória automaticamente

Extração a cada mensagem custa tokens, gera memória falsa e fica invasiva.
O modelo só grava quando percebe um fato durável ou um pedido explícito.
Se um dia houver resumo automático, o lugar certo é um job noturno, não o
caminho do chat.

## 3. SQLite ou Supabase

O projeto já abstrai os dois backends:

- **SQLite** (`sera/api/db.py`): desenvolvimento local e testes.
- **Supabase** (`sera/api/db_supabase.py`): produção, via PostgREST + RLS.

Memória e ajustes usam as mesmas tabelas nos dois. Não criar um SQLite
separado para o aprendizado: o disco do Render free é efêmero e não
sincroniza entre dispositivos.

## Pendente (fase 3)

- Tela para listar, editar e apagar memórias e ajustes.
- Ferramenta `esquecer` ou equivalente para "não lembre mais disso".
- Política de confirmação mais explícita para saúde/finanças.
- Exportar tudo o que a Sera sabe sobre a pessoa (LGPD).
- Limite/expiração de memórias antigas.
