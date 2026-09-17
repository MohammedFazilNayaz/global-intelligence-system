"""create_v0_5_economic_tables

Revision ID: 7a8e9d123456
Revises: 6967998b2719
Create Date: 2026-09-10 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a8e9d123456'
down_revision: Union[str, Sequence[str], None] = '6967998b2719'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'economic_indicators',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('canonical_name', sa.String(length=256), nullable=False),
        sa.Column('normalized_name', sa.String(length=256), nullable=False),
        sa.Column('indicator_type', sa.String(length=64), nullable=False),
        sa.Column('economic_domain', sa.String(length=64), nullable=False),
        sa.Column('country_entity_id', sa.Uuid(), nullable=True),
        sa.Column('default_unit', sa.String(length=32), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['country_entity_id'], ['entities.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('indicator_type', 'country_entity_id', name='uq_indicator_type_country'),
    )
    with op.batch_alter_table('economic_indicators', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_economic_indicators_canonical_name'), ['canonical_name'], unique=False)
        batch_op.create_index(batch_op.f('ix_economic_indicators_normalized_name'), ['normalized_name'], unique=False)
        batch_op.create_index(batch_op.f('ix_economic_indicators_indicator_type'), ['indicator_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_economic_indicators_economic_domain'), ['economic_domain'], unique=False)
        batch_op.create_index(batch_op.f('ix_economic_indicators_country_entity_id'), ['country_entity_id'], unique=False)
        batch_op.create_index('ix_economic_indicators_domain_type', ['economic_domain', 'indicator_type'], unique=False)

    op.create_table(
        'economic_observations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('indicator_id', sa.Uuid(), nullable=False),
        sa.Column('event_id', sa.Uuid(), nullable=True),
        sa.Column('document_id', sa.Uuid(), nullable=False),
        sa.Column('observation_period', sa.String(length=64), nullable=True),
        sa.Column('observation_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reported_value', sa.Float(), nullable=True),
        sa.Column('reported_unit', sa.String(length=32), nullable=True),
        sa.Column('previous_value', sa.Float(), nullable=True),
        sa.Column('expected_value', sa.Float(), nullable=True),
        sa.Column('revised_value', sa.Float(), nullable=True),
        sa.Column('direction', sa.String(length=32), nullable=True),
        sa.Column('change_value', sa.Float(), nullable=True),
        sa.Column('change_percent', sa.Float(), nullable=True),
        sa.Column('calculation_method', sa.String(length=64), nullable=True),
        sa.Column('economic_relevance', sa.Float(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['event_id'], ['extracted_events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['indicator_id'], ['economic_indicators.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('economic_observations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_economic_observations_indicator_id'), ['indicator_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_economic_observations_event_id'), ['event_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_economic_observations_document_id'), ['document_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_economic_observations_observation_period'), ['observation_period'], unique=False)
        batch_op.create_index(batch_op.f('ix_economic_observations_direction'), ['direction'], unique=False)
        batch_op.create_index(batch_op.f('ix_economic_observations_economic_relevance'), ['economic_relevance'], unique=False)
        batch_op.create_index('ix_economic_obs_indicator_period', ['indicator_id', 'observation_period'], unique=False)
        batch_op.create_index('ix_economic_obs_doc_indicator', ['document_id', 'indicator_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('economic_observations')
    op.drop_table('economic_indicators')
