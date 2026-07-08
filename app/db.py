"""
Database connection utilities.
We expose a SQLAlchemy engine that can be reused across scripts and API routes.
"""

from sqlalchemy import create_engine
from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL)