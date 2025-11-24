from sqlalchemy import Column, Integer, String, Boolean
from app.db.base_class import Base

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    xtream_url = Column(String, nullable=False)
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)
    movies_dir = Column(String, nullable=False)
    series_dir = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
