#!/usr/bin/env python3
"""No-agent cron job: last month's spending per category. Empty output = silent."""

from inbox import spend

if out := spend(None):
    print(out)
