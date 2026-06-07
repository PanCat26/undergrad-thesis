import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def create_guest_user(session: AsyncSession) -> User:
    user = User(is_guest=True)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def get_or_create_cognito_user(
    session: AsyncSession, cognito_sub: str, email: str | None
) -> User:
    result = await session.execute(select(User).where(User.cognito_sub == cognito_sub))
    user = result.scalar_one_or_none()
    if user is not None:
        if email and user.email != email:
            user.email = email
            await session.commit()
        return user

    user = User(cognito_sub=cognito_sub, email=email, is_guest=False)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def delete_user(session: AsyncSession, user: User) -> None:
    await session.delete(user)
    await session.commit()
