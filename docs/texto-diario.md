# Texto diário

Entrega diária do “Exame das Escrituras Diariamente” (texto diário) do
JW.org. A mensagem é **determinística**: o texto real e os links entram no
chat sem passar pelo modelo, então não há resumo, invenção nem custo de LLM.

## Fonte

O backend lê a página pública do dia:

```
https://wol.jw.org/pt/wol/dt/r5/lp-t/AAAA/MM/DD
```

Dela saem o título (dia da semana e data), o versículo-tema, o comentário e
todos os links internos (versículos e publicações). O parser está em
`sera/api/texto_diario.py` e tem um fixture de teste em
`tests/fixtures/texto_diario_2026_11_04.html`.

Este fluxo lê o WOL diretamente, sem passar pelo `jw-mcp`: a entrega diária
é determinística e não pode depender de o serviço JW estar acordado.

Todos os links do texto são convertidos para URLs absolutas do `jw.org`.
No chat, `MensagemMarkdown` intercepta cliques nesses links e abre um modal
com o conteúdo legível buscado por `GET /jw/conteudo?url=...`. O WOL não
pode ser embutido em iframe (`X-Frame-Options: SAMEORIGIN`), por isso o
modal mostra o texto extraído e oferece “Abrir no JW.org”.

Para links bíblicos (`/wol/bc/`), o texto do link (`Atos 20:35`, `Fil. 1:1`)
vai como `referencia` e o modal mostra **só o versículo citado**, sem as
notas de estudo nem as referências cruzadas. Sem referência, mostra o
capítulo inteiro (também só o texto bíblico).

## Assinatura

No Supabase, aplique `supabase/migrations/20261104000000_texto_diario.sql`
e `supabase/migrations/20261107001705_notificacoes_pgcron.sql` (agendador).
No SQLite local, a migração sobe sozinha na inicialização (versão 5).

Uma linha por pessoa em `texto_diario_assinaturas`:

| Campo | Uso |
| --- | --- |
| `ativo` | liga/desliga o envio diário |
| `hora` | `HH:MM` no fuso escolhido |
| `fuso` | fuso IANA (padrão: o da conta) |
| `conversa_id` | conversa “Texto diário” criada na primeira entrega |
| `ultimo_envio_dia` | dia local já entregue; evita duplicidade |

O horário pode ser alterado a qualquer momento pela tela Conta ou pela
própria Sera (“me manda o texto diário às 7h”). A conversa é separada das
conversas normais; a lista lateral mostra “Texto diário”.

## Rotas

| Método | Caminho | Uso |
| --- | --- | --- |
| `GET` | `/pessoas/{id}/texto-diario` | configuração atual (ou padrão desligado) |
| `PUT` | `/pessoas/{id}/texto-diario` | ativa/desativa e muda hora/fuso |
| `POST` | `/pessoas/{id}/texto-diario/enviar` | entrega o texto de hoje agora |
| `GET` | `/jw/conteudo?url=...` | conteúdo legível para o modal |

## Ferramenta da IA

Com tool calling ativo, a Sera recebe a ferramenta `texto_diario`:

- `ativar` (`hora`, `fuso?`)
- `desativar`
- `alterar_horario` (`hora`)
- `consultar`
- `enviar_agora`

A instrução `INSTRUCAO_TEXTO_DIARIO` pede para perguntar a hora quando ela
não for dita e para não repetir o texto na resposta (só confirmar).

## Disparo

O endpoint `POST /notificacoes/disparar` executa os lembretes da agenda
**e** o texto diário. O agendador principal é o `pg_cron` do Supabase, que
roda a cada minuto e só chama a API quando há algo vencido. O workflow
`.github/workflows/lembretes.yml` continua como fallback a cada 5 minutos.
O laço interno faz o mesmo enquanto a API está acordada.

Para cada assinatura ativa:

1. converte o instante atual para o fuso da pessoa;
2. espera até passar de `hora`;
3. reivindica o dia com `UPDATE ... WHERE ultimo_envio_dia != dia`;
4. busca o texto (cache por dia), cria/reutiliza a conversa e insere a
   mensagem;
5. envia Web Push com o tema e o link `/c/{conversa_id}`.

Se a busca falhar, a reivindicação é liberada e a pessoa tenta de novo
depois de 15 minutos (evita martelar o WOL antes de o texto ser publicado).
Duas instâncias da API não entregam o mesmo dia duas vezes.

O atraso máximo é de cerca de 1 minuto com o `pg_cron`; o workflow do
GitHub é só fallback. O segredo usado pelo agendador fica no Vault do
Supabase com o nome `notificacoes_segredo`. A entrega na conversa funciona
mesmo sem VAPID; a notificação é que depende das chaves e da inscrição do
dispositivo (Agenda → Ativar notificações).

## Limites

- O HTML do WOL pode mudar; os testes de fixture acusam a quebra.
- O texto é de uso pessoal/estudo; a mensagem sempre aponta para a página
  original no JW.org.
- O modal limita o conteúdo a ~14 mil caracteres e mostra o link para a
  página completa.
