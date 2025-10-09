"""Helpers to connect MessageRouter flows to Mongo-backed storage."""

from __future__ import annotations

from typing import Any, Dict

from chef.chefmain.message_router import MessageRouter
from chef.utilities.history_messages import (
    get_full_history_message_object,
    message_history_process,
)

from .repository import MongoChatRepository

MessageObject = Dict[str, Any]


def route_message_with_persistence(
    router: MessageRouter,
    message_object: MessageObject,
    repository: MongoChatRepository,
) -> str:
    """Route a message through the existing router and persist the resulting history."""

    user_id = str(message_object.get("user_id"))
    if not user_id:
        raise ValueError("message_object must include user_id")

    # Let the existing history utility capture the message locally so router sees prior context.
    message_history_process(message_object)

    # Route the message via existing logic.
    response = router.route_message(message_object=message_object)

    # Pull the full history that router/utility just updated and push to Mongo.
    history = get_full_history_message_object(user_id)
    if history:
        repository.upsert_session(history)
    return response


def persist_existing_history(user_id: str, repository: MongoChatRepository) -> None:
    """Load any existing on-disk history for the given user and save it to MongoDB."""

    history = get_full_history_message_object(str(user_id))
    if history:
        repository.upsert_session(history)


__all__ = [
    "route_message_with_persistence",
    "persist_existing_history",
]
