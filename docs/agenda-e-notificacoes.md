# Agenda e notificações

Compromissos são por pessoa e nunca se sobrepõem: a API recusa com `409`
quando o intervalo cruza um compromisso existente da mesma pessoa. Horários
que apenas se encostam (`fim` de um == `inicio` do outro) são permitidos.

## Modelo

- `compromissos`: `titulo`, `descricao`, `inicio`, `fim`, `fuso`,
  `lembrete_minutos`, `lembrete_em` e `lembrete_enviado_em`.
- `push_inscricoes`: uma inscrição de Web Push por navegador/dispositivo.
- `inicio`, `fim` e `lembrete_em` ficam em UTC. O `fuso` é só de exibição.

O lembrete dispara quando `lembrete_em <= agora` e o compromisso ainda não
terminou. O disparo reivindica o compromisso antes de enviar, então duas
instâncias da API não mandam a mesma notificação duas vezes.

## Rotas

| Método | Caminho | Uso |
| --- | --- | --- |
| `GET` | `/pessoas/{id}/compromissos` | lista (aceita `de`/`ate`) |
| `POST` | `/pessoas/{id}/compromissos` | cria; `409` em sobreposição |
| `PATCH` | `/pessoas/{id}/compromissos/{compromisso}` | edita |
| `DELETE` | `/pessoas/{id}/compromissos/{compromisso}` | apaga |
| `GET` | `/notificacoes/chave` | chave pública VAPID |
| `GET` | `/pessoas/{id}/notificacoes/inscricoes` | lista dispositivos |
| `POST` | `/pessoas/{id}/notificacoes/inscricoes` | registra inscrição |
| `DELETE` | `/pessoas/{id}/notificacoes/inscricoes?endpoint=...` | remove |
| `POST` | `/pessoas/{id}/notificacoes/teste` | envia um teste |
| `POST` | `/notificacoes/disparar` | cron; exige `X-Sera-Segredo` |

## Ferramentas da IA

Com tool calling ativo (`llm_provider=openai`), a Sera recebe três
ferramentas:

| Ferramenta | Uso |
| --- | --- |
| `agendar` | cria compromisso (`titulo`, `inicio`, `fim`, `descricao`, `lembrete_minutos`) |
| `consultar_agenda` | lista por período (`de`/`ate`); sem período, próximos 30 dias |
| `cancelar_compromisso` | apaga por `id` ou trecho do `titulo` |

As datas entram como `AAAA-MM-DD` ou `AAAA-MM-DDTHH:MM`, sem fuso; o
`FUSO_HORARIO` da pessoa é aplicado e o banco guarda tudo em UTC. O lembrete
padrão é 10 minutos antes e o fim padrão é uma hora depois do início. Se o
horário cruzar outro compromisso, a ferramenta devolve o conflito em vez de
gravar.

## Respostas do chat

Quando um job assíncrono (`POST /chat/job`) termina, a API envia Web Push
para todas as inscrições da pessoa: título "Sera", aviso de que a resposta
chegou (ou de erro) e link para `/c/{conversa_id}`. Por privacidade, o
conteúdo da resposta **não** aparece na tela de bloqueio; para mostrar uma
prévia de até 140 caracteres, defina `NOTIFICACOES_PREVIEW=true`. Exige
VAPID configurado e notificações ativadas no dispositivo (Agenda → Ativar
notificações). O service worker não mostra a notificação quando a conversa
já está aberta e visível, para não duplicar o polling. Jobs cancelados não
notificam.

## Configuração

```bash
uv pip install "pywebpush>=2.0"
```

Variáveis de ambiente:

```bash
VAPID_PUBLIC_KEY=...
VAPID_PRIVATE_KEY=...
VAPID_SUBJECT=mailto:voce@exemplo.com
NOTIFICACOES_SEGREDO=...        # inventado, longo e aleatório
NOTIFICACOES_PREVIEW=false      # true mostra prévia da resposta no push
SUPABASE_SERVICE_KEY=...        # só em produção (disparo entre usuários)
```

Gerar um par VAPID:

```bash
python - <<'PY'
from py_vapid import Vapid
import base64
v = Vapid(); v.generate_keys()
raw = v.public_key.public_numbers()
pub = base64.urlsafe_b64encode(
    b'\x04' + raw.x.to_bytes(32, 'big') + raw.y.to_bytes(32, 'big')
).decode().rstrip('=')
priv = base64.urlsafe_b64encode(
    v.private_key.private_numbers().private_value.to_bytes(32, 'big')
).decode().rstrip('=')
print('VAPID_PUBLIC_KEY=' + pub)
print('VAPID_PRIVATE_KEY=' + priv)
PY
```

A chave pública é entregue ao navegador; a privada nunca sai do servidor.
Trocar o par invalida as inscrições existentes (as pessoas precisam ativar de
novo).

## Disparo em produção

O Render free dorme sem tráfego, então um laço em memória não basta. O
workflow `.github/workflows/lembretes.yml` chama `/notificacoes/disparar` a
cada 5 minutos. Configure os secrets:

- `SERA_API_URL` — URL da API (ex.: `https://sera-api.onrender.com`)
- `SERA_NOTIFICACOES_SEGREDO` — o mesmo valor de `NOTIFICACOES_SEGREDO`

Enquanto a API está acordada, o laço interno também dispara a cada
`NOTIFICACOES_INTERVALO` segundos (padrão 60), sem duplicar envios.

## Limites conhecidos

- No iPhone, Web Push só funciona com a Sera instalada na tela inicial
  (iOS 16.4+).
- As inscrições mortas (`404`/`410`) são removidas automaticamente no envio.
- Os handlers de push ficam em `web/public/push-handlers.js` e são carregados
  pelo service worker do PWA via `importScripts`, usando o mesmo escopo `/`.
