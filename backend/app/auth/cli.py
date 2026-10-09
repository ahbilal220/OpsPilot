import argparse
import asyncio

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth.models import Role, User
from app.core.config import Settings


async def set_user_role(email: str, role: Role) -> bool:
    settings = Settings()
    engine = create_async_engine(settings.database_url.get_secret_value())
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            user = await session.scalar(
                select(User).where(func.lower(User.email) == email.strip().lower())
            )
            if user is None:
                return False
            user.role = role
            await session.commit()
            return True
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="OpsPilot operator commands")
    commands = parser.add_subparsers(dest="command", required=True)
    set_role = commands.add_parser("set-role", help="set an existing user's role")
    set_role.add_argument("email")
    set_role.add_argument("role", choices=[role.value for role in Role])
    args = parser.parse_args()

    if args.command == "set-role":
        role = Role(args.role)
        if not asyncio.run(set_user_role(args.email, role)):
            parser.error(f"user not found: {args.email}")
        print(f"Updated {args.email.strip().lower()} to role {role.value}")


if __name__ == "__main__":
    main()
