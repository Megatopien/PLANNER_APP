# Overview

This is the University Course Prerequisite Planner. It is a web app that uses Docker and FastAPI to plan courses for university students based on said courses' prerequisites'.

The main.ipynb file is an exploration of the data. Not all datasets are used, only the "University University of Illinois' Course Prerequisites" dataset.

API Features:

+ Check if student can take a course (prerequisite validation)
  + e.g. GET /api/students/{student_id}/eligibility?course_id={course_id}
+ Suggest optimal course sequence
  + e.g. GET /api/students/{student_id}/plan/sequence?target={degree_or_goal}
+ Find all possible paths to graduation
  + e.g. GET /api/students/{student_id}/paths/graduation
+ Detect circular dependencies in prerequisites
  + e.g. GET /api/courses/prerequisites/cycles



# Data
The datasets come from the following sources:
+ [University University of Illinois' Course Prerequisites](https://github.com/illinois/prerequisites-dataset?tab=readme-ov-file)
  + 8,589 course sections
  + Structured CSV with all course prerequisites
+ [Open University Learning Analytics Dataset](https://www.kaggle.com/datasets/rocki37/open-university-learning-analytics-dataset)
  + 32,593 students, 22 course presentations
  + Includes demographics, assessments, and VLE interactions
+ [coursera-course-dataset](https://huggingface.co/datasets/azrai99/coursera-course-dataset)
  + Course skills and metadata
  + Good for skill graph construction
  + Requires internet connection to download(or does it?)

# Instructions
Navigate to this directory. Then run these commands:
+ cd api
+ pip install -r requirements.txt
+ export NEO4J_URI=bolt://localhost:7687
+ export NEO4J_USER=neo4j
+ export NEO4J_PASSWORD=neo4j
+ uvicorn app:app --reload

Then go to website: `http://localhost:8000/docs`

Run the following commands when you first open this code and navigate to this folder:
+ cd api
+ pip install -r requirements.txt
+ docker compose up --build


Run this code every time you want to access the API:
+ docker compose up
  + This command runs all the necessary parts(Docker, Neo4j, API)
  + Overall, it takes 2 minutes to execute
  + If the port 8000 is already occupied, then run lsof
