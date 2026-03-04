"""Add security tables, RLS policies, and pgcrypto

Revision ID: e1a2b3c4d5f6
Revises: d4b7f2a91e3c
Create Date: 2026-03-04 11:00:00.000000

Creates:
  - users, families, family_memberships, devices, pairing_tokens,
    refresh_tokens, locations_raw tables
  - Enables pgcrypto extension
  - Adds family_id column to zones
  - Creates kin_app database role with RLS policies on all sensitive tables
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = 'e1a2b3c4d5f6'
down_revision: Union[str, None] = '5b76f9c889a9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extensions ────────────────────────────────────────
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')

    # ── Users table ───────────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # ── Families table ────────────────────────────────────
    op.create_table(
        'families',
        sa.Column('id', UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── Family Memberships table ──────────────────────────
    op.create_table(
        'family_memberships',
        sa.Column('id', UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.ForeignKeyConstraint(['family_id'], ['families.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('family_id', 'user_id', name='uq_family_user'),
    )

    # ── Devices table ─────────────────────────────────────
    op.create_table(
        'devices',
        sa.Column('id', UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('device_identifier', sa.String(255), nullable=False),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('mqtt_username', sa.String(255), nullable=True),
        sa.Column('mqtt_password_hash', sa.String(255), nullable=True),
        sa.Column('paired_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()')),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.ForeignKeyConstraint(['family_id'], ['families.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_devices_device_identifier', 'devices',
                    ['device_identifier'], unique=True)

    # ── Pairing Tokens table ──────────────────────────────
    op.create_table(
        'pairing_tokens',
        sa.Column('id', UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('token', sa.String(64), nullable=False),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('device_id', UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['family_id'], ['families.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_pairing_tokens_token', 'pairing_tokens',
                    ['token'], unique=True)

    # ── Refresh Tokens table ──────────────────────────────
    op.create_table(
        'refresh_tokens',
        sa.Column('id', UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('jti', sa.String(64), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('device_id', UUID(as_uuid=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_refresh_tokens_jti', 'refresh_tokens',
                    ['jti'], unique=True)

    # ── Locations Raw (encrypted coordinates) ─────────────
    op.create_table(
        'locations_raw',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('device_id', sa.String(), nullable=False),
        sa.Column('lat_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('lng_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('altitude', sa.Float(), nullable=True),
        sa.Column('speed', sa.Float(), nullable=True),
        sa.Column('battery_level', sa.Float(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True),
                  server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_locations_raw_device_id', 'locations_raw',
                    ['device_id'])

    # ── Add family_id to zones ────────────────────────────
    op.add_column('zones',
                  sa.Column('family_id', UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_zones_family_id', 'zones', 'families',
        ['family_id'], ['id'],
    )

    # ── RLS Policies ──────────────────────────────────────
    # Note: RLS policies use app.current_family_id session variable.
    # For the MVP, we apply them but they only activate for the kin_app role.
    # The migration role (kinuser) bypasses RLS as the table owner.

    # Create the kin_app role if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kin_app') THEN
                CREATE ROLE kin_app LOGIN PASSWORD 'kin_app_secure_password';
            END IF;
        END
        $$;
    """)

    # Grant permissions to kin_app
    op.execute('GRANT USAGE ON SCHEMA public TO kin_app')
    op.execute('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO kin_app')
    op.execute('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO kin_app')
    op.execute('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO kin_app')
    op.execute('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO kin_app')

    # -- RLS on location_history --
    op.execute('ALTER TABLE location_history ENABLE ROW LEVEL SECURITY')
    op.execute("""
        CREATE POLICY family_locations ON location_history
        FOR ALL TO kin_app
        USING (
            device_id IN (
                SELECT device_identifier FROM devices
                WHERE family_id = current_setting('app.current_family_id')::uuid
            )
        )
    """)

    # -- RLS on matched_routes --
    op.execute('ALTER TABLE matched_routes ENABLE ROW LEVEL SECURITY')
    op.execute("""
        CREATE POLICY family_routes ON matched_routes
        FOR ALL TO kin_app
        USING (
            device_id IN (
                SELECT device_identifier FROM devices
                WHERE family_id = current_setting('app.current_family_id')::uuid
            )
        )
    """)

    # -- RLS on current_status --
    op.execute('ALTER TABLE current_status ENABLE ROW LEVEL SECURITY')
    op.execute("""
        CREATE POLICY family_status ON current_status
        FOR ALL TO kin_app
        USING (
            device_id IN (
                SELECT device_identifier FROM devices
                WHERE family_id = current_setting('app.current_family_id')::uuid
            )
        )
    """)

    # -- RLS on locations_raw --
    op.execute('ALTER TABLE locations_raw ENABLE ROW LEVEL SECURITY')
    op.execute("""
        CREATE POLICY family_raw_locations ON locations_raw
        FOR ALL TO kin_app
        USING (
            device_id IN (
                SELECT device_identifier FROM devices
                WHERE family_id = current_setting('app.current_family_id')::uuid
            )
        )
    """)

    # -- RLS on geofence_events --
    op.execute('ALTER TABLE geofence_events ENABLE ROW LEVEL SECURITY')
    op.execute("""
        CREATE POLICY family_events ON geofence_events
        FOR ALL TO kin_app
        USING (
            device_id IN (
                SELECT device_identifier FROM devices
                WHERE family_id = current_setting('app.current_family_id')::uuid
            )
        )
    """)

    # -- RLS on zones (uses direct family_id column) --
    op.execute('ALTER TABLE zones ENABLE ROW LEVEL SECURITY')
    op.execute("""
        CREATE POLICY family_zones ON zones
        FOR ALL TO kin_app
        USING (
            family_id = current_setting('app.current_family_id')::uuid
            OR family_id IS NULL
        )
    """)


def downgrade() -> None:
    # Drop RLS policies
    op.execute('DROP POLICY IF EXISTS family_zones ON zones')
    op.execute('ALTER TABLE zones DISABLE ROW LEVEL SECURITY')
    op.execute('DROP POLICY IF EXISTS family_events ON geofence_events')
    op.execute('ALTER TABLE geofence_events DISABLE ROW LEVEL SECURITY')
    op.execute('DROP POLICY IF EXISTS family_raw_locations ON locations_raw')
    op.execute('ALTER TABLE locations_raw DISABLE ROW LEVEL SECURITY')
    op.execute('DROP POLICY IF EXISTS family_status ON current_status')
    op.execute('ALTER TABLE current_status DISABLE ROW LEVEL SECURITY')
    op.execute('DROP POLICY IF EXISTS family_routes ON matched_routes')
    op.execute('ALTER TABLE matched_routes DISABLE ROW LEVEL SECURITY')
    op.execute('DROP POLICY IF EXISTS family_locations ON location_history')
    op.execute('ALTER TABLE location_history DISABLE ROW LEVEL SECURITY')

    # Drop FK on zones
    op.drop_constraint('fk_zones_family_id', 'zones', type_='foreignkey')
    op.drop_column('zones', 'family_id')

    # Drop tables in reverse dependency order
    op.drop_index('ix_locations_raw_device_id', table_name='locations_raw')
    op.drop_table('locations_raw')
    op.drop_index('ix_refresh_tokens_jti', table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
    op.drop_index('ix_pairing_tokens_token', table_name='pairing_tokens')
    op.drop_table('pairing_tokens')
    op.drop_index('ix_devices_device_identifier', table_name='devices')
    op.drop_table('devices')
    op.drop_table('family_memberships')
    op.drop_table('families')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')

    # Drop kin_app role
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kin_app') THEN
                REVOKE ALL ON ALL TABLES IN SCHEMA public FROM kin_app;
                REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM kin_app;
                REVOKE USAGE ON SCHEMA public FROM kin_app;
                DROP ROLE kin_app;
            END IF;
        END
        $$;
    """)
