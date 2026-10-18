"""Local insert-only landmark scenario setup; no geocoding or account reassignment."""
from sqlalchemy.orm import Session
from database import get_engine
from landmark import setup
if __name__=='__main__':
    with Session(get_engine()) as session:print(setup(session))
