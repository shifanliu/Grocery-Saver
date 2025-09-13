from dotenv import load_dotenv
load_dotenv()

from app.database import Base, engine, DATABASE_URL
from app import models

print("Using DB:", DATABASE_URL)

print("Creating tables...")
Base.metadata.create_all(bind=engine)
print("Tables created.")
