import os
import pandas as pd
from neo4j import GraphDatabase

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PWD = os.getenv("NEO4J_PASSWORD", "neo4j")

CSV_PATH = os.getenv("UIUC_CSV", "../uiuc-prerequisites.csv")

df = pd.read_csv(CSV_PATH)

driver = GraphDatabase.driver(URI, auth=(USER, PWD))

def norm(x):
    if pd.isna(x):
        return None
    s = str(x).strip()
    return s if s else None

with driver.session() as s:
    for _, row in df.iterrows():
        course = norm(row.get("Course"))
        if not course:
            continue

        s.run("MERGE (:Course {course_id:$id})", {"id": course})

        for col in [str(i) for i in range(10)]:
            prereq = norm(row.get(col))
            if not prereq:
                continue
            s.run(
                """
                MERGE (c:Course {course_id:$c})
                MERGE (p:Course {course_id:$p})
                MERGE (c)-[:REQUIRES]->(p)
                """,
                {"c": course, "p": prereq},
            )

driver.close()
print("UIUC prerequisites loaded.")
