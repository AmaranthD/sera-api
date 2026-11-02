-- Chat assíncrono: resposta gerada no servidor mesmo se o app fechar.
-- `gerando` é o estado intermediário; `fontes` guarda os links citados.

alter table public.mensagens
  add column if not exists fontes jsonb not null default '[]'::jsonb;

alter table public.mensagens
  drop constraint if exists mensagens_status_check;

alter table public.mensagens
  add constraint mensagens_status_check
  check (status in ('gerando', 'completa', 'interrompida', 'erro'));
