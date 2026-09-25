"""seed providers

Revision ID: 3be4ff79b8e3
Revises: 1f4b999c64d9
Create Date: 2026-09-25 17:37:53.051568

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3be4ff79b8e3'
down_revision: Union[str, None] = '1f4b999c64d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade():
    op.execute("""
        INSERT INTO providers (id, name, base_url, priority, cost_per_1k_input, cost_per_1k_output, is_active)
        VALUES
            (gen_random_uuid(), 'groq', 'https://api.groq.com/openai/v1', 1, 0, 0, true),
            (gen_random_uuid(), 'gemini', 'https://generativelanguage.googleapis.com', 2, 0, 0, true),
            (gen_random_uuid(), 'openrouter', 'https://openrouter.ai/api/v1', 3, 0, 0, true)
        ON CONFLICT (name) DO NOTHING;
    """)


def downgrade():
    op.execute("""
        DELETE FROM providers
        WHERE name IN ('groq', 'gemini', 'openrouter');
    """)
