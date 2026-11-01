# Design v1 — Sera, a Sentinela

> **Status:** v1 lançada em 2026-11-01. Este documento é a fonte das regras
> visuais. Qualquer mudança de design deve atualizar este arquivo.

## 1. Conceito

A Sera não é uma personagem de desenho. É uma **sentinela**: uma presença
calma, séria e protetora, feita de aço, ouro e noite. O pixel art da pasta
`op/` é a referência de proporção, luz e material — não de caricatura.

A interface tem dois mundos:

| Mundo | Onde | Sensação |
|---|---|---|
| **O santuário** | chat, login (lado esquerdo) | noite, aço, ouro, silêncio, a paladina ao fundo |
| **O registro** | sidebar, conta, login (cartão) | pergaminho, tinta, selo, leitura |

O chat é **sempre escuro**, mesmo no tema claro. A sidebar e as páginas de
conta seguem o tema do sistema. Essa divisão vem do mockup em `desing/`.

## 2. Referências

| Pasta | Arquivo | Uso |
|---|---|---|
| `op/` | paladina de corpo inteiro | referência principal de silhueta, armadura, asas, halo e paleta |
| `logo/` | elmo em close | marca/medalhão da Sera |
| `bg/` | vídeo vertical da paladina | fundo do chat, bem apagado |
| `desing/` | mockup cru | ponto de partida da divisão sidebar clara + chat escuro |

## 3. Paleta

### Tema claro (pergaminho)

| Token | Hex | Uso |
|---|---|---|
| `--paper` | `#f3ecdc` | fundo da página |
| `--paper-alto` | `#e9dfca` | sidebar |
| `--superficie` | `#fbf6ea` | cartões e campos |
| `--tinta` | `#1c1a18` | texto |
| `--tinta-suave` | `#4f4a40` | texto secundário |
| `--tinta-fraca` | `#6d6658` | legendas |
| `--ouro` / `--indigo` | `#b8892f` | ação, foco, destaque |
| `--ouro-claro` | `#e0b45c` | hover do ouro |
| `--aco` | `#6f7d99` | informação neutra |
| `--azul` | `#3d5fa8` | links e detalhes |
| `--perigo` | `#b84a3e` | destruir/sair |

### Tema escuro (aço)

| Token | Hex | Uso |
|---|---|---|
| `--paper` | `#070a14` | fundo |
| `--paper-alto` | `#0b1020` | sidebar |
| `--superficie` | `#10162a` | cartões |
| `--tinta` | `#e9edf8` | texto |
| `--tinta-suave` | `#b8c2d8` | texto secundário |
| `--ouro` / `--indigo` | `#e0b45c` | ação |
| `--azul` | `#7d9bff` | links |

### Santuário (chat, sempre escuro)

| Token | Valor | Uso |
|---|---|---|
| `--chat-fundo` | `#080c18` | canvas |
| `--chat-fundo-2` | `#0d1326` | variação |
| `--chat-superficie` | `rgba(16, 23, 42, 0.82)` | balões, composer |
| `--chat-texto` | `#e9edf8` | texto |
| `--chat-texto-suave` | `#b8c2d8` | secundário |
| `--chat-texto-fraco` | `#8b96b0` | legendas |
| `--chat-ouro` | `#d8ad5c` | ação, borda de destaque |
| `--chat-linha` | `rgba(200, 212, 235, 0.16)` | divisórias |

Regras:

- Ouro é **ação e foco**, não decoração. Não pinte tudo de dourado.
- Azul/aço é informação; vermelho é perigo.
- Nunca use branco puro (`#fff`) como fundo ou texto principal.
- O antigo indigo `#4f46e5` está proibido.

## 4. Tipografia

| Papel | Fonte | Regra |
|---|---|---|
| Títulos | **Cinzel** | 400/600, caixa normal, elegante e lapidada |
| Marca e rótulos | **Silkscreen** | só em marca, legendas e labels de seção; 8–24px |
| Corpo | system sans | 16.5–17px, line-height 1.6 |

- **Nunca** use Silkscreen em parágrafos longos.
- Rótulos em pixel: maiúsculas, `letter-spacing` 0.12–0.18em, 8–10px.
- A palavra “Sera” na marca fica em caixa mista (não `SERA`), para não
  parecer um “Å” no Silkscreen.

## 5. Regras de pixel sem cartoon

- Raio de borda: **4px** (controles) ou **6px** (painéis). Nada de pill
  `999px`.
- Bordas: **2px** nos controles; 1–2px em divisórias.
- Sombra: **dura e deslocada** (2–5px), sem blur. Ex.:
  `box-shadow: 3px 3px 0 var(--sombra-dura-cor)`.
- Hover/active: deslocamento de 2–3px com `steps(1)`, não animação elástica.
- Sem gradientes de vidro, sem brilho 3D, sem bevel, sem emoji na UI.
- Ícones continuam lineares (stroke 1.8); não virar ícone de desenho.
- `image-rendering: pixelated` só em pixel art pequena (logo/avatar), nunca no
  texto ou no vídeo de fundo.
- O pixel art é **sério e esculpido**: armadura, asas, ouro, halo. Não é
  mascote fofo, não tem olhos grandes, não tem contorno grosso de cartoon.

## 6. Marca

- Arquivo: `web/public/marca-sera.webp` (512×512, ~67 KB), derivado de
  `imgs/logo/`.
- Uso principal: medalhão quadrado de 44px (34px na variante pequena), borda
  de 2px em ouro, raio 4px, `image-rendering: pixelated`.
- A palavra “Sera” fica ao lado em Silkscreen.
- Ícones do PWA derivam do mesmo medalhão:
  - `icon-192.png`, `icon-512.png`, `apple-touch-icon.png` com moldura dourada;
  - `icon-maskable-512.png` com o elmo reduzido sobre campo noturno e anel
    dourado.
- Tamanho mínimo: 32px. Não esticar, não remover a moldura sobre fundo
  movimentado.

## 7. Fundo do chat (vídeo)

- Origem: `imgs/bg/gemini_generated_video_d1128780.mp4` (720×1280, 24fps,
  10s, com áudio).
- Saída: `web/public/fundo/paladina.webm` (~797 KB) e
  `paladina.mp4` (~604 KB), 540×960, 20fps, **sem áudio**.
- Poster: `web/public/fundo/paladina-poster.webp` (~64 KB).
- Opacidade: **0.08 no desktop**, **0.06 no mobile**. É para ser um fantasma:
  a pessoa só percebe quando repara.
- `object-fit: cover`; `object-position: center 20%` (desktop) e `16%`
  (mobile).
- Véu: gradiente radial + linear em `rgba(8,12,24,...)` para escurecer o
  centro e as bordas.
- Grain: linhas horizontais de 1px a 4% de opacidade (`mix-blend-mode:
  overlay`), para lembrar pixel/CRT sem sujar o texto.
- Comportamento: `autoplay`, `muted`, `loop`, `playsInline`, sem controles,
  `pointer-events: none`, `aria-hidden`.
- `prefers-reduced-motion`: não autoplay; fica o poster.
- O vídeo **não** entra no precache do PWA. Poster e marca podem entrar.
- Texto nunca fica diretamente sobre a parte clara: balões têm fundo sólido.

### Comando de geração

```bash
ffmpeg -i imgs/bg/gemini_generated_video_d1128780.mp4 -an \
  -vf "scale=540:-2,fps=20" -c:v libvpx-vp9 -crf 40 -b:v 0 -row-mt 1 \
  web/public/fundo/paladina.webm

ffmpeg -i imgs/bg/gemini_generated_video_d1128780.mp4 -an \
  -vf "scale=540:-2,fps=20" -c:v libx264 -crf 30 -preset slow \
  -pix_fmt yuv420p -movflags +faststart \
  web/public/fundo/paladina.mp4

ffmpeg -ss 0 -i imgs/bg/gemini_generated_video_d1128780.mp4 -frames:v 1 \
  -vf "scale=540:-2" -c:v libwebp -quality 82 \
  web/public/fundo/paladina-poster.webp
```

## 8. Layout

- **Chat:** sidebar de 320px + canvas escuro. O canvas tem o vídeo no fundo
  (`z-index: 0`) e todo o conteúdo em `z-index: 1`.
- **Sidebar:** pergaminho no claro, aço no escuro; item ativo com barra de
  ouro à esquerda.
- **Login:** metade esquerda é o santuário com a paladina a 52% e um gradiente
  escuro para o texto; metade direita é o cartão de pergaminho.
- **Conta:** página de pergaminho/aço, cartão com sombra dura, seções de
  memória e ajustes em cartões menores.
- **Mobile:** sidebar vira drawer; welcome e composer precisam caber na tela
  (não usar `min-height: 100%` em filho de flex sem `min-height: 0`).

## 9. Acessibilidade e leitura

- Contraste: texto em `--chat-texto` sobre balão opaco; legendas em
  `--chat-texto-fraco` só para informação secundária.
- O vídeo é decorativo (`aria-hidden`) e não captura clique.
- `prefers-reduced-motion` desliga o autoplay e as animações.
- Não usar o vídeo como única indicação de estado.
- Testar em tela real: o vídeo parece mais forte no celular.

## 10. Faça / não faça

**Faça**

- Use Cinzel para títulos e Silkscreen para a marca/rótulos.
- Mantenha o chat escuro e a sidebar no tema do sistema.
- Use ouro para ação; aço/azul para informação.
- Preserve a paladina como detalhe, não como protagonista.
- Use sombras duras e bordas de 2px.

**Não faça**

- Não use cartoon, mascote, emoji ou olhos grandes.
- Não use pills/raios grandes, blur, vidro ou gradiente colorido.
- Não aumente a opacidade do vídeo acima de 0.1.
- Não coloque texto em cima da parte clara da armadura/asas.
- Não use a paleta antiga de indigo `#4f46e5`.
- Não transforme o pixel font em texto corrido.

## 11. Arquivos da v1

| Arquivo | O que é |
|---|---|
| `web/src/estilos/global.css` | tokens, temas, base |
| `web/src/telas/chat/FundoPaladina.tsx` | vídeo de fundo |
| `web/src/componentes/Marca.tsx` | medalhão + wordmark |
| `web/src/telas/login/Login.tsx` | hero da paladina |
| `web/public/marca-sera.webp` | logo |
| `web/public/paladina.webp` | ilustração do login |
| `web/public/fundo/*` | vídeo e poster |
| `web/scripts/gerar-assets-design.mjs` | gera logo, ícones e ilustração |

## 13. Instalação e link compartilhável

- Link público: **`https://sera-chat.pages.dev/instalar`**
- A página não exige login e serve para mandar para alguém. Ela mostra:
  - botão nativo de instalar quando o navegador dispara
    `beforeinstallprompt`;
  - instruções para iPhone (Safari → Compartilhar → Adicionar à Tela de
    Início) e Android (Chrome → menu → Instalar app);
  - “Copiar link” e “Enviar no WhatsApp”;
  - aviso de cache de ícone/barra do sistema.
- O evento de instalação fica em um store global (`usePwa.ts`) para não se
  perder quando a pessoa navega até `/instalar`.
- PWA:
  - `theme_color` e `background_color`: `#080c18`;
  - um único `<meta name="theme-color" content="#080c18">`, para a barra do
    navegador/app não puxar o pergaminho;
  - ícones versionados (`icon-*-v2.png`) para forçar a troca do ícone antigo
    na tela inicial;
  - se o ícone continuar antigo, remover o atalho, limpar os dados do site e
    instalar de novo.
- **Barra do sistema:** a barra com voltar/menu do Android é controlada pelo
  tema/Material You do aparelho, não pelo site. O app controla a cor da
  barra do navegador/PWA; se ela estiver verde, o ajuste é no tema do
  celular (ou trocar o accent do sistema).


## 14. Próximos passos (v2)

- Logo com transparência real (hoje o recorte é JPEG com fundo azul).
- Ornamentos de canto/dither nos painéis, com moderação.
- Variante do vídeo para `save-data` (ou esconder no 3G).
- Teste visual em aparelhos reais (o vídeo muda muito de tela para tela).
- Se um dia houver tema claro no chat, ele precisa de outro tratamento de
  véu — o atual é feito para o santuário escuro.
