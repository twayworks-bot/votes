from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import DATABASE_URL

# SQLite 멀티스레드 지원 설정
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """데이터베이스 세션 의존성 주입 제너레이터"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """테이블 초기화 및 생성, 기존 테이블에 대한 안전한 컬럼 마이그레이션"""
    import app.models.event  # noqa: F401
    import app.models.item   # noqa: F401
    from sqlalchemy import inspect, text

    Base.metadata.create_all(bind=engine)

    # SQLite 컬럼 마이그레이션 처리
    inspector = inspect(engine)
    if "event_items" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("event_items")]
        with engine.connect() as conn:
            if "media_type" not in columns:
                conn.execute(text("ALTER TABLE event_items ADD COLUMN media_type VARCHAR(20) DEFAULT 'image' NOT NULL"))
            if "video_id" not in columns:
                conn.execute(text("ALTER TABLE event_items ADD COLUMN video_id VARCHAR(64)"))
            if "video_stream_url" not in columns:
                conn.execute(text("ALTER TABLE event_items ADD COLUMN video_stream_url VARCHAR(500)"))
            if "video_status" not in columns:
                conn.execute(text("ALTER TABLE event_items ADD COLUMN video_status VARCHAR(30) DEFAULT 'COMPLETED'"))
            if "video_duration" not in columns:
                conn.execute(text("ALTER TABLE event_items ADD COLUMN video_duration INTEGER"))
            conn.commit()

