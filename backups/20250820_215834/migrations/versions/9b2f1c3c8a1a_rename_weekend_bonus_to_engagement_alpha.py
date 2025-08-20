"""
Rename weekend_bonus_multiplier to engagement_weight_alpha

Revision ID: 9b2f1c3c8a1a
Revises: 673f29da221c
Create Date: 2025-08-19 16:33:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '9b2f1c3c8a1a'
down_revision = '673f29da221c'
branch_labels = None
depends_on = None

def upgrade():
    # Use batch operations for SQLite compatibility
    with op.batch_alter_table('evaluation_system_config', schema=None) as batch_op:
        # If the old column exists, rename it; otherwise create the new column if missing
        try:
            batch_op.alter_column(
                'weekend_bonus_multiplier',
                new_column_name='engagement_weight_alpha',
                existing_type=sa.Float(),
                existing_nullable=True,
            )
        except Exception:
            # In case the column was already renamed manually, ensure it exists
            batch_op.add_column(sa.Column('engagement_weight_alpha', sa.Float(), nullable=True))
    # Set default-like value for existing rows that still have the old default 1.5
    try:
        op.execute(
            "UPDATE evaluation_system_config SET engagement_weight_alpha = 0.667 "
            "WHERE engagement_weight_alpha IS NULL OR engagement_weight_alpha = 1.5"
        )
    except Exception:
        pass


def downgrade():
    with op.batch_alter_table('evaluation_system_config', schema=None) as batch_op:
        try:
            batch_op.alter_column(
                'engagement_weight_alpha',
                new_column_name='weekend_bonus_multiplier',
                existing_type=sa.Float(),
                existing_nullable=True,
            )
        except Exception:
            batch_op.add_column(sa.Column('weekend_bonus_multiplier', sa.Float(), nullable=True))
