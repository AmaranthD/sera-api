# Sera — prompt e personalidade

Contexto que define quem a Sera é e como o system prompt é montado. O `personality.yaml` é a fonte da verdade da camada base; o montador transforma isso em prompt.

## Linguagem

**Pessoa**:
Quem está conversando com a Sera, identificada por nome, faixa etária e perfil.
_Avoid_: usuário, cliente, familiar

**Limites invioláveis**:
Regras que nenhum perfil, ajuste aprendido, pedido ou roleplay pode sobrescrever. Ocupam a primeira e a última posição do prompt.
_Avoid_: regras de segurança, guardrails, restrições

**Camada base**:
Personalidade escrita à mão no `personality.yaml`, fora os limites invioláveis. Só o dono do sistema a edita.
_Avoid_: personalidade padrão, personality base

**Perfil**:
Preset de estilo escolhido para uma pessoa (`padrao`, `crianca_adolescente`, `idoso_ou_pouco_tecnico`). Fornece valores iniciais para os botões de estilo.
_Avoid_: preset, modo, adaptação

**Ajuste aprendido**:
Preferência acumulada de uma pessoa, guardada como item tipado na camada 3. Pode baixar um botão de estilo, nunca passar do teto da base.
_Avoid_: personality_learned, customização, preferência

**Memória**:
Fatos sobre uma pessoa, guardados na camada 4, mais a lista explícita de assuntos que não devem ser trazidos à conversa.
_Avoid_: histórico, contexto, memória do usuário

**Conversa**:
Sequência persistida de mensagens entre uma pessoa e a Sera, identificada por um id e sempre pertencente a uma única pessoa.
_Avoid_: sessão, chat, thread

**Mensagem**:
Um item persistido de uma conversa, com papel `user` ou `assistant` e status de conclusão. É a unidade do histórico.
_Avoid_: turno, evento, fala

**Histórico**:
As mensagens completas de uma conversa que entram no contexto do modelo, limitadas por janela e orçamento. Não se confunde com memória: histórico é o que foi dito, memória é o que se sabe sobre a pessoa.
_Avoid_: contexto, transcript, log

**Faixa etária**:
Declaração obrigatória de que a pessoa é adulto, adolescente ou criança. Determina os limites de sarcasmo e desliga o toque dramático para menores.
_Avoid_: idade, público

**Teto**:
Valor máximo que um ajuste aprendido pode atingir em cada botão de estilo. Existe para impedir que ajustes amplifiquem traços de forma cumulativa.
_Avoid_: limite, máximo, cap

**Botão de estilo**:
Um dos valores ajustáveis do perfil: nível de sarcasmo, formalidade, nível técnico e toque dramático.
_Avoid_: parâmetro, configuração, knob

## Notas

**Nota**:
Um arquivo Markdown do vault, identificado pelo caminho relativo à raiz. O frontmatter dá as tags; o primeiro `#` dá o título.
_Avoid_: documento, arquivo, página

**Seção**:
Um pedaço da nota delimitado por `##`, com o texto antes do primeiro `##` como seção sem nome. É a unidade indexada.
_Avoid_: chunk, bloco, pedaço

**Trecho**:
A seção já recuperada e pronta para entrar no prompt, com nome da nota e da seção. Vive na camada `CONTEXTO`.
_Avoid_: resultado, hit, chunk

**Índice**:
O conteúdo derivado das notas guardado no SQLite (tabelas `notas`, `trechos` e `trechos_fts`). Pode ser apagado e reconstruído a qualquer momento.
_Avoid_: cache, base vetorial, embeddings

## Montagem

**Bloco**:
Uma camada já renderizada, com título e conteúdo, pronta para entrar no prompt.
_Avoid_: seção, parte

**Camada de contexto**:
Os trechos de nota recuperados para a mensagem atual. Não se confunde com memória: memória é fato sobre a pessoa, contexto é o que está escrito nas notas.
_Avoid_: RAG, documentos, base de conhecimento

**Prompt montado**:
O resultado do montador: a lista ordenada de blocos, os botões efetivos e os avisos. A string enviada ao modelo é o `render()` disso.
_Avoid_: prompt final, system prompt
