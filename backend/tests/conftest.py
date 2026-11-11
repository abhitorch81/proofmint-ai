import os
os.environ['DATABASE_URL']='sqlite://'
os.environ['RECEIPT_SIGNING_SECRET']='test-only-secret'
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
import pytest
from app.main import app
from app.db import Base, get_db
engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
Session=sessionmaker(bind=engine,expire_on_commit=False)
@pytest.fixture
def client():
    Base.metadata.create_all(engine)
    def override():
        with Session() as db: yield db
    app.dependency_overrides[get_db]=override
    with TestClient(app) as c: yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
