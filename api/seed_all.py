# api/seed_all.py
"""
One-shot seeding entrypoint for Docker Compose.

Loads:
1) Courses + prerequisites from UIUC_CSV
2) Students + completed courses from STUDENTS_CSV
"""

import os
import time

from api.db import run  # uses Neo4j settings from env
from api.load_students import load_students  # your new loader


def wait_for_neo4j(timeout_s: int = 120) -> None:
    """Wait until Neo4j is reachable (compose healthcheck should do this, but belt+suspenders)."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            rows = run("RETURN 1 AS ok")
            if rows and rows[0].get("ok") == 1:
                return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError("Neo4j did not become ready in time.")


# in api/seed_all.py
import csv
from api.db import run

def load_uiuc_prereqs(csv_path: str) -> None:
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            course = (row.get("Course") or "").strip()
            if not course:
                continue

            run("MERGE (:Course {course_id:$id})", {"id": course})

            # your dataset has columns "0".."9" for prerequisite course IDs
            for i in range(10):
                prereq = (row.get(str(i)) or "").strip()
                if not prereq:
                    continue

                run(
                    """
                    MERGE (c:Course {course_id:$c})
                    MERGE (p:Course {course_id:$p})
                    MERGE (c)-[:REQUIRES]->(p)
                    """,
                    {"c": course, "p": prereq},
                )

    # constraints/indexes (safe to run repeatedly)
    run("CREATE CONSTRAINT course_id_unique IF NOT EXISTS FOR (c:Course) REQUIRE c.course_id IS UNIQUE")
    run("CREATE CONSTRAINT student_id_unique IF NOT EXISTS FOR (s:Student) REQUIRE s.student_id IS UNIQUE")
    run("CREATE INDEX course_id_index IF NOT EXISTS FOR (c:Course) ON (c.course_id)")
    run("CREATE INDEX student_id_index IF NOT EXISTS FOR (s:Student) ON (s.student_id)")


def main() -> None:
    uiuc_csv = os.getenv("UIUC_CSV", "/data/uiuc-prerequisites.csv")
    students_csv = os.getenv("STUDENTS_CSV", "/data/students.csv")

    wait_for_neo4j()

    print(f"[seed] Loading UIUC prerequisites from {uiuc_csv}")
    load_uiuc_prereqs(uiuc_csv)

    print(f"[seed] Loading students from {students_csv}")
    load_students(students_csv)

    print("[seed] Done.")


if __name__ == "__main__":
    main()
