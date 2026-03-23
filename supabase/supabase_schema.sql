-- ══════════════════════════════════════════════════════════
--  Supabase Schema — AuSignal
--  วางใน Supabase SQL Editor แล้วกด Run
-- ══════════════════════════════════════════════════════════

-- 1) Profiles (ต่อจาก auth.users ของ Supabase)
create table public.profiles (
  id       uuid primary key references auth.users(id) on delete cascade,
  email    text unique not null,
  name     text default '',
  role     text default 'user' check (role in ('user','premium','admin')),
  plan     text default 'free' check (plan in ('free','pro','enterprise')),
  created_at timestamptz default now()
);

-- 2) Signals (บันทึกทุก signal ที่ AI ส่งออกมา)
create table public.signals (
  id          uuid primary key default gen_random_uuid(),
  symbol      text not null default 'XAU/USD',
  interval    text not null default '1h',
  signal      text not null check (signal in ('BUY','SELL','WAIT')),
  confidence  numeric(5,2),
  price       numeric(10,2),
  sl          numeric(10,2),
  tp          numeric(10,2),
  rsi_14      numeric(6,2),
  adx_14      numeric(6,2),
  result      text check (result in ('win','loss','open','expired')),
  pnl_pct     numeric(8,4),
  created_at  timestamptz default now(),
  closed_at   timestamptz
);

-- 3) Model Logs
create table public.model_logs (
  id          uuid primary key default gen_random_uuid(),
  event       text not null,   -- 'predict', 'retrain', 'error', 'kill_switch'
  message     text,
  metadata    jsonb,
  created_at  timestamptz default now()
);

-- 4) Row Level Security (RLS)
alter table public.profiles enable row level security;
alter table public.signals   enable row level security;
alter table public.model_logs enable row level security;

-- User เห็นแค่ profile ตัวเอง
create policy "own profile" on public.profiles
  for all using (auth.uid() = id);

-- User เห็น signals ได้ถ้า plan = premium หรือ admin
create policy "premium signals" on public.signals
  for select using (
    exists (
      select 1 from public.profiles
      where id = auth.uid() and role in ('premium','admin')
    )
  );

-- Admin เห็น logs ได้
create policy "admin logs" on public.model_logs
  for all using (
    exists (
      select 1 from public.profiles
      where id = auth.uid() and role = 'admin'
    )
  );

-- 5) Auto-create profile หลัง register
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer as $$
begin
  insert into public.profiles (id, email)
  values (new.id, new.email);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- ══════════════════════════════════════════════════════════
--  INDEX สำหรับ query เร็ว
-- ══════════════════════════════════════════════════════════
create index idx_signals_created on public.signals(created_at desc);
create index idx_signals_symbol  on public.signals(symbol);
create index idx_logs_created    on public.model_logs(created_at desc);
