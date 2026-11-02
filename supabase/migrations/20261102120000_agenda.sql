-- Agenda por pessoa e inscrições de Web Push.
--
-- `inicio`, `fim` e `lembrete_em` ficam em UTC (timestamptz). O fuso é só
-- para exibir o compromisso no horário de quem o criou.
-- A checagem de sobreposição é feita pela API antes de gravar; o índice
-- ajuda a consultar a agenda por intervalo.

create table if not exists public.compromissos (
  id uuid primary key default gen_random_uuid(),
  pessoa_id uuid not null references public.pessoas(id) on delete cascade,
  titulo text not null,
  descricao text not null default '',
  inicio timestamptz not null,
  fim timestamptz not null,
  fuso text not null default 'America/Sao_Paulo',
  lembrete_minutos int not null default 10
    check (lembrete_minutos between 0 and 10080),
  lembrete_em timestamptz not null,
  lembrete_enviado_em timestamptz,
  criado_em timestamptz not null default now(),
  atualizado_em timestamptz not null default now(),
  check (fim > inicio)
);
create index if not exists idx_compromissos_pessoa
  on public.compromissos (pessoa_id, inicio);
create index if not exists idx_compromissos_lembrete
  on public.compromissos (lembrete_em)
  where lembrete_enviado_em is null;

create table if not exists public.push_inscricoes (
  id uuid primary key default gen_random_uuid(),
  pessoa_id uuid not null references public.pessoas(id) on delete cascade,
  endpoint text not null unique,
  p256dh text not null,
  auth text not null,
  user_agent text,
  criada_em timestamptz not null default now()
);
create index if not exists idx_push_inscricoes_pessoa
  on public.push_inscricoes (pessoa_id);

grant select, insert, update, delete
  on public.compromissos, public.push_inscricoes to authenticated;
grant all
  on public.compromissos, public.push_inscricoes to service_role;

alter table public.compromissos enable row level security;
drop policy if exists compromisso_proprio on public.compromissos;
create policy compromisso_proprio on public.compromissos
  for all to authenticated
  using (pessoa_id = auth.uid())
  with check (pessoa_id = auth.uid());

alter table public.push_inscricoes enable row level security;
drop policy if exists inscricao_propria on public.push_inscricoes;
create policy inscricao_propria on public.push_inscricoes
  for all to authenticated
  using (pessoa_id = auth.uid())
  with check (pessoa_id = auth.uid());
