-- Extensões do agendador de notificações.
-- O pg_cron roda a verificação a cada minuto e o pg_net faz a chamada HTTP
-- assíncrona para a API da Sera.

create extension if not exists pg_cron;
create extension if not exists pg_net;
