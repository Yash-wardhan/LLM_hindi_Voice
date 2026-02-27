"""
UUIDv7 generator
────────────────
UUIDv7 encodes a Unix timestamp (ms precision) in the high bits so that
lexicographic sort order equals chronological order — ideal as a user/session key.

Layout (RFC 9562):
  ┌──────────────────── 48 bits ─── unix_ts_ms ───────────────────────┐
  │                                                                    │
  xxxx xxxx  xxxx xxxx  xxxx xxxx  xxxx xxxx  xxxx xxxx  xxxx xxxx
  xxxx                   ← 4 bits version = 0111 (7)
       xxxx xxxx xxxx    ← 12 bits rand_a
  xx                     ← 2 bits variant = 10
    xx xxxx xxxx xxxx  xxxx xxxx  xxxx xxxx  xxxx xxxx  xxxx xxxx
                                                   ← 62 bits rand_b
"""

import os
import time
import uuid


def uuid7() -> str:
    """Return a new UUIDv7 string (lowercase, xxxxxxxx-xxxx-7xxx-yxxx-xxxxxxxxxxxx)."""
    # 48-bit millisecond timestamp
    ms = int(time.time() * 1000) & 0xFFFF_FFFF_FFFF

    # 74 random bits split into rand_a (12 bits) and rand_b (62 bits)
    rand = int.from_bytes(os.urandom(10), "big")
    rand_a = (rand >> 62) & 0xFFF          # top 12 bits
    rand_b = rand & 0x3FFF_FFFF_FFFF_FFFF  # bottom 62 bits

    # Assemble the 128-bit integer
    # [47:0] ts_ms | [51:48] version=7 | [63:52] rand_a | [65:64] variant=0b10 | [127:66] rand_b
    hi = (ms << 16) | (0x7 << 12) | rand_a
    lo = (0b10 << 62) | rand_b

    uid = uuid.UUID(int=(hi << 64) | lo)
    return str(uid)
