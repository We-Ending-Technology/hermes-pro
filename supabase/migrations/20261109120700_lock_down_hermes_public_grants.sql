-- Hermes data is accessed only by the private backend through its service role.
-- RLS remains enabled; anon/authenticated must not retain SQL privileges such as TRUNCATE.
DO $$
DECLARE item record;
BEGIN
  FOR item IN
    SELECT tablename
    FROM pg_tables
    WHERE schemaname = 'public'
      AND tablename LIKE 'hermes\_%' ESCAPE '\'
  LOOP
    EXECUTE format(
      'REVOKE ALL PRIVILEGES ON TABLE public.%I FROM anon, authenticated',
      item.tablename
    );
    EXECUTE format(
      'GRANT ALL PRIVILEGES ON TABLE public.%I TO service_role',
      item.tablename
    );
  END LOOP;

  FOR item IN
    SELECT sequence_name
    FROM information_schema.sequences
    WHERE sequence_schema = 'public'
      AND sequence_name LIKE 'hermes\_%' ESCAPE '\'
  LOOP
    EXECUTE format(
      'REVOKE ALL PRIVILEGES ON SEQUENCE public.%I FROM anon, authenticated',
      item.sequence_name
    );
    EXECUTE format(
      'GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.%I TO service_role',
      item.sequence_name
    );
  END LOOP;
END $$;

-- Future Hermes tables/sequences created by the normal migration owner must
-- not inherit Supabase's broad default grants to anon/authenticated.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL ON SEQUENCES FROM anon, authenticated;
