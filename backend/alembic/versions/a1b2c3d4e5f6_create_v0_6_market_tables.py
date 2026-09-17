"""create_v0_6_market_tables

Revision ID: a1b2c3d4e5f6
Revises: 7a8e9d123456
Create Date: 2026-09-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '7a8e9d123456'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. market_assets
    op.create_table(
        'market_assets',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('symbol', sa.String(length=32), nullable=False),
        sa.Column('canonical_name', sa.String(length=128), nullable=False),
        sa.Column('asset_type', sa.String(length=32), nullable=False),
        sa.Column('exchange_venue', sa.String(length=64), nullable=True),
        sa.Column('quote_currency', sa.String(length=16), nullable=True),
        sa.Column('base_currency', sa.String(length=16), nullable=True),
        sa.Column('entity_id', sa.Uuid(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('symbol', name='uq_market_assets_symbol'),
    )
    with op.batch_alter_table('market_assets', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_market_assets_symbol'), ['symbol'], unique=True)
        batch_op.create_index(batch_op.f('ix_market_assets_canonical_name'), ['canonical_name'], unique=False)
        batch_op.create_index(batch_op.f('ix_market_assets_asset_type'), ['asset_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_market_assets_entity_id'), ['entity_id'], unique=False)
        batch_op.create_index('ix_market_assets_type_symbol', ['asset_type', 'symbol'], unique=False)

    # 2. market_observations
    op.create_table(
        'market_observations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('market_asset_id', sa.Uuid(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('open', sa.Float(), nullable=False),
        sa.Column('high', sa.Float(), nullable=False),
        sa.Column('low', sa.Float(), nullable=False),
        sa.Column('close', sa.Float(), nullable=False),
        sa.Column('volume', sa.Float(), nullable=True),
        sa.Column('source', sa.String(length=64), nullable=False),
        sa.Column('interval', sa.String(length=16), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['market_asset_id'], ['market_assets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('market_asset_id', 'interval', 'timestamp', 'source', name='uq_market_obs_asset_interval_ts_source'),
    )
    with op.batch_alter_table('market_observations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_market_observations_market_asset_id'), ['market_asset_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_market_observations_timestamp'), ['timestamp'], unique=False)
        batch_op.create_index(batch_op.f('ix_market_observations_interval'), ['interval'], unique=False)
        batch_op.create_index('ix_market_obs_asset_interval_ts', ['market_asset_id', 'interval', 'timestamp'], unique=False)
        batch_op.create_index('ix_market_obs_asset_ts', ['market_asset_id', 'timestamp'], unique=False)

    # 3. event_market_correlations
    op.create_table(
        'event_market_correlations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('event_id', sa.Uuid(), nullable=False),
        sa.Column('cluster_id', sa.Uuid(), nullable=True),
        sa.Column('market_asset_id', sa.Uuid(), nullable=False),
        sa.Column('window_size', sa.String(length=16), nullable=False),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('pre_event_price', sa.Float(), nullable=True),
        sa.Column('event_price', sa.Float(), nullable=True),
        sa.Column('post_event_price', sa.Float(), nullable=True),
        sa.Column('return_percent', sa.Float(), nullable=True),
        sa.Column('absolute_change', sa.Float(), nullable=True),
        sa.Column('volatility', sa.Float(), nullable=True),
        sa.Column('volume_change', sa.Float(), nullable=True),
        sa.Column('max_excursion', sa.Float(), nullable=True),
        sa.Column('min_excursion', sa.Float(), nullable=True),
        sa.Column('calculated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('methodology', sa.String(length=64), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['cluster_id'], ['event_clusters.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['event_id'], ['extracted_events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['market_asset_id'], ['market_assets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id', 'market_asset_id', 'window_size', name='uq_event_asset_window'),
    )
    with op.batch_alter_table('event_market_correlations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_event_market_correlations_event_id'), ['event_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_event_market_correlations_cluster_id'), ['cluster_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_event_market_correlations_market_asset_id'), ['market_asset_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_event_market_correlations_window_size'), ['window_size'], unique=False)
        batch_op.create_index('ix_corr_event_asset', ['event_id', 'market_asset_id'], unique=False)
        batch_op.create_index('ix_corr_asset_window', ['market_asset_id', 'window_size'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('event_market_correlations')
    op.drop_table('market_observations')
    op.drop_table('market_assets')
