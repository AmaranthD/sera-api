-- A busca precisa considerar o título e as tags da nota, como no FTS5 local.
-- Sem isso, procurar por "saúde" não encontra a nota "Saúde" quando o termo
-- aparece só no título.
--
-- A coluna é preenchida por trigger (e não GENERATED) porque o cast de
-- text[] para text não é immutable para o Postgres.

alter table public.notas
  add column if not exists busca tsvector;

create or replace function public.notas_busca_trigger()
returns trigger
language plpgsql
as $$
begin
  new.busca := to_tsvector(
    'portuguese',
    public.sera_unaccent(
      coalesce(new.titulo, '') || ' ' || coalesce(array_to_string(new.tags, ' '), '')
    )
  );
  return new;
end
$$;

drop trigger if exists trg_notas_busca on public.notas;
create trigger trg_notas_busca
  before insert or update of titulo, tags on public.notas
  for each row execute function public.notas_busca_trigger();

update public.notas
set busca = to_tsvector(
  'portuguese',
  public.sera_unaccent(
    coalesce(titulo, '') || ' ' || coalesce(array_to_string(tags, ' '), '')
  )
);

create index if not exists idx_notas_busca on public.notas using gin (busca);

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
  where (t.busca || n.busca) @@ q
  order by ts_rank(t.busca || n.busca, q) desc, n.titulo, t.ordem
  limit greatest(coalesce(limite, 3), 0)
$$;

revoke execute on function public.buscar_trechos(text, int) from public, anon;
grant execute on function public.buscar_trechos(text, int) to authenticated;
