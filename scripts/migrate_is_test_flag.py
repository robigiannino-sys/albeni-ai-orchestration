#!/usr/bin/env python3
"""
FASE 7.4.A — Migration is_test flag su behavioral_signals (2026-05-15)

1. ALTER TABLE behavioral_signals ADD COLUMN is_test BOOLEAN DEFAULT FALSE NOT NULL
2. UPDATE retroattivo: marca come is_test=TRUE tutti gli events dei 13 user_id
   che hanno almeno UN event_type='checkout_complete' (synthetic users)
3. Verify counts pre/post

Run from Mac:
    cd ~/Desktop/ALBENI/albeni.com/STEFANO/AI\ STACK\ APP/ai-orchestration-layer
    railway run --service Postgres bash -c 'python3 scripts/migrate_is_test_flag.py'

Idempotente: safe da rilanciare (DDL usa IF NOT EXISTS, UPDATE è no-op se già marcati).
"""
import os
import sys
import psycopg2

DRY_RUN = '--dry-run' in sys.argv

def main():
    url = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_PUBLIC_URL not set", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(url)
    conn.autocommit = False
    cur = conn.cursor()

    print(f"{'DRY-RUN: ' if DRY_RUN else ''}Migrating is_test flag on behavioral_signals\n")

    # Pre-state
    cur.execute("SELECT COUNT(*) FROM behavioral_signals")
    total = cur.fetchone()[0]
    print(f"Total behavioral_signals rows: {total}")

    # Step 1: Add column if missing
    cur.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name='behavioral_signals' AND column_name='is_test'
    """)
    has_col = cur.fetchone() is not None
    if has_col:
        print("Column is_test already exists (idempotent path).")
    else:
        if DRY_RUN:
            print("[DRY-RUN] Would: ALTER TABLE behavioral_signals ADD COLUMN is_test BOOLEAN NOT NULL DEFAULT FALSE")
        else:
            cur.execute("ALTER TABLE behavioral_signals ADD COLUMN is_test BOOLEAN NOT NULL DEFAULT FALSE")
            print("Column is_test added.")

    # Step 2: Identify synthetic user_id (those with at least one checkout_complete)
    cur.execute("""
        SELECT DISTINCT user_id FROM behavioral_signals
        WHERE event_type = 'checkout_complete' AND user_id IS NOT NULL
    """)
    synthetic_ids = [r[0] for r in cur.fetchall()]
    print(f"Synthetic users (with ≥1 checkout_complete): {len(synthetic_ids)}")
    for uid in synthetic_ids:
        print(f"  - {uid}")

    if not synthetic_ids:
        print("No synthetic users to flag. Done.")
        conn.commit()
        return

    # Step 3: Count events that will be flagged
    cur.execute("""
        SELECT COUNT(*) FROM behavioral_signals
        WHERE user_id = ANY(%s) AND is_test = FALSE
    """, (synthetic_ids,))
    to_flag = cur.fetchone()[0]
    print(f"\nEvents to flag is_test=TRUE: {to_flag}")

    # Step 4: Breakdown by event_type pre-update
    cur.execute("""
        SELECT event_type, COUNT(*) FROM behavioral_signals
        WHERE user_id = ANY(%s)
        GROUP BY event_type ORDER BY 2 DESC
    """, (synthetic_ids,))
    rows = cur.fetchall()
    print("\nBreakdown event_type (synthetic users):")
    for et, n in rows:
        print(f"  {et:30s} {n}")

    # Step 5: Execute UPDATE
    if DRY_RUN:
        print("\n[DRY-RUN] Would UPDATE %d rows" % to_flag)
    else:
        cur.execute("""
            UPDATE behavioral_signals SET is_test = TRUE
            WHERE user_id = ANY(%s) AND is_test = FALSE
        """, (synthetic_ids,))
        updated = cur.rowcount
        print(f"\nUPDATE executed: {updated} rows flagged is_test=TRUE")

    # Step 6: Verify post-state
    cur.execute("SELECT COUNT(*) FROM behavioral_signals WHERE is_test = TRUE")
    test_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM behavioral_signals WHERE is_test = FALSE")
    real_count = cur.fetchone()[0]
    print(f"\n=== POST-MIGRATION STATE ===")
    print(f"  is_test = TRUE  : {test_count} events")
    print(f"  is_test = FALSE : {real_count} events")
    print(f"  TOTAL           : {test_count + real_count} (was {total})")

    # Step 7: Verify funnel logic — synthetic users should have 0 conversion if filtered
    cur.execute("""
        SELECT COUNT(DISTINCT user_id) FROM behavioral_signals
        WHERE event_type = 'checkout_complete' AND is_test = FALSE
    """)
    real_conv = cur.fetchone()[0]
    cur.execute("""
        SELECT COUNT(DISTINCT user_id) FROM behavioral_signals
        WHERE event_type = 'checkout_complete'
    """)
    all_conv = cur.fetchone()[0]
    print(f"\n=== FUNNEL CONVERSION CHECK (90d window not applied — all-time) ===")
    print(f"  All checkout_complete users    : {all_conv}")
    print(f"  Real checkout_complete users   : {real_conv}")
    print(f"  Synthetic (filtered out)        : {all_conv - real_conv}")

    if DRY_RUN:
        print("\n[DRY-RUN] Rollback (no changes committed)")
        conn.rollback()
    else:
        conn.commit()
        print("\n✅ Migration committed.")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
