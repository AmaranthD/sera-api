# Ordem das camadas do prompt

## Status

accepted

## Decisão

O system prompt é montado em cinco blocos, nesta ordem: limites invioláveis, personalidade base, ajustes aprendidos, memória da pessoa e um lembrete final de que os limites prevalecem. Os limites aparecem no topo porque precisam dominar todo o resto, e de novo no fim porque o modelo dá mais peso ao que está perto da pergunta; a repetição é uma defesa barata contra deriva.

## Consequências

- Limites e base nunca são truncados; ajustes e memória têm orçamento em caracteres e degradam com aviso, nunca em silêncio.
- A camada base é renderizada por um renderizador curado, não por um despejo do YAML: `versao` é metadado, os presets de `adaptacao_por_usuario` são resolvidos para a pessoa em vez de todos emitidos, e `exemplos_de_voz` entram como referência de tom, não como texto a decorar.
- Ajustes aprendidos são valores absolutos com teto por botão, nunca deltas. Assim o `anti_deriva` do YAML vira uma propriedade verificável do código em vez de uma promessa no texto.
