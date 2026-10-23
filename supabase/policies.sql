-- Run in the Supabase SQL editor.
-- Anyone with the publishable key can read; only signed-in users can write or call the RPCs.

do $$
declare
    table_name text;
begin
    foreach table_name in array array['preset_toys', 'toy_bom', 'tasks', 'workers', 'warehouse_parts'] loop
        execute format('alter table public.%I enable row level security', table_name);

        execute format('drop policy if exists "Public read" on public.%I', table_name);
        execute format('create policy "Public read" on public.%I for select to anon, authenticated using (true)', table_name);

        execute format('drop policy if exists "Authenticated write" on public.%I', table_name);
        execute format('create policy "Authenticated write" on public.%I for all to authenticated using (true) with check (true)', table_name);
    end loop;
end $$;

do $$
declare
    fn regprocedure;
begin
    for fn in
        select oid::regprocedure from pg_proc
        where pronamespace = 'public'::regnamespace
          and proname in ('record_return', 'complete_task_and_deduct_inventory')
    loop
        execute format('revoke execute on function %s from public, anon', fn);
        execute format('grant execute on function %s to authenticated', fn);
    end loop;
end $$;
