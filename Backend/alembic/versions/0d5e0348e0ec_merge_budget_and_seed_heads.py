"""merge budget and seed heads

Revision ID: 0d5e0348e0ec
Revises: 3be4ff79b8e3, 4d12b7a9c301
Create Date: 2026-09-28 17:37:20.331674

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0d5e0348e0ec'
down_revision: Union[str, None] = ('3be4ff79b8e3', '4d12b7a9c301')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
