"""Дерекқор кестелері (дипломның 10-кестесі + қызметтік кестелер)."""
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .config import get_settings
from .db import Base

DIM = get_settings().embedding_dim


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(primary_key=True)
    name_kk: Mapped[str] = mapped_column(String(200))
    name_ru: Mapped[str] = mapped_column(String(200))


class User(Base):
    """Жүйеге кіру тіркелгісі. role: employee | manager | hr."""
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(16))
    display_name: Mapped[str] = mapped_column(String(128))
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))


class Employee(Base):
    """Қызметкер: жеке деректер минимумы (аты-жөні орнына бүркеншік код)."""
    __tablename__ = "employees"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    current_role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"))
    target_role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"))
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    department: Mapped[Department] = relationship()
    current_role: Mapped["Role | None"] = relationship(foreign_keys=[current_role_id])
    target_role: Mapped["Role | None"] = relationship(foreign_keys=[target_role_id])


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(32))  # resume | profile | self_assessment
    lang: Mapped[str] = mapped_column(String(8))
    filename: Mapped[str | None] = mapped_column(String(256))
    text: Mapped[str] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Skill(Base):
    """ESCO дағдысы."""
    __tablename__ = "skills"
    esco_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    label_en: Mapped[str] = mapped_column(String(512))
    alt_labels: Mapped[list] = mapped_column(JSON, default=list)
    type: Mapped[str] = mapped_column(String(32))  # skill/competence | knowledge
    reuse_level: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")
    embedding = mapped_column(Vector(DIM), nullable=True)


class SkillLabel(Base):
    """Векторлық индекс жолы: дағдының негізгі немесе балама атауы."""
    __tablename__ = "skill_labels"
    id: Mapped[int] = mapped_column(primary_key=True)
    esco_id: Mapped[str] = mapped_column(ForeignKey("skills.esco_id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(512))
    is_preferred: Mapped[bool] = mapped_column(default=False)
    embedding = mapped_column(Vector(DIM))


class Role(Base):
    """Ұйымдағы рөл (ESCO кәсібімен және ҚР кәсіби стандартымен байланысты)."""
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    esco_occupation_id: Mapped[str | None] = mapped_column(String(128))
    esco_occupation_label: Mapped[str | None] = mapped_column(String(256))
    title_kk: Mapped[str] = mapped_column(String(200))
    title_ru: Mapped[str] = mapped_column(String(200))
    title_en: Mapped[str] = mapped_column(String(200))
    grade: Mapped[int] = mapped_column(Integer, default=2)  # 1 junior … 3 senior
    family: Mapped[str] = mapped_column(String(64), default="")
    description_kk: Mapped[str] = mapped_column(Text, default="")
    description_ru: Mapped[str] = mapped_column(Text, default="")
    prof_standard_ref: Mapped[str] = mapped_column(String(512), default="")

    skills: Mapped[list["RoleSkill"]] = relationship(back_populates="role", cascade="all, delete-orphan")


class RoleSkill(Base):
    __tablename__ = "role_skills"
    __table_args__ = (UniqueConstraint("role_id", "esco_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    esco_id: Mapped[str] = mapped_column(ForeignKey("skills.esco_id"))
    weight: Mapped[float] = mapped_column(Float)
    required_level: Mapped[int] = mapped_column(Integer)
    relation: Mapped[str] = mapped_column(String(16), default="essential")  # essential | optional | expert
    source: Mapped[str] = mapped_column(String(16), default="esco")  # esco | onet | expert

    role: Mapped[Role] = relationship(back_populates="skills")
    skill: Mapped[Skill] = relationship()


class EmployeeSkill(Base):
    __tablename__ = "employee_skills"
    __table_args__ = (UniqueConstraint("employee_id", "esco_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    esco_id: Mapped[str] = mapped_column(ForeignKey("skills.esco_id"))
    level: Mapped[int] = mapped_column(Integer)
    evidence: Mapped[str] = mapped_column(Text, default="")
    phrase: Mapped[str] = mapped_column(String(512), default="")
    source: Mapped[str] = mapped_column(String(16))  # llm | offline | self | manager
    status: Mapped[str] = mapped_column(String(16), default="unconfirmed")  # unconfirmed | confirmed | rejected
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    similarity: Mapped[float] = mapped_column(Float, default=0.0)
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    skill: Mapped[Skill] = relationship()


class Transition(Base):
    __tablename__ = "transitions"
    __table_args__ = (UniqueConstraint("from_role_id", "to_role_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    from_role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    to_role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    count: Mapped[float] = mapped_column(Float, default=0)
    prob: Mapped[float] = mapped_column(Float, default=0)
    source: Mapped[str] = mapped_column(String(32))  # karrierewege | expert | karrierewege+expert


class Course(Base):
    __tablename__ = "courses"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    provider: Mapped[str] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(String(500))
    duration_h: Mapped[float | None] = mapped_column(Float)
    lang: Mapped[str] = mapped_column(String(16), default="en")
    level: Mapped[str] = mapped_column(String(32), default="")
    esco_ids: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(Text, default="")
    is_free: Mapped[bool] = mapped_column(default=True)


class IDP(Base):
    """Жеке даму жоспары. status: draft | submitted | approved | returned."""
    __tablename__ = "idp"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    target_role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    plan_json: Mapped[dict] = mapped_column(JSON)
    generator: Mapped[str] = mapped_column(String(16), default="offline")  # llm | offline
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    manager_comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AuditLog(Base):
    """ЖИ әрекеттері мен шешімдердің журналы."""
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    tool: Mapped[str | None] = mapped_column(String(64))
    employee_id: Mapped[int | None] = mapped_column(Integer)
    input_hash: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class LLMCache(Base):
    __tablename__ = "llm_cache"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    model: Mapped[str] = mapped_column(String(64))
    response: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
