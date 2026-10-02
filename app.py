from flask import Flask, render_template, request, redirect, url_for, session, flash
from dotenv import load_dotenv
import sqlite3
import os
import re
from werkzeug.security import generate_password_hash, check_password_hash
from openai import OpenAI


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")

client = None

if API_KEY:
    client = OpenAI(api_key=API_KEY)
    print("✅ OPENAI API KEY FOUND")
else:
    print("⚠️ OPENAI API KEY NOT FOUND")


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)

app.secret_key = "my_interview_secret_key"


# ============================================================
# USER DATABASE
# ============================================================

def get_user_database():

    connection = sqlite3.connect("users.db")

    connection.row_factory = sqlite3.Row

    return connection


# ============================================================
# INTERVIEW DATABASE
# ============================================================

def get_interview_database():

    connection = sqlite3.connect("interview.db")

    connection.row_factory = sqlite3.Row

    return connection


# ============================================================
# CREATE INTERVIEW TABLE
# ============================================================

def create_interview_table():

    connection = get_interview_database()

    try:

        connection.execute("""
            CREATE TABLE IF NOT EXISTS interviews (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER,

                role TEXT,

                difficulty TEXT,

                experience TEXT,

                interview_type TEXT,

                score INTEGER,

                feedback TEXT

            )
        """)

        connection.commit()

        columns = connection.execute(
            "PRAGMA table_info(interviews)"
        ).fetchall()

        existing_columns = [
            column["name"]
            for column in columns
        ]

        if "difficulty" not in existing_columns:

            connection.execute("""
                ALTER TABLE interviews
                ADD COLUMN difficulty TEXT
            """)

        if "experience" not in existing_columns:

            connection.execute("""
                ALTER TABLE interviews
                ADD COLUMN experience TEXT
            """)

        if "interview_type" not in existing_columns:

            connection.execute("""
                ALTER TABLE interviews
                ADD COLUMN interview_type TEXT
            """)

        connection.commit()

    except Exception as error:

        print("❌ DATABASE SETUP ERROR:", error)

    finally:

        connection.close()


# ============================================================
# HOME
# ============================================================

@app.route("/")
def index():

    return render_template("index.html")


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        role = request.form.get(
            "role",
            "Student"
        )

        if not name or not email or not password:

            flash("Please fill all fields.")

            return redirect(
                url_for("register")
            )

        if len(password) < 6:

            flash(
                "Password must contain at least 6 characters."
            )

            return redirect(
                url_for("register")
            )

        connection = get_user_database()

        try:

            existing_user = connection.execute("""
                SELECT id
                FROM users
                WHERE email = ?
            """, (email,)).fetchone()

            if existing_user:

                connection.close()

                flash(
                    "Email already exists. Please login."
                )

                return redirect(
                    url_for("login")
                )

            hashed_password = generate_password_hash(
                password
            )

            connection.execute("""
                INSERT INTO users
                (
                    name,
                    email,
                    password,
                    role
                )
                VALUES (?, ?, ?, ?)
            """, (
                name,
                email,
                hashed_password,
                role
            ))

            connection.commit()

            connection.close()

            flash(
                "Account created successfully!"
            )

            return redirect(
                url_for("login")
            )

        except Exception as error:

            connection.close()

            print(
                "❌ REGISTER ERROR:",
                error
            )

            flash(
                "Unable to create account."
            )

            return redirect(
                url_for("register")
            )

    return render_template(
        "register.html"
    )


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        connection = get_user_database()

        try:

            user = connection.execute("""
                SELECT *
                FROM users
                WHERE email = ?
            """, (email,)).fetchone()

            connection.close()

            if user:

                password_valid = False

                try:

                    password_valid = check_password_hash(
                        user["password"],
                        password
                    )

                except Exception:

                    password_valid = (
                        user["password"] == password
                    )

                if password_valid:

                    session["user_id"] = user["id"]

                    session["name"] = user["name"]

                    session["email"] = user["email"]

                    session["role"] = user["role"]

                    return redirect(
                        url_for("dashboard")
                    )

            flash(
                "Invalid email or password."
            )

            return redirect(
                url_for("login")
            )

        except Exception as error:

            connection.close()

            print(
                "❌ LOGIN ERROR:",
                error
            )

            flash(
                "Login error."
            )

            return redirect(
                url_for("login")
            )

    return render_template(
        "login.html"
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("index")
    )


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    create_interview_table()

    connection = get_interview_database()

    try:

        interviews = connection.execute("""
            SELECT score
            FROM interviews
            WHERE user_id = ?
            ORDER BY id DESC
        """, (
            session["user_id"],
        )).fetchall()

        total_interviews = len(
            interviews
        )

        if total_interviews > 0:

            scores = [
                interview["score"] or 0
                for interview in interviews
            ]

            average_score = round(
                sum(scores) / len(scores),
                1
            )

            best_score = max(scores)

        else:

            average_score = 0

            best_score = 0

    except Exception as error:

        print(
            "❌ DASHBOARD ERROR:",
            error
        )

        total_interviews = 0

        average_score = 0

        best_score = 0

    finally:

        connection.close()

    return render_template(
        "dashboard.html",

        username=session.get("name"),

        total_interviews=total_interviews,

        average_score=average_score,

        best_score=best_score
    )


# ============================================================
# CREATE INTERVIEW
# ============================================================

@app.route("/create", methods=["GET", "POST"])
def create():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if request.method == "POST":

        role = request.form.get(
            "role",
            "General IT"
        )

        difficulty = request.form.get(
            "difficulty",
            "Medium"
        )

        experience = request.form.get(
            "experience",
            "Fresher"
        )

        session["interview_role"] = role

        session["interview_difficulty"] = difficulty

        session["interview_experience"] = experience

        session["interview_type"] = (
            "Technical / General"
        )

        session["questions"] = []

        session["answers"] = []

        session["question_number"] = 0

        session["result_saved"] = False

        return redirect(
            url_for("mock_interview")
        )

    return render_template(
        "create.html"
    )


# ============================================================
# GENERATE AI QUESTIONS
# ============================================================

def generate_questions(
    role,
    difficulty,
    experience
):

    fallback_questions = [

        "Tell me about yourself.",

        "Why do you want this role?",

        "What are your strengths?",

        "What is your biggest weakness?",

        "Where do you see yourself in five years?"

    ]

    if not client:

        print(
            "⚠️ OpenAI API key is not available."
        )

        return fallback_questions

    prompt = f"""
You are a professional interviewer.

Create exactly 5 interview questions.

Job Role:
{role}

Difficulty:
{difficulty}

Experience:
{experience}

Requirements:

- Exactly 5 questions
- Mix HR and job-related questions
- Suitable for a student or fresher
- Realistic interview questions
- Number questions from 1 to 5
- Do not provide answers

Return only the questions.
"""

    try:

        response = client.chat.completions.create(

            model="gpt-4o-mini",

            messages=[

                {
                    "role": "system",
                    "content":
                    "You are a professional interviewer."
                },

                {
                    "role": "user",
                    "content": prompt
                }

            ],

            temperature=0.7
        )

        ai_text = response.choices[
            0
        ].message.content

        questions = []

        for line in ai_text.split("\n"):

            line = line.strip()

            if not line:
                continue

            line = re.sub(
                r"^\s*\d+[\.\)\-:]\s*",
                "",
                line
            )

            if line:

                questions.append(line)

        if len(questions) >= 5:

            return questions[:5]

    except Exception as error:

        print(
            "❌ AI QUESTION ERROR:",
            error
        )

    return fallback_questions


# ============================================================
# MOCK INTERVIEW
# ============================================================

@app.route(
    "/mock-interview",
    methods=["GET", "POST"]
)
def mock_interview():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if not session.get("questions"):

        questions = generate_questions(

            session.get(
                "interview_role",
                "General IT"
            ),

            session.get(
                "interview_difficulty",
                "Medium"
            ),

            session.get(
                "interview_experience",
                "Fresher"
            )
        )

        session["questions"] = questions

        session["answers"] = []

        session["question_number"] = 0

    if request.method == "POST":

        answer = request.form.get(
            "answer",
            ""
        ).strip()

        if not answer:

            answer = "No answer provided."

        answers = session.get(
            "answers",
            []
        )

        answers.append(answer)

        session["answers"] = answers

        question_number = session.get(
            "question_number",
            0
        )

        question_number += 1

        session["question_number"] = question_number

        if question_number >= 5:

            return redirect(
                url_for("interview_result")
            )

    questions = session.get(
        "questions",
        []
    )

    question_number = session.get(
        "question_number",
        0
    )

    if question_number >= len(questions):

        return redirect(
            url_for("interview_result")
        )

    return render_template(

        "mock_interview.html",

        question=questions[
            question_number
        ],

        question_number=(
            question_number + 1
        ),

        total_questions=5
    )


# ============================================================
# AI EVALUATION
# ============================================================

def evaluate_answers(
    questions,
    answers
):

    if not client:

        return """
Score: 0

Overall Performance:
AI evaluation is currently unavailable.

Communication:
Please check your OpenAI API key.

Technical Knowledge:
AI evaluation could not be completed.

Strengths:
Your answers were recorded successfully.

Weaknesses:
No AI evaluation available.

Areas for Improvement:
Please configure your OpenAI API key.

Final Advice:
Try the interview again after configuring the API.
"""

    interview_text = ""

    for i in range(
        min(
            len(questions),
            len(answers)
        )
    ):

        interview_text += f"""

Question {i + 1}:
{questions[i]}

Candidate Answer:
{answers[i]}

"""

    prompt = f"""
You are a professional interview evaluator.

Evaluate the following candidate interview:

{interview_text}

Provide a detailed but easy-to-understand evaluation.

Include exactly these sections:

Overall Performance

Score: X

Communication

Technical Knowledge

Strengths

Weaknesses

Areas for Improvement

Final Advice

The score must be a number between 0 and 100.

Write the score exactly like:

Score: 75
"""

    try:

        response = client.chat.completions.create(

            model="gpt-4o-mini",

            messages=[

                {
                    "role": "system",
                    "content":
                    "You are a professional interview evaluator."
                },

                {
                    "role": "user",
                    "content": prompt
                }

            ],

            temperature=0.5
        )

        feedback = response.choices[
            0
        ].message.content

        return feedback

    except Exception as error:

        print(
            "❌ AI EVALUATION ERROR:",
            error
        )

        return """
Score: 0

Overall Performance:
Unable to evaluate the interview.

Communication:
Evaluation unavailable.

Technical Knowledge:
Evaluation unavailable.

Strengths:
Your answers were successfully recorded.

Weaknesses:
AI evaluation could not be completed.

Areas for Improvement:
Please check your API configuration.

Final Advice:
Try the interview again.
"""


# ============================================================
# INTERVIEW RESULT
# ============================================================

@app.route("/interview-result")
def interview_result():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    questions = session.get(
        "questions",
        []
    )

    answers = session.get(
        "answers",
        []
    )

    feedback = evaluate_answers(
        questions,
        answers
    )

    role = session.get(
        "interview_role",
        "General IT"
    )

    difficulty = session.get(
        "interview_difficulty",
        "Medium"
    )

    experience = session.get(
        "interview_experience",
        "Fresher"
    )

    interview_type = session.get(
        "interview_type",
        "Technical / General"
    )

    score = extract_score(feedback)

    if not session.get(
        "result_saved",
        False
    ):

        create_interview_table()

        connection = get_interview_database()

        try:

            connection.execute("""
                INSERT INTO interviews
                (
                    user_id,
                    role,
                    difficulty,
                    experience,
                    interview_type,
                    score,
                    feedback
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (

                session["user_id"],

                role,

                difficulty,

                experience,

                interview_type,

                score,

                feedback
            ))

            connection.commit()

            session["result_saved"] = True

            print(
                "✅ INTERVIEW SAVED TO HISTORY"
            )

        except Exception as error:

            print(
                "❌ HISTORY SAVE ERROR:",
                error
            )

        finally:

            connection.close()

    return render_template(

        "result.html",

        feedback=feedback,

        score=score,

        role=role,

        difficulty=difficulty,

        experience=experience
    )


# ============================================================
# SCORE EXTRACTION
# ============================================================

def extract_score(feedback):

    patterns = [

        r"Score\s*:\s*(\d+)",

        r"Score\s*-\s*(\d+)",

        r"Score\s+(\d+)",

        r"(\d+)\s*/\s*100"

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            feedback,
            re.IGNORECASE
        )

        if match:

            score = int(
                match.group(1)
            )

            return max(
                0,
                min(score, 100)
            )

    return 0


# ============================================================
# HISTORY
# ============================================================

@app.route("/history")
def history():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    create_interview_table()

    connection = get_interview_database()

    try:

        interviews = connection.execute("""
            SELECT *
            FROM interviews
            WHERE user_id = ?
            ORDER BY id DESC
        """, (
            session["user_id"],
        )).fetchall()

    except Exception as error:

        print(
            "❌ HISTORY ERROR:",
            error
        )

        interviews = []

    finally:

        connection.close()

    return render_template(
        "history.html",
        interviews=interviews
    )


# ============================================================
# ANALYTICS
# ============================================================

@app.route("/analytics")
def analytics():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    create_interview_table()

    connection = get_interview_database()

    try:

        interviews = connection.execute("""
            SELECT *
            FROM interviews
            WHERE user_id = ?
            ORDER BY id DESC
        """, (
            session["user_id"],
        )).fetchall()

    except Exception as error:

        print(
            "❌ ANALYTICS ERROR:",
            error
        )

        interviews = []

    finally:

        connection.close()

    total_interviews = len(
        interviews
    )

    if total_interviews > 0:

        scores = [

            interview["score"] or 0

            for interview in interviews

        ]

        average_score = round(
            sum(scores) / len(scores),
            1
        )

        highest_score = max(scores)

        lowest_score = min(scores)

    else:

        average_score = 0

        highest_score = 0

        lowest_score = 0

    return render_template(

        "analytics.html",

        interviews=interviews,

        total_interviews=total_interviews,

        average_score=average_score,

        highest_score=highest_score,

        lowest_score=lowest_score
    )


# ============================================================
# HR INTERVIEW
# ============================================================

@app.route("/hr")
def hr():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    session["interview_role"] = (
        "HR Interview"
    )

    session["interview_difficulty"] = (
        "Medium"
    )

    session["interview_experience"] = (
        "Fresher"
    )

    session["interview_type"] = (
        "HR Interview"
    )

    session["questions"] = []

    session["answers"] = []

    session["question_number"] = 0

    session["result_saved"] = False

    return redirect(
        url_for("mock_interview")
    )


# ============================================================
# PRACTICE
# ============================================================

@app.route(
    "/practice",
    methods=["GET", "POST"]
)
def practice():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    practice_questions = {

        "Python": [

            "What is Python and why is it widely used?",

            "What is the difference between a list and a tuple?",

            "What is a Python dictionary?",

            "What is a function in Python?",

            "What is the difference between == and = in Python?"

        ],

        "Data Analyst": [

            "What is data analysis?",

            "What is the difference between mean and median?",

            "What is Pandas used for?",

            "What is a DataFrame?",

            "Why is data visualization important?"

        ],

        "HR": [

            "Tell me about yourself.",

            "What are your strengths?",

            "What is your biggest weakness?",

            "Why should we hire you?",

            "Where do you see yourself in five years?"

        ],

        "General Interview": [

            "Tell me about yourself.",

            "Why do you want this job?",

            "What are your strengths?",

            "How do you handle pressure?",

            "Why should we select you?"

        ]

    }

    if request.method == "POST":

        category = request.form.get(
            "category"
        )

        if category not in practice_questions:

            category = "General Interview"

        session["practice_category"] = category

        session["practice_questions"] = (
            practice_questions[category]
        )

        session["practice_answers"] = []

        session["practice_question_number"] = 0

        return redirect(
            url_for("practice_question")
        )

    return render_template(

        "practice.html",

        categories=list(
            practice_questions.keys()
        )
    )


# ============================================================
# PRACTICE QUESTIONS
# ============================================================

@app.route(
    "/practice-question",
    methods=["GET", "POST"]
)
def practice_question():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    questions = session.get(
        "practice_questions",
        []
    )

    if not questions:

        return redirect(
            url_for("practice")
        )

    question_number = session.get(
        "practice_question_number",
        0
    )

    if request.method == "POST":

        answer = request.form.get(
            "answer",
            ""
        ).strip()

        if not answer:

            answer = "No answer provided."

        answers = session.get(
            "practice_answers",
            []
        )

        answers.append(answer)

        session["practice_answers"] = answers

        question_number += 1

        session["practice_question_number"] = (
            question_number
        )

        if question_number >= len(questions):

            return redirect(
                url_for("practice_complete")
            )

    current_question = questions[
        question_number
    ]

    return render_template(

        "practice_question.html",

        question=current_question,

        question_number=(
            question_number + 1
        ),

        total_questions=len(questions),

        category=session.get(
            "practice_category",
            "General Interview"
        )
    )


# ============================================================
# PRACTICE AI FEEDBACK
# ============================================================

def evaluate_practice(
    category,
    questions,
    answers
):

    if not client:

        return """
Score: 0

Overall Performance:
AI feedback is unavailable because the OpenAI API key was not found.

Strengths:
Your answers were recorded successfully.

Weaknesses:
AI evaluation could not be completed.

Areas for Improvement:
Check your OPENAI_API_KEY inside the .env file.

Final Advice:
Configure the API key and try the practice again.
"""

    practice_text = ""

    for i in range(
        min(
            len(questions),
            len(answers)
        )
    ):

        practice_text += f"""

Question {i + 1}:
{questions[i]}

Student Answer:
{answers[i]}

"""

    prompt = f"""
You are an AI interview coach.

Evaluate this practice session.

Category:
{category}

{practice_text}

Give useful feedback to the student.

Use exactly these sections:

Overall Performance

Score: X

Strengths

Weaknesses

Areas for Improvement

Question-by-Question Feedback

Final Advice

The score must be between 0 and 100.

Write the score exactly like:

Score: 80

Be encouraging but honest.
"""

    try:

        response = client.chat.completions.create(

            model="gpt-4o-mini",

            messages=[

                {
                    "role": "system",
                    "content":
                    "You are an expert interview coach."
                },

                {
                    "role": "user",
                    "content": prompt
                }

            ],

            temperature=0.5
        )

        return response.choices[
            0
        ].message.content

    except Exception as error:

        print(
            "❌ PRACTICE AI ERROR:",
            error
        )

        return """
Score: 0

Overall Performance:
Unable to generate AI feedback.

Strengths:
Your answers were recorded.

Weaknesses:
AI evaluation could not be completed.

Areas for Improvement:
Check your OpenAI API key and internet connection.

Final Advice:
Try the practice session again.
"""


# ============================================================
# PRACTICE COMPLETE
# ============================================================

@app.route("/practice-complete")
def practice_complete():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    category = session.get(
        "practice_category",
        "General Interview"
    )

    answers = session.get(
        "practice_answers",
        []
    )

    questions = session.get(
        "practice_questions",
        []
    )

    # Generate AI feedback
    feedback = evaluate_practice(

        category,

        questions,

        answers
    )

    # Extract score
    practice_score = extract_score(
        feedback
    )

    return render_template(

        "practice_complete.html",

        category=category,

        answers=answers,

        questions=questions,

        total_questions=len(questions),

        feedback=feedback,

        score=practice_score
    )


# ============================================================
# RESUME ANALYSIS
# ============================================================

@app.route("/resume-analysis")
def resume_analysis():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    return render_template(
        "resume_analysis.html"
    )


# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":

    create_interview_table()

    print("")
    print("========================================")
    print("       AI INTERVIEW PLATFORM")
    print("========================================")

    if API_KEY:

        print("✅ OpenAI API key loaded")

    else:

        print("⚠️ OpenAI API key NOT loaded")

    print("")

    print(
        "🌐 http://127.0.0.1:5000"
    )

    print("")

    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True
    )