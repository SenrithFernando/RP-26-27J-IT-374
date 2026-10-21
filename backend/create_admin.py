"""Interactive local command for creating the first SafeRide administrator."""

from getpass import getpass

from backend.database import initialize_database
from backend.users import create_administrator


def main() -> None:
    print("Create SafeRide-LK administrator")
    full_name = input("Full name: ").strip()
    email = input("Email: ").strip()
    password = getpass("Password (minimum 10 characters): ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match. No account was created.")

    try:
        initialize_database()
        user = create_administrator(full_name, email, password)
    except (RuntimeError, ValueError) as error:
        raise SystemExit(f"Account was not created: {error}") from error
    print(f"Administrator ready: {user['email']}")


if __name__ == "__main__":
    main()
