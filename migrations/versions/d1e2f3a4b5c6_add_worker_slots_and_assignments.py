"""worker slot assignments and worker snapshots

Revision ID: d1e2f3a4b5c6
Revises: c4d5e6f7a8b9
Create Date: 2026-09-04 14:00:00.000000

This migration converts dynamic worker barcodes into fixed 150 credential
slots (TRB000001–TRB000150) with immutable assignment history and worker
identity snapshots in harvest entries.

DOWNGRADE POLICY:
    This migration is NOT safely reversible. The barcode transformation and
    assignment creation destroy information that the previous schema cannot
    represent. Attempting to downgrade will raise RuntimeError. To reverse
    this migration, restore the pre-migration database backup.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d1e2f3a4b5c6"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None

MAX_SLOTS = 150


def upgrade():
    conn = op.get_bind()

    # =========================================================================
    # PRECONDITIONS — validate before any structural changes
    # =========================================================================

    existing_worker_count = conn.execute(
        sa.text("SELECT COUNT(*) FROM workers")
    ).scalar()

    if existing_worker_count > MAX_SLOTS:
        raise RuntimeError(
            f"Found {existing_worker_count} workers; maximum allowed is "
            f"{MAX_SLOTS}. Aborting migration."
        )

    # All existing workers must have a non-empty name
    bad_names = conn.execute(
        sa.text(
            "SELECT id, name FROM workers "
            "WHERE name IS NULL OR LENGTH(TRIM(name)) = 0"
        )
    ).mappings().all()
    if bad_names:
        raise RuntimeError(
            f"Workers with empty or null name: "
            f"{[dict(r) for r in bad_names]}. "
            "All existing workers must have a name before migration."
        )

    # Collision check: TRB000001–TRB000150 must not overlap with existing barcodes
    for slot in range(1, MAX_SLOTS + 1):
        trb = f"TRB{slot:06d}"
        existing = conn.execute(
            sa.text("SELECT id, barcode FROM workers WHERE barcode = :bc"),
            {"bc": trb},
        ).mappings().first()
        if existing:
            raise RuntimeError(
                f"Barcode collision: {trb} already exists as worker "
                f"id={existing['id']} (barcode={existing['barcode']}). "
                "Cannot proceed with migration."
            )

    # =========================================================================
    # STRUCTURAL CHANGES
    # =========================================================================

    # --- 1. Make workers.name nullable (production has NOT NULL) ---
    op.alter_column(
        "workers",
        "name",
        existing_type=sa.String(length=150),
        nullable=True,
    )

    # --- 2. Create worker_assignments table ---
    op.create_table(
        "worker_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "worker_id",
            sa.Integer(),
            sa.ForeignKey("workers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("person_name", sa.String(length=150), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_check_constraint(
        "ck_worker_assignments_person_name_not_empty",
        "worker_assignments",
        "LENGTH(TRIM(person_name)) > 0",
    )
    op.create_check_constraint(
        "ck_worker_assignments_ended_at_gte_started_at",
        "worker_assignments",
        "ended_at IS NULL OR ended_at >= started_at",
    )
    op.create_index(
        "ix_worker_assignments_worker_id",
        "worker_assignments",
        ["worker_id"],
    )
    op.create_index(
        "ux_worker_assignments_open_per_worker",
        "worker_assignments",
        ["worker_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
    )

    # --- 3. Add worker snapshot fields to harvest_entries ---
    op.add_column(
        "harvest_entries",
        sa.Column("worker_assignment_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "harvest_entries",
        sa.Column("worker_slot_number_snapshot", sa.Integer(), nullable=True),
    )
    op.add_column(
        "harvest_entries",
        sa.Column("worker_barcode_snapshot", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "harvest_entries",
        sa.Column("worker_name_snapshot", sa.String(length=150), nullable=True),
    )

    # --- 4. Add slot_number to workers (nullable temporarily for backfill) ---
    op.add_column(
        "workers",
        sa.Column("slot_number", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_workers_slot_number_range",
        "workers",
        "slot_number BETWEEN 1 AND 150",
    )

    # =========================================================================
    # BACKFILL — transform existing workers into fixed slots
    # =========================================================================

    existing_workers = conn.execute(
        sa.text(
            "SELECT id, barcode, name, created_at "
            "FROM workers ORDER BY id ASC"
        )
    ).mappings().all()

    # Remember old barcodes, names, and slot numbers for snapshot verification
    old_barcodes_by_worker_id = {}
    old_names_by_worker_id = {}
    slot_numbers_by_worker_id = {}

    max_slot = len(existing_workers)

    for idx, worker in enumerate(existing_workers, start=1):
        slot_number = idx
        wid = worker["id"]
        old_barcode = worker["barcode"]
        old_name = worker["name"]
        old_created_at = worker["created_at"]

        # Store for verification
        old_barcodes_by_worker_id[wid] = old_barcode
        old_names_by_worker_id[wid] = old_name
        slot_numbers_by_worker_id[wid] = slot_number

        # a. Compute started_at using LEAST(worker.created_at, MIN(entry.created_at))
        started_at = conn.execute(
            sa.text(
                "SELECT LEAST("
                "  :created_at, "
                "  COALESCE("
                "    (SELECT MIN(created_at) "
                "     FROM harvest_entries WHERE worker_id = :wid), "
                "    :created_at"
                "  )"
                ")::timestamp with time zone"
            ),
            {"wid": wid, "created_at": old_created_at},
        ).scalar()

        # b. Update slot_number
        conn.execute(
            sa.text("UPDATE workers SET slot_number = :sn WHERE id = :wid"),
            {"sn": slot_number, "wid": wid},
        )

        # c. Backfill snapshots: OLD barcode, OLD name, NEW slot_number
        conn.execute(
            sa.text(
                "UPDATE harvest_entries "
                "SET worker_barcode_snapshot = :bc, "
                "    worker_name_snapshot = :nm, "
                "    worker_slot_number_snapshot = :sn "
                "WHERE worker_id = :wid "
                "AND worker_barcode_snapshot IS NULL"
            ),
            {"bc": old_barcode, "nm": old_name, "sn": slot_number, "wid": wid},
        )

        # d. INSERT ... RETURNING id (direct use, no re-query)
        assignment_id = conn.execute(
            sa.text(
                "INSERT INTO worker_assignments "
                "(worker_id, person_name, started_at, ended_at) "
                "VALUES (:wid, :nm, :started, NULL) "
                "RETURNING id"
            ),
            {"wid": wid, "nm": old_name, "started": started_at},
        ).scalar()

        # e. Link entries using the returned assignment_id directly
        conn.execute(
            sa.text(
                "UPDATE harvest_entries "
                "SET worker_assignment_id = :aid "
                "WHERE worker_id = :wid "
                "AND worker_assignment_id IS NULL"
            ),
            {"aid": assignment_id, "wid": wid},
        )

        # f. Update barcode to fixed TRB format
        new_barcode = f"TRB{slot_number:06d}"
        conn.execute(
            sa.text("UPDATE workers SET barcode = :bc WHERE id = :wid"),
            {"bc": new_barcode, "wid": wid},
        )

    # =========================================================================
    # EMPTY SLOTS — slots beyond existing workers (no assignment, name=NULL)
    # =========================================================================

    if max_slot < MAX_SLOTS:
        for slot in range(max_slot + 1, MAX_SLOTS + 1):
            conn.execute(
                sa.text(
                    "INSERT INTO workers "
                    "(barcode, name, active, slot_number, created_at) "
                    "VALUES (:bc, NULL, TRUE, :sn, CURRENT_TIMESTAMP)"
                ),
                {"bc": f"TRB{slot:06d}", "sn": slot},
            )

    # =========================================================================
    # FINALIZE CONSTRAINTS
    # =========================================================================

    op.alter_column("workers", "slot_number", nullable=False)
    op.create_unique_constraint("uq_workers_slot_number", "workers", ["slot_number"])
    op.create_check_constraint(
        "ck_workers_barcode_fixed_format",
        "workers",
        "barcode ~ '^TRB[0-9]{6}$'",
    )
    op.create_check_constraint(
        "ck_workers_barcode_matches_slot",
        "workers",
        "barcode = 'TRB' || LPAD(slot_number::text, 6, '0')",
    )

    # FK and index for worker_assignment_id
    op.create_foreign_key(
        "fk_harvest_entries_worker_assignment_id",
        "harvest_entries",
        "worker_assignments",
        ["worker_assignment_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_harvest_entries_worker_assignment_id",
        "harvest_entries",
        ["worker_assignment_id"],
    )

    # Snapshot consistency check (all-or-nothing)
    op.create_check_constraint(
        "ck_harvest_entries_worker_snapshot_consistency",
        "harvest_entries",
        "(worker_assignment_id IS NULL AND worker_slot_number_snapshot IS NULL "
        "AND worker_barcode_snapshot IS NULL AND worker_name_snapshot IS NULL) OR "
        "(worker_assignment_id IS NOT NULL AND worker_slot_number_snapshot IS NOT NULL "
        "AND worker_barcode_snapshot IS NOT NULL AND worker_name_snapshot IS NOT NULL)",
    )

    # =========================================================================
    # POST-BACKFILL VERIFICATIONS
    # =========================================================================

    # 1. Exactly 150 workers
    total = conn.execute(sa.text("SELECT COUNT(*) FROM workers")).scalar()
    if total != MAX_SLOTS:
        raise RuntimeError(f"Expected {MAX_SLOTS} workers, found {total}")

    # 2. slot_number covers 1–150 without gaps
    slots = [r[0] for r in conn.execute(
        sa.text("SELECT slot_number FROM workers ORDER BY slot_number")
    ).fetchall()]
    if slots != list(range(1, MAX_SLOTS + 1)):
        raise RuntimeError(f"slot_number gap detected: {slots}")

    # 3. All barcodes match TRB format
    bad_barcodes = conn.execute(
        sa.text(
            "SELECT id, barcode FROM workers "
            "WHERE barcode !~ '^TRB[0-9]{6}$'"
        )
    ).mappings().all()
    if bad_barcodes:
        raise RuntimeError(f"Invalid barcodes: {[dict(r) for r in bad_barcodes]}")

    # 4. Open assignments == existing_worker_count
    open_count = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM worker_assignments WHERE ended_at IS NULL"
        )
    ).scalar()
    if open_count != existing_worker_count:
        raise RuntimeError(
            f"Expected {existing_worker_count} open assignments, found {open_count}"
        )

    # 5. New slots have no assignment
    new_slots_without = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM workers w "
            "WHERE w.slot_number > :max_slot AND w.name IS NULL "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM worker_assignments wa "
            "  WHERE wa.worker_id = w.id AND wa.ended_at IS NULL"
            ")"
        ),
        {"max_slot": max_slot},
    ).scalar()
    expected_new = MAX_SLOTS - max_slot
    if new_slots_without != expected_new:
        raise RuntimeError(
            f"Expected {expected_new} new slots without assignment, "
            f"found {new_slots_without}"
        )

    # 6. Snapshot all-or-nothing (no partial)
    partial = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM harvest_entries "
            "WHERE (worker_assignment_id IS NULL "
            "  AND (worker_slot_number_snapshot IS NOT NULL "
            "    OR worker_barcode_snapshot IS NOT NULL "
            "    OR worker_name_snapshot IS NOT NULL)) "
            "OR (worker_assignment_id IS NOT NULL "
            "  AND (worker_slot_number_snapshot IS NULL "
            "    OR worker_barcode_snapshot IS NULL "
            "    OR worker_name_snapshot IS NULL))"
        )
    ).scalar()
    if partial:
        raise RuntimeError(
            f"Found {partial} entries with partial worker snapshots"
        )

    # 7. No existing entry left with all-null snapshots
    all_null = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM harvest_entries "
            "WHERE worker_assignment_id IS NULL "
            "AND worker_slot_number_snapshot IS NULL "
            "AND worker_barcode_snapshot IS NULL "
            "AND worker_name_snapshot IS NULL"
        )
    ).scalar()
    if all_null:
        raise RuntimeError(f"Found {all_null} entries with all-null snapshots")

    # 8. Verify snapshot correctness per worker using stored old values
    for wid, old_bc in old_barcodes_by_worker_id.items():
        old_nm = old_names_by_worker_id[wid]
        expected_slot = slot_numbers_by_worker_id[wid]
        bad_snapshots = conn.execute(
            sa.text(
                "SELECT he.id, he.worker_barcode_snapshot, "
                "       he.worker_name_snapshot, "
                "       he.worker_slot_number_snapshot "
                "FROM harvest_entries he "
                "WHERE he.worker_id = :wid "
                "AND ("
                "  he.worker_barcode_snapshot IS DISTINCT FROM :bc "
                "  OR he.worker_name_snapshot IS DISTINCT FROM :nm "
                "  OR he.worker_slot_number_snapshot IS DISTINCT FROM :sn"
                ")"
            ),
            {"wid": wid, "bc": old_bc, "nm": old_nm, "sn": expected_slot},
        ).mappings().all()
        if bad_snapshots:
            raise RuntimeError(
                f"Worker {wid}: snapshot mismatch. "
                f"Expected barcode={old_bc}, name={old_nm}, "
                f"slot={expected_slot}. "
                f"Bad entries: {[dict(r) for r in bad_snapshots]}"
            )

    # 9. Verify slot_number_snapshot matches actual slot for each entry
    slot_mismatch = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM harvest_entries he "
            "JOIN workers w ON he.worker_id = w.id "
            "WHERE he.worker_slot_number_snapshot IS DISTINCT FROM w.slot_number"
        )
    ).scalar()
    if slot_mismatch:
        raise RuntimeError(
            f"Found {slot_mismatch} entries with slot_number_snapshot mismatch"
        )

    # 10. Verify assignment.worker_id == entry.worker_id for all linked entries
    mismatched_worker = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM harvest_entries he "
            "JOIN worker_assignments wa ON he.worker_assignment_id = wa.id "
            "WHERE he.worker_id IS DISTINCT FROM wa.worker_id"
        )
    ).scalar()
    if mismatched_worker:
        raise RuntimeError(
            f"Found {mismatched_worker} entries where "
            f"worker_id != assignment.worker_id"
        )

    # 11. Verify harvest_entries.worker_name_snapshot == assignment.person_name
    name_mismatch = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM harvest_entries he "
            "JOIN worker_assignments wa ON he.worker_assignment_id = wa.id "
            "WHERE he.worker_name_snapshot IS DISTINCT FROM wa.person_name"
        )
    ).scalar()
    if name_mismatch:
        raise RuntimeError(
            f"Found {name_mismatch} entries where "
            f"worker_name_snapshot != assignment.person_name"
        )

    # 12. worker_name_snapshot is not empty for all linked entries
    empty_name = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM harvest_entries "
            "WHERE worker_assignment_id IS NOT NULL "
            "AND (worker_name_snapshot IS NULL "
            "  OR LENGTH(TRIM(worker_name_snapshot)) = 0)"
        )
    ).scalar()
    if empty_name:
        raise RuntimeError(
            f"Found {empty_name} entries with empty worker_name_snapshot"
        )

    # 13. started_at <= entry.created_at for all linked entries
    bad_dates = conn.execute(
        sa.text(
            "SELECT he.id FROM harvest_entries he "
            "JOIN worker_assignments wa ON he.worker_assignment_id = wa.id "
            "WHERE wa.started_at > he.created_at"
        )
    ).fetchall()
    if bad_dates:
        raise RuntimeError(
            f"Entries where assignment.started_at > entry.created_at: "
            f"{[r[0] for r in bad_dates]}"
        )

    # 14. Explicit barcode verification: barcode matches slot formula
    barcode_mismatch = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM workers "
            "WHERE barcode IS DISTINCT FROM "
            "('TRB' || LPAD(slot_number::text, 6, '0'))"
        )
    ).scalar()
    if barcode_mismatch:
        raise RuntimeError(
            f"Found {barcode_mismatch} workers where "
            f"barcode != 'TRB' || LPAD(slot_number, 6, '0')"
        )


def downgrade():
    """Reverse worker slot assignments migration.

    This migration converts worker barcodes to a fixed TRB format and
    creates assignment records linking to historical harvest entries.
    The previous schema cannot represent this data.

    DOWNGRADE IS NOT POSSIBLE.
    Restore the pre-migration database backup.
    """
    raise RuntimeError(
        "This data migration is not safely reversible. "
        "Restore the pre-migration database backup."
    )
