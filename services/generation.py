"""Public generation API; existing engine and single-request lock are preserved."""
from services.chapter_generation import generate, registry, generation_lock
