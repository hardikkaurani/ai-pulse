"""Synthetic demo data. Idempotent: never drops or resets an existing database."""

import argparse
from .db import SessionLocal
from . import models, config
from .auth import hash_password
from .services.questions import questions_for, question_version
from .services.actions import create_plan

PEOPLE = [
    (
        "Asha Rao",
        "asha@northwind.test",
        "Northwind Logistics",
        None,
        "admin",
        "manager",
        "lead",
    ),
    (
        "Meera Pillai",
        "meera@bluepeak.test",
        "Bluepeak Retail",
        None,
        "admin",
        "manager",
        "lead",
    ),
    (
        "Ravi Kapoor",
        "ravi@consult.test",
        "Northwind Logistics",
        "HR",
        "employee",
        "manager",
        "senior",
    ),
    (
        "Ravi Kapoor",
        "ravi@consult.test",
        "Bluepeak Retail",
        None,
        "admin",
        "manager",
        "senior",
    ),
    (
        "Priya Nair",
        "priya@northwind.test",
        "Northwind Logistics",
        "Support",
        "employee",
        "support",
        "junior",
    ),
    (
        "Arjun Iyer",
        "arjun@northwind.test",
        "Northwind Logistics",
        "Support",
        "employee",
        "support",
        "senior",
    ),
    (
        "Kavitha Menon",
        "kavitha@northwind.test",
        "Northwind Logistics",
        "Support",
        "employee",
        "support",
        "mid",
    ),
    (
        "Maya Das",
        "maya@northwind.test",
        "Northwind Logistics",
        "Support",
        "employee",
        "support",
        "mid",
    ),
    (
        "Ishaan Sen",
        "ishaan@northwind.test",
        "Northwind Logistics",
        "Support",
        "employee",
        "support",
        "junior",
    ),
    (
        "New Participant",
        "new@northwind.test",
        "Northwind Logistics",
        "Support",
        "employee",
        "support",
        "junior",
    ),
    (
        "Dev Malhotra",
        "dev@northwind.test",
        "Northwind Logistics",
        "Engineering",
        "employee",
        "engineering",
        "lead",
    ),
    (
        "Sara Thomas",
        "sara@northwind.test",
        "Northwind Logistics",
        "Engineering",
        "employee",
        "engineering",
        "mid",
    ),
    (
        "Aarav Shah",
        "aarav@northwind.test",
        "Northwind Logistics",
        "Engineering",
        "employee",
        "engineering",
        "senior",
    ),
    (
        "Zoya Khan",
        "zoya@northwind.test",
        "Northwind Logistics",
        "Engineering",
        "employee",
        "engineering",
        "mid",
    ),
    (
        "Anika Rao",
        "anika@northwind.test",
        "Northwind Logistics",
        "Engineering",
        "employee",
        "engineering",
        "junior",
    ),
    (
        "Rhea Jain",
        "rhea@northwind.test",
        "Northwind Logistics",
        "Engineering",
        "employee",
        "engineering",
        "senior",
    ),
    (
        "Vikram Shah",
        "vikram@northwind.test",
        "Northwind Logistics",
        "Sales",
        "employee",
        "sales",
        "senior",
    ),
    (
        "Neha Gupta",
        "neha@northwind.test",
        "Northwind Logistics",
        "Sales",
        "employee",
        "sales",
        "junior",
    ),
    (
        "Rohan Mehta",
        "rohan@northwind.test",
        "Northwind Logistics",
        "Sales",
        "employee",
        "sales",
        "mid",
    ),
    (
        "Imran Khan",
        "imran@northwind.test",
        "Northwind Logistics",
        "HR",
        "employee",
        "manager",
        "senior",
    ),
    (
        "Tom Fernandes",
        "tom@bluepeak.test",
        "Bluepeak Retail",
        "Stores",
        "employee",
        "sales",
        "mid",
    ),
    (
        "Lina George",
        "lina@bluepeak.test",
        "Bluepeak Retail",
        "Stores",
        "employee",
        "sales",
        "junior",
    ),
    (
        "Kabir Das",
        "kabir@bluepeak.test",
        "Bluepeak Retail",
        "Customer Care",
        "employee",
        "support",
        "senior",
    ),
]


def run(db=None):
    own = db is None
    db = db or SessionLocal()
    try:
        if db.query(models.User).first():
            return False
        orgs, departments = {}, {}
        for name, teams in [
            ("Northwind Logistics", ["Sales", "Support", "Engineering", "HR"]),
            ("Bluepeak Retail", ["Stores", "Customer Care"]),
        ]:
            org = models.Organization(name=name)
            db.add(org)
            db.flush()
            orgs[name] = org
            for team in teams:
                department = models.Department(org_id=org.id, name=team)
                db.add(department)
                db.flush()
                departments[(name, team)] = department.id
        users = {}
        for i, (name, email, org, team, role, job, seniority) in enumerate(PEOPLE):
            if email not in users:
                user = models.User(
                    name=name, email=email, password_hash=hash_password("pulse123")
                )
                db.add(user)
                db.flush()
                users[email] = user
            member = models.Membership(
                user_id=users[email].id,
                org_id=orgs[org].id,
                department_id=departments.get((org, team)),
                role=role,
                job_role=job,
                seniority=seniority,
            )
            db.add(member)
            db.flush()
            if role == "admin" or email.startswith("new@"):
                continue
            questions = questions_for(job, seniority)
            assessment = models.Assessment(
                membership_id=member.id,
                status="completed",
                fingerprint=f"synthetic-{member.id}",
                question_version=question_version(),
                question_snapshot=questions,
                ai_mode="mock",
                model="demo-fixture",
                prompt_version=config.PROMPT_VERSION,
            )
            db.add(assessment)
            db.flush()
            rows = []
            for q in questions:
                value = (4 if team == "Engineering" else 2) + (i % 2)
                if q["type"] == "mcq":
                    option = q["options"][min(value - 1, len(q["options"]) - 1)]
                    answer, score = option["text"], option["points"]
                else:
                    answer, score = (
                        "Synthetic example: I used an approved AI tool to draft a reply and checked it before use.",
                        3,
                    )
                row = models.Response(
                    membership_id=member.id,
                    assessment_id=assessment.id,
                    question_id=q["id"],
                    answer=answer,
                    score=score,
                    reason="Synthetic demo data; not a real employee evaluation.",
                    flags=[],
                )
                db.add(row)
                rows.append(row)
            create_plan(db, assessment, rows, job)
        db.commit()
        return True
    finally:
        if own:
            db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Create synthetic accounts in an empty database.",
    )
    args = parser.parse_args()
    if not args.demo:
        parser.error("Explicit --demo is required. This never resets existing data.")
    print(
        "Created synthetic demo accounts."
        if run()
        else "Database already has users; nothing changed."
    )
