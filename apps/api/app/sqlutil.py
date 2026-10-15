from sqlalchemy import select
from sqlalchemy.orm import Session


def select_orm_stmt(model, *where):
    return select(model).where(*where)


def select_orm(db: Session, model, *where):
    return db.scalars(select(model).where(*where)).all()
