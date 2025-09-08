from __future__ import annotations

from enum import Enum


class Platform(str, Enum):
    META = "meta"
    REDDIT = "reddit"
    PINTEREST = "pinterest"
    TIKTOK = "tiktok"
    X = "x"


class Entity(str, Enum):
    ACCOUNT = "account"
    CAMPAIGN = "campaign"
    ADSET = "adset"
    AD = "ad"
    CREATIVE = "creative"


class DatePreset(str, Enum):
    TODAY = "today"
    YESTERDAY = "yesterday"
    LAST_3D = "last_3d"
    LAST_7D = "last_7d"
    LAST_14D = "last_14d"
    LAST_28D = "last_28d"
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    LIFETIME = "lifetime"
