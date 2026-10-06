"""Enforce lineage immutability even for direct SQL writes."""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE FUNCTION langai_immutable_lineage() RETURNS trigger AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Lineage records are immutable'; END IF;
      IF TG_TABLE_NAME = 'datasets' THEN
        RAISE EXCEPTION 'Dataset snapshots are immutable';
      ELSIF TG_TABLE_NAME = 'training_runs' AND
        (to_jsonb(NEW) - ARRAY['status','started_at','completed_at','heartbeat_at','metrics','artifact_location','cancel_requested','error'])
        IS DISTINCT FROM
        (to_jsonb(OLD) - ARRAY['status','started_at','completed_at','heartbeat_at','metrics','artifact_location','cancel_requested','error']) THEN
        RAISE EXCEPTION 'Training run configuration is immutable';
      ELSIF TG_TABLE_NAME = 'models' AND
        (to_jsonb(NEW) - ARRAY['status','approved_by']) IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['status','approved_by']) THEN
        RAISE EXCEPTION 'Model provenance and evaluations are immutable';
      ELSIF TG_TABLE_NAME IN ('audit_events','run_events') THEN
        RAISE EXCEPTION 'Events are append-only';
      END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql""")
    for table in ["datasets", "training_runs", "models", "audit_events", "run_events"]:
        op.execute(
            f"CREATE TRIGGER immutable_lineage BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION langai_immutable_lineage()"
        )


def downgrade():
    for table in ["datasets", "training_runs", "models", "audit_events", "run_events"]:
        op.execute(f"DROP TRIGGER immutable_lineage ON {table}")
    op.execute("DROP FUNCTION langai_immutable_lineage()")
