from fastapi import FastAPI, HTTPException, Query
from typing import List, Optional
from api.db import run, close_driver
from api.schemas import (
    PrereqResponse, EligibilityResponse, CycleResponse,
    SequenceResponse, GraduationPathsResponse, SkillsResponse
)
 
from collections import defaultdict, deque

app = FastAPI(title="University Prerequisite Planner API")

@app.on_event("shutdown")
def _shutdown():
    close_driver()



@app.get("/api/courses/{course_id}/prerequisites")
def get_prerequisites(course_id: str, max_depth: int = 10):
    d = max(1, min(int(max_depth), 20))

    exists = run(
        "MATCH (c:Course {course_id:$cid}) RETURN count(c) AS n",
        {"cid": course_id},
    )[0]["n"]
    if exists == 0:
        raise HTTPException(status_code=404, detail="Course not found")

    direct = run(
        """
        MATCH (:Course {course_id:$cid})-[:REQUIRES]->(p:Course)
        RETURN collect(DISTINCT p.course_id) AS direct
        """,
        {"cid": course_id},
    )[0]["direct"]

    transitive = run(
        f"""
        MATCH (:Course {{course_id:$cid}})-[:REQUIRES*1..{d}]->(p:Course)
        RETURN collect(DISTINCT p.course_id) AS transitive
        """,
        {"cid": course_id},
    )[0]["transitive"]

    return {"course_id": course_id, "direct": direct, "transitive": transitive}


@app.get("/api/students/{student_id}/eligibility")
def eligibility(student_id: str, course_id: str, max_depth: int = 10):
    d = max(1, min(int(max_depth), 20))

    s_exists = run(
        "MATCH (s:Student {student_id:$sid}) RETURN count(s) AS n",
        {"sid": student_id},
    )[0]["n"]
    if s_exists == 0:
        raise HTTPException(status_code=404, detail="Student not found")

    c_exists = run(
        "MATCH (c:Course {course_id:$cid}) RETURN count(c) AS n",
        {"cid": course_id},
    )[0]["n"]
    if c_exists == 0:
        raise HTTPException(status_code=404, detail="Course not found")

    completed = run(
        """
        MATCH (s:Student {student_id:$sid})-[:COMPLETED]->(c:Course)
        RETURN collect(DISTINCT c.course_id) AS completed
        """,
        {"sid": student_id},
    )[0]["completed"]

    prereqs = run(
        f"""
        MATCH (:Course {{course_id:$cid}})-[:REQUIRES*1..{d}]->(p:Course)
        RETURN collect(DISTINCT p.course_id) AS prereqs
        """,
        {"cid": course_id},
    )[0]["prereqs"]

    missing = sorted(list(set(prereqs) - set(completed)))
    return {
        "student_id": student_id,
        "course_id": course_id,
        "eligible": len(missing) == 0,
        "missing": missing,
        "completed": completed,
    }


@app.get("/api/courses/prerequisites/cycles")
def prerequisite_cycles(max_depth: int = 10, limit: int = 50):
    d = max(1, min(int(max_depth), 20))
    lim = max(1, min(int(limit), 200))

    try:
        # NOTE: depth in variable-length patterns cannot be parameterized -> use f-string
        rows = run(
            f"""
            MATCH p=(c:Course)-[:REQUIRES*1..{d}]->(c)
            RETURN [n IN nodes(p) | n.course_id] AS cycle
            LIMIT $lim
            """,
            {"lim": lim},
        )

        cycles = []
        seen = set()

        for r in rows:
            cyc = r.get("cycle")
            if not cyc:
                continue
            # remove any None that could appear
            cyc = [x for x in cyc if x is not None]
            if not cyc:
                continue
            t = tuple(cyc)
            if t not in seen:
                seen.add(t)
                cycles.append(cyc)

        return {"cycles": cycles}

    except Exception as e:
        # If you prefer to NEVER fail the demo, you can return [] instead of raising.
        # return {"cycles": []}
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/students/{student_id}/plan/sequence")
def plan_sequence(student_id: str, target: str, max_depth: int = 10):
    # clamp depth
    d = max(1, min(int(max_depth), 20))

    # parse targets (comma-separated)
    targets = [t.strip() for t in target.split(",") if t.strip()]
    if not targets:
        raise HTTPException(status_code=422, detail="Empty target")

    # student exists?
    s_exists = run(
        "MATCH (s:Student {student_id:$sid}) RETURN count(s) AS n",
        {"sid": student_id},
    )[0]["n"]
    if s_exists == 0:
        raise HTTPException(status_code=404, detail="Student not found")

    # completed courses for student
    completed_res = run(
        """
        MATCH (s:Student {student_id:$sid})-[:COMPLETED]->(c:Course)
        RETURN collect(DISTINCT c.course_id) AS completed
        """,
        {"sid": student_id},
    )
    completed_list = (completed_res[0].get("completed") or [])
    completed = set([c for c in completed_list if c is not None])

    nodes = set()
    edges = set()  # (prereq -> course)

    for t in targets:
        # course exists?
        t_exists = run(
            "MATCH (c:Course {course_id:$cid}) RETURN count(c) AS n",
            {"cid": t},
        )[0]["n"]
        if t_exists == 0:
            raise HTTPException(status_code=404, detail=f"Course not found: {t}")

        # Get all nodes reachable from target up to depth d, plus prerequisite edges inside that subgraph
        rows = run(
            f"""
            MATCH (t:Course {{course_id:$cid}})-[:REQUIRES*0..{d}]->(c:Course)
            WITH t, collect(DISTINCT c) AS sub
            UNWIND sub AS c
            OPTIONAL MATCH (c)-[:REQUIRES]->(p:Course)
            WHERE p IN sub
            RETURN DISTINCT c.course_id AS c, p.course_id AS p
            """,
            {"cid": t},
        )

        nodes.add(t)

        for r in rows:
            c = r.get("c")
            p = r.get("p")

            # IMPORTANT: never add None
            if c is not None:
                nodes.add(c)
            if p is not None:
                nodes.add(p)

            if c is not None and p is not None:
                edges.add((p, c))

    # Extra safety
    nodes.discard(None)
    edges = {(a, b) for (a, b) in edges if a is not None and b is not None}

    # Build graph for topo sort
    adj = {n: [] for n in nodes}
    indeg = {n: 0 for n in nodes}

    for a, b in edges:
        if a not in adj:
            adj[a] = []
            indeg.setdefault(a, 0)
        if b not in adj:
            adj[b] = []
            indeg.setdefault(b, 0)

        adj[a].append(b)
        indeg[b] += 1

    # Kahn topo
    queue = sorted([n for n in nodes if indeg.get(n, 0) == 0])
    topo = []

    while queue:
        n = queue.pop(0)
        topo.append(n)
        for m in adj.get(n, []):
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
                queue.sort()

    if len(topo) != len(nodes):
        raise HTTPException(status_code=409, detail="Cycle detected in prerequisite subgraph")

    # Needed = not completed, and not already a target
    needed = [c for c in topo if c not in completed and c not in targets]
    seq = needed + [t for t in targets if t not in completed]

    return {
        "student_id": student_id,
        "target": targets,
        "sequence": seq,
        "already_completed": sorted(list((nodes & completed))),
    }




@app.get("/api/students/{student_id}/paths/graduation")
def paths_graduation(student_id: str, targets: str, max_depth: int = 6, limit: int = 50):
    d = max(1, min(int(max_depth), 20))
    lim = max(1, min(int(limit), 500))

    target_list = [t.strip() for t in targets.split(",") if t.strip()]
    if not target_list:
        raise HTTPException(status_code=422, detail="Empty targets")

    # student exists?
    s_exists = run(
        "MATCH (s:Student {student_id:$sid}) RETURN count(s) AS n",
        {"sid": student_id},
    )[0]["n"]
    if s_exists == 0:
        raise HTTPException(status_code=404, detail="Student not found")

    completed = set(run(
        """
        MATCH (s:Student {student_id:$sid})-[:COMPLETED]->(c:Course)
        RETURN collect(DISTINCT c.course_id) AS completed
        """,
        {"sid": student_id},
    )[0]["completed"] or [])

    results = []

    for t in target_list:
        t_exists = run(
            "MATCH (c:Course {course_id:$cid}) RETURN count(c) AS n",
            {"cid": t},
        )[0]["n"]
        if t_exists == 0:
            raise HTTPException(status_code=404, detail=f"Course not found: {t}")

        # Pull prerequisite edges inside the target subgraph (depth-limited)
        rows = run(
            f"""
            MATCH (t:Course {{course_id:$tid}})-[:REQUIRES*0..{d}]->(c:Course)
            OPTIONAL MATCH (c)-[:REQUIRES]->(p:Course)
            WHERE (t)-[:REQUIRES*0..{d}]->(p)
            RETURN DISTINCT c.course_id AS c, p.course_id AS p
            """,
            {"tid": t},
        )

        nodes = set()
        edges = set()  # prereq -> course

        nodes.add(t)

        for r in rows:
            c = r.get("c")
            p = r.get("p")

            # critical: skip nulls
            if c is None:
                continue
            nodes.add(c)

            if p is None:
                continue
            nodes.add(p)
            edges.add((p, c))

        # build adjacency safely
        adj = defaultdict(list)
        indeg = {n: 0 for n in nodes}

        for a, b in edges:
            if a is None or b is None:
                continue
            adj[a].append(b)
            if b in indeg:
                indeg[b] += 1

        # topo sort (stable)
        q = deque(sorted([n for n in nodes if indeg.get(n, 0) == 0]))
        topo = []
        while q:
            n = q.popleft()
            topo.append(n)
            for m in adj.get(n, []):
                indeg[m] -= 1
                if indeg[m] == 0:
                    q.append(m)

        if len(topo) != len(nodes):
            raise HTTPException(status_code=409, detail=f"Cycle detected in prerequisite subgraph for target {t}")

        # Missing prerequisites = nodes in subgraph that are not completed and not the target itself
        missing = [c for c in topo if c not in completed and c != t]

        # Provide one “suggested order” to reach t (missing first, then t if not completed)
        sequence = missing + ([] if t in completed else [t])

        results.append({
            "target": t,
            "missing": missing[:lim],
            "sequence": sequence[:lim],
        })

    return {
        "student_id": student_id,
        "targets": target_list,
        "already_completed_in_subgraph": sorted(list(completed)),
        "plans": results,
    }


@app.get("/api/courses/{course_id}/skills", response_model=SkillsResponse)
def course_skills(course_id: str):
    rows = run(
        "MATCH (c:Course {course_id:$id}) "
        "OPTIONAL MATCH (c)-[:TEACHES]->(s:Skill) "
        "OPTIONAL MATCH (cc:CourseraCourse)-[:MAPS_TO]->(c) "
        "OPTIONAL MATCH (cc)-[:TEACHES]->(s2:Skill) "
        "RETURN DISTINCT coalesce(s.name, s2.name) AS skill",
        {"id": course_id},
    )
    skills = sorted({r["skill"] for r in rows if r.get("skill")})
    return {"course_id": course_id, "skills": skills}

@app.get("/api/health")
def health():
    try:
        x = run("RETURN 1 AS ok")
        return {"ok": bool(x and x[0]["ok"] == 1)}
    except Exception:
        raise HTTPException(status_code=503, detail="Neo4j not reachable")
