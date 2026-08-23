"""Per-tenant integration credential encryption at rest, using pgcrypto's
symmetric functions (extension already enabled by alembic 0001) keyed by
INTEGRATION_CREDENTIALS_KEY — a single app-level secret, not a per-tenant
key, matching PHASE_2_PLAN.md §3's design note. Encryption/decryption run
as a database round trip rather than in-process crypto so the key never
needs a Python crypto dependency and the ciphertext format stays whatever
pgcrypto produces (portable across any tool that can call
pgp_sym_decrypt with the same key).
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings


async def encrypt_token(db: AsyncSession, plaintext: str) -> bytes:
    result = await db.execute(
        select(func.pgp_sym_encrypt(plaintext, get_settings().integration_credentials_key))
    )
    return result.scalar_one()


async def decrypt_token(db: AsyncSession, ciphertext: bytes) -> str:
    result = await db.execute(
        select(func.pgp_sym_decrypt(ciphertext, get_settings().integration_credentials_key))
    )
    return result.scalar_one()
