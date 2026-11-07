-- Agendador confiável para lembretes e texto diário.
--
-- O cron do GitHub não é pontual no plano free e o Render dorme após alguns
-- minutos sem requisições. O pg_cron roda a cada minuto e só acorda a API
-- quando existe algo vencido para entregar.
--
-- O segredo do endpoint fica no Vault (nome: notificacoes_segredo) e nunca
-- é gravado nesta migração. Para configurá-lo, use o procedimento descrito
-- em docs/agenda-e-notificacoes.md.

create extension if not exists pg_cron;
create extension if not exists pg_net;

create or replace function public.sera_notificacoes_pendentes()
returns boolean
language sql
security definer
set search_path = ''
as $$
  select
    exists (
      select 1
      from public.compromissos c
      where c.lembrete_enviado_em is null
        and c.lembrete_em <= now()
        and c.fim >= now()
    )
    or exists (
      select 1
      from public.texto_diario_assinaturas a
      where a.ativo
        and (now() at time zone a.fuso)::date >
            coalesce(a.ultimo_envio_dia, '-infinity'::date)
        and (now() at time zone a.fuso)::time >= a.hora::time
    );
$$;

comment on function public.sera_notificacoes_pendentes() is
  'Indica se há lembrete ou texto diário vencido para o agendador acordar a API.';

create or replace function public.sera_disparar_notificacoes()
returns bigint
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_segredo text;
  v_pedido bigint;
begin
  if not public.sera_notificacoes_pendentes() then
    return null;
  end if;

  select decrypted_secret
    into v_segredo
    from vault.decrypted_secrets
   where name = 'notificacoes_segredo'
   limit 1;

  if v_segredo is null or v_segredo = '' then
    raise exception 'segredo de notificações ausente no Vault';
  end if;

  select net.http_post(
    url := 'https://sera-api-8n2k.onrender.com/notificacoes/disparar',
    body := '{}'::jsonb,
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'X-Sera-Segredo', v_segredo
    ),
    timeout_milliseconds := 60000
  ) into v_pedido;

  return v_pedido;
end;
$$;

comment on function public.sera_disparar_notificacoes() is
  'Acorda a API da Sera quando há notificações vencidas.';

revoke all on function public.sera_notificacoes_pendentes()
  from public, anon, authenticated;
revoke all on function public.sera_disparar_notificacoes()
  from public, anon, authenticated;

grant execute on function public.sera_notificacoes_pendentes()
  to service_role;
grant execute on function public.sera_disparar_notificacoes()
  to service_role;

select cron.schedule(
  'sera-notificacoes',
  '* * * * *',
  'select public.sera_disparar_notificacoes()'
);
