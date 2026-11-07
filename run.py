import sys
import argparse
from app import create_app
from extensions import db, socketio
from scripts.seed_data import seed_database

app = create_app()

def main():
    parser = argparse.ArgumentParser(description="MediQueue - Smart Hospital Queue Optimization System")
    parser.add_argument('--seed', action='store_true', help="Initialize and seed demo database with realistic hackathon data")
    parser.add_argument('--reset', action='store_true', help="Reset existing database and reseed")
    parser.add_argument('--port', type=int, default=5000, help="Port to run server on (default 5000)")
    parser.add_argument('--host', type=str, default='127.0.0.1', help="Host address (default 127.0.0.1)")

    args = parser.parse_args()

    with app.app_context():
        # Ensure database tables exist
        db.create_all()

        if args.seed or args.reset:
            print("[INFO] Seeding MediQueue database with demo accounts & records...")
            seed_database(force_reset=args.reset)
            print("[SUCCESS] Database successfully seeded.")

    print(f"\n=======================================================")
    print(f" MediQueue Hospital Management & Queue System")
    print(f" TECHNOVATE 2.0 - Problem Statement 13")
    print(f" Server running at: http://{args.host}:{args.port}")
    print(f" Default Admin: admin / Admin@123")
    print(f" Default Staff: staff / Staff@123")
    print(f" Default Patient: patient / Patient@123")
    print(f"=======================================================\n")

    socketio.run(app, host=args.host, port=args.port, debug=True, allow_unsafe_werkzeug=True)

if __name__ == '__main__':
    main()
