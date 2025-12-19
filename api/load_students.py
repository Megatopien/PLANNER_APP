# api/load_students.py
import os
import csv
from api.db import run

STUDENTS_CSV = os.getenv("STUDENTS_CSV", "/app/data/students.csv")

def load_students(csv_path: str = STUDENTS_CSV) -> None:
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid = row["student_id"].strip()
            completed_raw = row.get("completed_courses", "").strip()
            completed = [c.strip() for c in completed_raw.split(";") if c.strip()]

            # Create student
            run("MERGE (:Student {student_id:$sid})", {"sid": sid})

            # Create COMPLETED edges (only if course exists)
            for course_id in completed:
                run(
                    """
                    MATCH (c:Course {course_id:$cid})
                    MERGE (s:Student {student_id:$sid})
                    MERGE (s)-[:COMPLETED]->(c)
                    """,
                    {"sid": sid, "cid": course_id},
                )

if __name__ == "__main__":
    load_students()
    print(f"Loaded students from {STUDENTS_CSV}")
