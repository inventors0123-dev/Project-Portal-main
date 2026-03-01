from app import init_db


if __name__ == "__main__":
    if init_db is None:
        raise RuntimeError("init_db function was not found in application module.")
    init_db()
    print("Database tables created (if missing).")
