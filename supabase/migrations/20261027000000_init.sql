-- Sera — schema inicial (Supabase/Postgres)
-- Identidade em auth.users, dados isolados por RLS e RAG fase 1 com tsvector.

create extension if not exists pgcrypto with schema extensions;
create extension if not exists unaccent with schema extensions;

-- unaccent não é immutable; o wrapper permite usar em coluna gerada.
create or replace function public.sera_unaccent(texto text)
returns text
language sql
immutable
parallel safe
as $$ select extensions.unaccent('extensions.unaccent', texto) $$;

create table if not exists public.pessoas (
  id uuid primary key references auth.users(id) on delete cascade,
  nome text not null,
  faixa_etaria text not null
    check (faixa_etaria in ('adulto', 'adolescente', 'crianca')),
  perfil text not null default 'padrao'
    check (perfil in ('padrao', 'crianca_adolescente', 'idoso_ou_pouco_tecnico')),
  acesso_vault boolean not null default true,
  criada_em timestamptz not null default now()
);

create table if not exists public.conversas (
  id uuid primary key default gen_random_uuid(),
  pessoa_id uuid not null references public.pessoas(id) on delete cascade,
  titulo text,
  criada_em timestamptz not null default now(),
  atualizada_em timestamptz not null default now()
);
create index if not exists idx_conversas_pessoa
  on public.conversas (pessoa_id, atualizada_em desc);

create table if not exists public.mensagens (
  id uuid primary key default gen_random_uuid(),
  conversa_id uuid not null references public.conversas(id) on delete cascade,
  papel text not null check (papel in ('user', 'assistant')),
  conteudo text not null,
  status text not null default 'completa'
    check (status in ('completa', 'interrompida', 'erro')),
  criada_em timestamptz not null default now()
);
create index if not exists idx_mensagens_conversa
  on public.mensagens (conversa_id, criada_em);

create table if not exists public.memorias (
  id uuid primary key default gen_random_uuid(),
  pessoa_id uuid not null references public.pessoas(id) on delete cascade,
  texto text not null,
  categoria text not null default 'outro'
    check (categoria in ('familia', 'trabalho', 'gostos', 'rotina', 'saude', 'outro')),
  criada_em timestamptz not null default now()
);
create index if not exists idx_memorias_pessoa on public.memorias (pessoa_id);

create table if not exists public.nao_mencionar (
  pessoa_id uuid not null references public.pessoas(id) on delete cascade,
  tema text not null,
  primary key (pessoa_id, tema)
);

create table if not exists public.ajustes (
  id uuid primary key default gen_random_uuid(),
  pessoa_id uuid not null references public.pessoas(id) on delete cascade,
  tipo text not null check (tipo in (
    'apelido', 'piada_interna', 'formato', 'assunto',
    'nivel_sarcasmo', 'formalidade', 'nivel_tecnico', 'toque_yandere'
  )),
  texto text,
  valor text,
  origem text not null check (origem in ('conversa', 'manual')),
  criada_em timestamptz not null default now()
);
create index if not exists idx_ajustes_pessoa on public.ajustes (pessoa_id);

create table if not exists public.notas (
  id uuid primary key default gen_random_uuid(),
  caminho text not null unique,
  titulo text not null,
  tags text[] not null default '{}',
  hash text not null,
  atualizada_em timestamptz not null default now()
);

create table if not exists public.trechos (
  id bigserial primary key,
  nota_id uuid not null references public.notas(id) on delete cascade,
  ordem int not null,
  secao text not null,
  texto text not null,
  busca tsvector generated always as (
    to_tsvector(
      'portuguese',
      public.sera_unaccent(coalesce(secao, '') || ' ' || coalesce(texto, ''))
    )
  ) stored
);
create index if not exists idx_trechos_busca on public.trechos using gin (busca);
create index if not exists idx_trechos_nota on public.trechos (nota_id, ordem);

create table if not exists public.uso_llm (
  id bigserial primary key,
  pessoa_id uuid not null references public.pessoas(id) on delete cascade,
  modelo text not null,
  prompt_tokens int,
  completion_tokens int,
  total_tokens int,
  criada_em timestamptz not null default now()
);
create index if not exists idx_uso_llm_pessoa on public.uso_llm (pessoa_id, criada_em desc);

-- Busca da RAG fase 1. Devolve os trechos já ranqueados.
create or replace function public.buscar_trechos(consulta text, limite int default 3)
returns table (nota text, secao text, texto text)
language sql
stable
as $$
  select n.titulo, t.secao, t.texto
  from public.trechos t
  join public.notas n on n.id = t.nota_id,
       websearch_to_tsquery(
         'portuguese',
         public.sera_unaccent(coalesce(consulta, ''))
       ) q
  where t.busca @@ q
  order by ts_rank(t.busca, q) desc, n.titulo, t.ordem
  limit greatest(coalesce(limite, 3), 0)
$$;

grant usage on schema public to anon, authenticated;
grant select, insert, update, delete on all tables in schema public to authenticated;
grant usage, select on all sequences in schema public to authenticated;
grant execute on function public.buscar_trechos(text, int) to authenticated;

-- RLS: nenhuma tabela fica sem policy.
alter table public.pessoas enable row level security;
drop policy if exists pessoas_propria on public.pessoas;
create policy pessoas_propria on public.pessoas
  for all to authenticated
  using (id = auth.uid())
  with check (id = auth.uid());

alter table public.conversas enable row level security;
drop policy if exists conversa_propria on public.conversas;
create policy conversa_propria on public.conversas
  for all to authenticated
  using (pessoa_id = auth.uid())
  with check (pessoa_id = auth.uid());

alter table public.mensagens enable row level security;
drop policy if exists mensagem_propria on public.mensagens;
create policy mensagem_propria on public.mensagens
  for all to authenticated
  using (exists (
    select 1 from public.conversas c
    where c.id = conversa_id and c.pessoa_id = auth.uid()
  ))
  with check (exists (
    select 1 from public.conversas c
    where c.id = conversa_id and c.pessoa_id = auth.uid()
  ));

alter table public.memorias enable row level security;
drop policy if exists memoria_propria on public.memorias;
create policy memoria_propria on public.memorias
  for all to authenticated
  using (pessoa_id = auth.uid())
  with check (pessoa_id = auth.uid());

alter table public.nao_mencionar enable row level security;
drop policy if exists tema_proprio on public.nao_mencionar;
create policy tema_proprio on public.nao_mencionar
  for all to authenticated
  using (pessoa_id = auth.uid())
  with check (pessoa_id = auth.uid());

alter table public.ajustes enable row level security;
drop policy if exists ajuste_proprio on public.ajustes;
create policy ajuste_proprio on public.ajustes
  for all to authenticated
  using (pessoa_id = auth.uid())
  with check (pessoa_id = auth.uid());

alter table public.uso_llm enable row level security;
drop policy if exists uso_proprio on public.uso_llm;
create policy uso_proprio on public.uso_llm
  for all to authenticated
  using (pessoa_id = auth.uid())
  with check (pessoa_id = auth.uid());

-- Notas e trechos são conteúdo global: todo autenticado lê, só service_role escreve.
alter table public.notas enable row level security;
drop policy if exists notas_leitura on public.notas;
create policy notas_leitura on public.notas
  for select to authenticated
  using (true);

alter table public.trechos enable row level security;
drop policy if exists trechos_leitura on public.trechos;
create policy trechos_leitura on public.trechos
  for select to authenticated
  using (true);
