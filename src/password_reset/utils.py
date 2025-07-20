# src/password_reset/utils.py
import secrets


def generate_otp() -> str:
    return f"{secrets.randbelow(1000000):06d}"
