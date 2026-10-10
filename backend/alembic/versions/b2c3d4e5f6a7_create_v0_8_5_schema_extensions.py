"""create_v0_8_5_schema_extensions

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema with V0.7/V0.8/V0.8.5 extensions in an idempotent manner."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    # 1. Sources schema extensions
    sources_cols = {c["name"] for c in insp.get_columns("sources")} if "sources" in existing_tables else set()
    with op.batch_alter_table('sources', schema=None) as batch_op:
        if "is_primary" not in sources_cols:
            batch_op.add_column(sa.Column('is_primary', sa.Boolean(), nullable=False, server_default=sa.text('false')))
        if "region" not in sources_cols:
            batch_op.add_column(sa.Column('region', sa.String(length=64), nullable=True, server_default=sa.text("'Global'")))
            batch_op.create_index(batch_op.f('ix_sources_region'), ['region'], unique=False)
        if "country" not in sources_cols:
            batch_op.add_column(sa.Column('country', sa.String(length=8), nullable=True, server_default=sa.text("'XX'")))
            batch_op.create_index(batch_op.f('ix_sources_country'), ['country'], unique=False)
        if "domain" not in sources_cols:
            batch_op.add_column(sa.Column('domain', sa.String(length=128), nullable=True, server_default=sa.text("'General'")))
            batch_op.create_index(batch_op.f('ix_sources_domain'), ['domain'], unique=False)
        if "last_successful_fetch_at" not in sources_cols:
            batch_op.add_column(sa.Column('last_successful_fetch_at', sa.DateTime(timezone=True), nullable=True))
        if "last_attempted_fetch_at" not in sources_cols:
            batch_op.add_column(sa.Column('last_attempted_fetch_at', sa.DateTime(timezone=True), nullable=True))
        if "last_error_message" not in sources_cols:
            batch_op.add_column(sa.Column('last_error_message', sa.String(length=2048), nullable=True))
        if "consecutive_failures" not in sources_cols:
            batch_op.add_column(sa.Column('consecutive_failures', sa.Integer(), nullable=False, server_default=sa.text('0')))
        if "freshness_status" not in sources_cols:
            batch_op.add_column(sa.Column('freshness_status', sa.String(length=20), nullable=False, server_default=sa.text("'UNKNOWN'")))
            batch_op.create_index(batch_op.f('ix_sources_freshness_status'), ['freshness_status'], unique=False)

    # 2. Economic Indicators schema extensions
    ei_cols = {c["name"] for c in insp.get_columns("economic_indicators")} if "economic_indicators" in existing_tables else set()
    with op.batch_alter_table('economic_indicators', schema=None) as batch_op:
        if "symbol" not in ei_cols:
            batch_op.add_column(sa.Column('symbol', sa.String(length=64), nullable=True))
            batch_op.create_index(batch_op.f('ix_economic_indicators_symbol'), ['symbol'], unique=False)

    # 3. Economic Observations schema extensions
    eo_cols = {c["name"] for c in insp.get_columns("economic_observations")} if "economic_observations" in existing_tables else set()
    with op.batch_alter_table('economic_observations', schema=None) as batch_op:
        if "period_start" not in eo_cols:
            batch_op.add_column(sa.Column('period_start', sa.DateTime(timezone=True), nullable=True))
        if "period_end" not in eo_cols:
            batch_op.add_column(sa.Column('period_end', sa.DateTime(timezone=True), nullable=True))
        if "release_timestamp" not in eo_cols:
            batch_op.add_column(sa.Column('release_timestamp', sa.DateTime(timezone=True), nullable=True))
        if "is_revision" not in eo_cols:
            batch_op.add_column(sa.Column('is_revision', sa.Boolean(), nullable=False, server_default=sa.text('false')))
        if "revision_number" not in eo_cols:
            batch_op.add_column(sa.Column('revision_number', sa.Integer(), nullable=False, server_default=sa.text('0')))
        batch_op.alter_column('document_id', existing_type=sa.Uuid(), nullable=True)

    # 4. Ingestion Runs Table (V0.8 Ingestion provenance & audit telemetry)
    if "ingestion_runs" not in existing_tables:
        op.create_table(
            'ingestion_runs',
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('source_id', sa.Uuid(), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default=sa.text("'RUNNING'")),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('documents_discovered', sa.Integer(), nullable=False, server_default=sa.text('0')),
            sa.Column('documents_inserted', sa.Integer(), nullable=False, server_default=sa.text('0')),
            sa.Column('duplicates_skipped', sa.Integer(), nullable=False, server_default=sa.text('0')),
            sa.Column('failures_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('processing_stats', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        with op.batch_alter_table('ingestion_runs', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_ingestion_runs_source_id'), ['source_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_ingestion_runs_status'), ['status'], unique=False)
            batch_op.create_index(batch_op.f('ix_ingestion_runs_started_at'), ['started_at'], unique=False)
            batch_op.create_index('ix_ingestion_runs_source_started', ['source_id', 'started_at'], unique=False)

    # 5. Entity Relationships Table (V0.7 Knowledge graph verified links)
    if "entity_relationships" not in existing_tables:
        op.create_table(
            'entity_relationships',
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('source_entity_id', sa.Uuid(), nullable=False),
            sa.Column('target_entity_id', sa.Uuid(), nullable=False),
            sa.Column('relationship_type', sa.String(length=64), nullable=False),
            sa.Column('confidence', sa.Float(), nullable=False),
            sa.Column('source_document_id', sa.Uuid(), nullable=True),
            sa.Column('source_event_id', sa.Uuid(), nullable=True),
            sa.Column('extraction_method', sa.String(length=64), nullable=False, server_default=sa.text("'rule_based_v0.7'")),
            sa.Column('extractor_version', sa.String(length=32), nullable=False, server_default=sa.text("'v0.7.0'")),
            sa.Column('evidence', sa.Text(), nullable=False),
            sa.Column('metadata', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['source_entity_id'], ['entities.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['target_entity_id'], ['entities.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['source_document_id'], ['documents.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['source_event_id'], ['extracted_events.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('source_entity_id', 'target_entity_id', 'relationship_type', name='uq_entity_relationship_source_target_type'),
        )
        with op.batch_alter_table('entity_relationships', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_entity_relationships_source_entity_id'), ['source_entity_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_entity_relationships_target_entity_id'), ['target_entity_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_entity_relationships_relationship_type'), ['relationship_type'], unique=False)
            batch_op.create_index(batch_op.f('ix_entity_relationships_source_document_id'), ['source_document_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_entity_relationships_source_event_id'), ['source_event_id'], unique=False)
            batch_op.create_index('ix_entity_relationships_source_type', ['source_entity_id', 'relationship_type'], unique=False)
            batch_op.create_index('ix_entity_relationships_target_type', ['target_entity_id', 'relationship_type'], unique=False)

    # 6. Alerts Table (V0.8 Deterministic intelligence alerts)
    if "alerts" not in existing_tables:
        op.create_table(
            'alerts',
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('trigger_type', sa.String(length=64), nullable=False),
            sa.Column('alert_title', sa.String(length=256), nullable=False),
            sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
            sa.Column('importance', sa.Float(), nullable=False, server_default=sa.text('0.5')),
            sa.Column('confidence', sa.Float(), nullable=False, server_default=sa.text('0.8')),
            sa.Column('affected_entity_ids', sa.JSON(), nullable=False),
            sa.Column('affected_event_id', sa.Uuid(), nullable=True),
            sa.Column('affected_source_id', sa.Uuid(), nullable=True),
            sa.Column('evidence', sa.Text(), nullable=False),
            sa.Column('explanation', sa.Text(), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default=sa.text("'ACTIVE'")),
            sa.Column('metadata', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['affected_event_id'], ['extracted_events.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['affected_source_id'], ['sources.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        with op.batch_alter_table('alerts', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_alerts_trigger_type'), ['trigger_type'], unique=False)
            batch_op.create_index(batch_op.f('ix_alerts_timestamp'), ['timestamp'], unique=False)
            batch_op.create_index(batch_op.f('ix_alerts_importance'), ['importance'], unique=False)
            batch_op.create_index(batch_op.f('ix_alerts_status'), ['status'], unique=False)
            batch_op.create_index(batch_op.f('ix_alerts_affected_event_id'), ['affected_event_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_alerts_affected_source_id'), ['affected_source_id'], unique=False)
            batch_op.create_index('ix_alerts_trigger_status', ['trigger_type', 'status'], unique=False)
            batch_op.create_index('ix_alerts_event_trigger', ['affected_event_id', 'trigger_type'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    if "alerts" in existing_tables:
        op.drop_table('alerts')
    if "entity_relationships" in existing_tables:
        op.drop_table('entity_relationships')
    if "ingestion_runs" in existing_tables:
        op.drop_table('ingestion_runs')

    if "economic_observations" in existing_tables:
        with op.batch_alter_table('economic_observations', schema=None) as batch_op:
            batch_op.alter_column('document_id', existing_type=sa.Uuid(), nullable=False)
            batch_op.drop_column('revision_number')
            batch_op.drop_column('is_revision')
            batch_op.drop_column('release_timestamp')
            batch_op.drop_column('period_end')
            batch_op.drop_column('period_start')

    if "economic_indicators" in existing_tables:
        with op.batch_alter_table('economic_indicators', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_economic_indicators_symbol'))
            batch_op.drop_column('symbol')

    if "sources" in existing_tables:
        with op.batch_alter_table('sources', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_sources_freshness_status'))
            batch_op.drop_column('freshness_status')
            batch_op.drop_column('consecutive_failures')
            batch_op.drop_column('last_error_message')
            batch_op.drop_column('last_attempted_fetch_at')
            batch_op.drop_column('last_successful_fetch_at')
            batch_op.drop_index(batch_op.f('ix_sources_domain'))
            batch_op.drop_index(batch_op.f('ix_sources_country'))
            batch_op.drop_index(batch_op.f('ix_sources_region'))
            batch_op.drop_column('domain')
            batch_op.drop_column('country')
            batch_op.drop_column('region')
            batch_op.drop_column('is_primary')
