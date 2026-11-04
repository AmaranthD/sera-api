-- Texto diário: assinatura por pessoa, horário local e conversa dedicada.
--
-- O horário é `HH:MM` no fuso escolhido; `ultimo_envio_dia` guarda o dia
-- local já entregue para o cron não repetir. `conversa_id` aponta para a
-- conversa "Texto diário" criada na primeira entrega.

create table if not exists public.texto_diario_assinaturas (
  pessoa_id uuid primary key references public.pessoas(id) on delete cascade,
  ativo boolean not null default false,
  hora text not null default '07:00'
    check (hora ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'),
  fuso text not null default 'America/Sao_Paulo',
  conversa_id uuid references public.conversas(id) on delete set null,
  ultimo_envio_dia date,
  criado_em timestamptz not null default now(),
  atualizado_em timestamptz not null default now()
);
create index if not exists idx_texto_diario_ativos
  on public.texto_diario_assinaturas (ativo)
  where ativo;

grant select, insert, update, delete
  on public.texto_diario_assinaturas to authenticated;
grant all
  on public.texto_diario_assinaturas to service_role;

alter table public.texto_diario_assinaturas enable row level security;
drop policy if exists texto_diario_proprio on public.texto_diario_assinaturas;
create policy texto_diario_proprio on public.texto_diario_assinaturas
  for all to authenticated
  using (pessoa_id = auth.uid())
  with check (pessoa_id = auth.uid());
