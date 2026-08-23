"""API Key 加密工具。

使用 Fernet 对称加密保护存储的 API Key。
密钥持久化在 data 目录下（首次运行时自动生成），
也可通过 settings.encryption_key 显式指定。
"""

from cryptography.fernet import Fernet

from app.config import settings, DATA_DIR

_KEY_FILE = DATA_DIR / ".inkmaster.key"


def _load_key() -> bytes:
    """获取或生成 Fernet 密钥。优先级：settings > 本地密钥文件 > 自动生成。"""
    if settings.encryption_key:
        return settings.encryption_key.encode("utf-8")

    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes()

    key = Fernet.generate_key()
    _KEY_FILE.write_bytes(key)
    return key


_cipher = Fernet(_load_key())


def encrypt(plaintext: str) -> str:
    """加密明文字符串，空串原样返回。"""
    if not plaintext:
        return ""
    return _cipher.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    """解密。对历史遗留的明文存储做容错（解密失败时原样返回）。"""
    if not token:
        return ""
    try:
        return _cipher.decrypt(token.encode("ascii")).decode("utf-8")
    except Exception:
        return token