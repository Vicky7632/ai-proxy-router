from app.db.session import SessionLocal
from app.db.models.provider import Provider

db = SessionLocal()

# Check karo pehle se exist to nahi karta
existing = db.query(Provider).filter(Provider.name == "groq").first()

if existing:
    print("Groq provider already exists, skipping.")
else:
    groq = Provider(
        name="groq",
        base_url="https://api.groq.com/openai/v1",
        priority=1,
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0,
        is_active=True,
    )
    db.add(groq)
    db.commit()
    print("Seeded Groq provider successfully.")

db.close()