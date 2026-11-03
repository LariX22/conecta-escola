"""Regras de negócio para escolas (tenants)."""
from sqlalchemy.orm import Session

from app.models.school import School
from app.schemas.school import SchoolCreateRequest


class SlugAlreadyExistsError(Exception):
    pass


def create_school(db: Session, data: SchoolCreateRequest) -> School:
    if db.query(School).filter(School.slug == data.slug).first():
        raise SlugAlreadyExistsError(f"Já existe uma escola com o identificador: {data.slug}")

    school = School(name=data.name, slug=data.slug)
    db.add(school)
    db.commit()
    db.refresh(school)
    return school


def get_school(db: Session, school_id) -> School | None:
    return db.query(School).filter(School.id == school_id).first()
