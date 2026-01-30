from aiogram.filters import Filter
from aiogram.types import Message
from typing import List

class RoleFilter(Filter):
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    async def __call__(self, message: Message, role: str) -> bool:
        return role in self.allowed_roles
