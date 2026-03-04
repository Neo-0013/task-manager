from app import create_app, db
from app.schema import ensure_sqlite_schema

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        ensure_sqlite_schema(db)
    app.run(debug=True)