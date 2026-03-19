"""Centralized configuration — reads from env / .env"""
import os

API_KEY = os.getenv("KIMI_API_KEY", "")
MODEL = os.getenv("KIMI_MODEL", "kimi-for-coding")
API_URL = "https://api.kimi.com/coding/v1/chat/completions"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")  # comma-separated or *
RATE_LIMIT = int(os.getenv("RATE_LIMIT", "10"))  # per minute per IP
CODE_MAX_LEN = int(os.getenv("CODE_MAX_LEN", "50000"))
VERSION = "2.0.0"
