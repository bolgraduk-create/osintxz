"""
Telegram collector domain models.

Internal Telegram representation.

These models are independent from the database
and are used by the Telegram Intelligence module.

Pipeline:

Telegram Export
        ↓
TelegramParser
        ↓
TelegramModels
        ↓
TelegramMapper
        ↓
CollectedItem
        ↓
Evidence

Responsibilities:

- represent Telegram export
- provide typed structures
- keep parser independent from ORM

Does NOT:

- access database
- perform parsing
- perform AI
- create Evidence
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ==========================================================
# ENUMS
# ==========================================================


class TelegramChatType(str, Enum):
    PRIVATE = "private"
    GROUP = "group"
    SUPERGROUP = "supergroup"
    CHANNEL = "channel"
    UNKNOWN = "unknown"


class TelegramMediaType(str, Enum):
    NONE = "none"

    PHOTO = "photo"
    VIDEO = "video"
    VIDEO_NOTE = "video_note"

    AUDIO = "audio"
    VOICE = "voice"

    DOCUMENT = "document"

    STICKER = "sticker"

    GIF = "gif"

    LOCATION = "location"

    CONTACT = "contact"

    POLL = "poll"

    VENUE = "venue"

    GAME = "game"

    ANIMATION = "animation"

    UNKNOWN = "unknown"


class TelegramMessageType(str, Enum):

    TEXT = "text"

    SERVICE = "service"

    PHOTO = "photo"

    VIDEO = "video"

    AUDIO = "audio"

    DOCUMENT = "document"

    STICKER = "sticker"

    GIF = "gif"

    LOCATION = "location"

    CONTACT = "contact"

    POLL = "poll"

    UNKNOWN = "unknown"


class TelegramEntityType(str, Enum):

    BOLD = "bold"

    ITALIC = "italic"

    URL = "url"

    EMAIL = "email"

    PHONE = "phone"

    MENTION = "mention"

    HASHTAG = "hashtag"

    BOT_COMMAND = "bot_command"

    CODE = "code"

    PRE = "pre"

    TEXT_LINK = "text_link"

    SPOILER = "spoiler"

    CUSTOM_EMOJI = "custom_emoji"

    UNKNOWN = "unknown"


# ==========================================================
# BASIC STRUCTURES
# ==========================================================


@dataclass(slots=True)
class TelegramReaction:
    """
    Message reaction.
    """

    emoji: str

    count: int = 1


@dataclass(slots=True)
class TelegramEntity:
    """
    Rich text entity.
    """

    type: TelegramEntityType

    offset: int

    length: int

    value: str | None = None


@dataclass(slots=True)
class TelegramLocation:
    """
    Geographic location.
    """

    latitude: float

    longitude: float

    title: str | None = None

    address: str | None = None


@dataclass(slots=True)
class TelegramContact:
    """
    Shared contact.
    """

    first_name: str | None = None

    last_name: str | None = None

    phone_number: str | None = None

    user_id: str | None = None


@dataclass(slots=True)
class TelegramPollOption:

    text: str

    votes: int = 0


@dataclass(slots=True)
class TelegramPoll:

    question: str

    options: list[TelegramPollOption] = field(
        default_factory=list
    )

    multiple_answers: bool = False

    anonymous: bool = True


# ==========================================================
# USERS
# ==========================================================


@dataclass(slots=True)
class TelegramUser:
    """
    Telegram participant.
    """

    id: str | None = None

    username: str | None = None

    phone: str | None = None

    first_name: str | None = None

    last_name: str | None = None

    display_name: str | None = None

    is_bot: bool = False

    is_deleted: bool = False

    is_scam: bool = False

    is_fake: bool = False

    is_verified: bool = False

    is_premium: bool = False

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


# ==========================================================
# MEDIA
# ==========================================================


@dataclass(slots=True)
class TelegramAttachment:
    """
    Generic attachment.
    """

    type: TelegramMediaType

    file_path: str | None = None

    file_name: str | None = None

    mime_type: str | None = None

    size: int | None = None

    width: int | None = None

    height: int | None = None

    duration: float | None = None

    thumbnail: str | None = None

    caption: str | None = None

    performer: str | None = None

    title: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


# ==========================================================
# FORWARDS
# ==========================================================


@dataclass(slots=True)
class TelegramForwardInfo:

    from_name: str | None = None

    from_id: str | None = None

    from_chat: str | None = None

    date: datetime | None = None


# ==========================================================
# REPLIES
# ==========================================================


@dataclass(slots=True)
class TelegramReplyInfo:

    message_id: int | None = None

    sender_id: str | None = None

# ==========================================================
# MESSAGE
# ==========================================================


@dataclass(slots=True)
class TelegramMessage:
    """
    Telegram message.
    """

    # ---------- Identity ----------

    id: int

    internal_id: str | None = None

    chat_id: str | None = None

    chat_title: str | None = None

    # ---------- Sender ----------

    sender: TelegramUser | None = None

    sender_id: str | None = None

    sender_name: str | None = None

    author: str | None = None

    via_bot: str | None = None

    # ---------- Time ----------

    timestamp: datetime | None = None

    edit_timestamp: datetime | None = None

    # ---------- Content ----------

    message_type: TelegramMessageType = (
        TelegramMessageType.TEXT
    )

    text: str = ""

    raw_text: str = ""

    normalized_text: str = ""

    language: str | None = None

    # ---------- Thread ----------

    reply: TelegramReplyInfo | None = None

    thread_id: int | None = None

    # ---------- Forward ----------

    forward: TelegramForwardInfo | None = None

    # ---------- Media ----------

    attachments: list[
        TelegramAttachment
    ] = field(
        default_factory=list
    )

    # ---------- Rich Text ----------

    entities: list[
        TelegramEntity
    ] = field(
        default_factory=list
    )

    # ---------- Reactions ----------

    reactions: list[
        TelegramReaction
    ] = field(
        default_factory=list
    )

    # ---------- Poll ----------

    poll: TelegramPoll | None = None

    # ---------- Contact ----------

    contact: TelegramContact | None = None

    # ---------- Location ----------

    location: TelegramLocation | None = None

    # ---------- Flags ----------

    edited: bool = False

    pinned: bool = False

    outgoing: bool = False

    incoming: bool = False

    service: bool = False

    silent: bool = False

    scheduled: bool = False

    mentioned: bool = False

    media_spoiler: bool = False

    # ---------- Statistics ----------

    views: int | None = None

    forwards: int | None = None

    replies_count: int | None = None

    reaction_count: int | None = None

    # ---------- Files ----------

    media_group_id: str | None = None

    file_id: str | None = None

    file_unique_id: str | None = None

    # ---------- AI ----------

    keywords: list[str] = field(
        default_factory=list
    )

    detected_entities: list[str] = field(
        default_factory=list
    )

    sentiment: str | None = None

    summary: str | None = None

    embedding_id: str | None = None

    # ---------- Relationships ----------

    linked_messages: list[int] = field(
        default_factory=list
    )

    linked_users: list[str] = field(
        default_factory=list
    )

    linked_documents: list[str] = field(
        default_factory=list
    )

    linked_locations: list[str] = field(
        default_factory=list
    )

    # ---------- Metadata ----------

    metadata: dict[str, Any] = field(
        default_factory=dict
    )



    # ==========================================================
# CHAT
# ==========================================================


@dataclass(slots=True)
class TelegramChat:
    """
    Telegram chat.
    """

    id: str | None = None

    title: str = ""

    username: str | None = None

    chat_type: TelegramChatType = (
        TelegramChatType.PRIVATE
    )

    description: str | None = None

    invite_link: str | None = None

    members_count: int | None = None

    created_at: datetime | None = None

    users: list[TelegramUser] = field(
        default_factory=list
    )

    messages: list[TelegramMessage] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


# ==========================================================
# EXPORT
# ==========================================================


@dataclass(slots=True)
class TelegramExport:
    """
    Complete Telegram export.
    """

    source: str = ""

    exported_at: datetime | None = None

    version: str | None = None

    chats: list[TelegramChat] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    @property
    def messages(self) -> list[TelegramMessage]:
        """
        Returns all messages.
        """

        result: list[TelegramMessage] = []

        for chat in self.chats:
            result.extend(chat.messages)

        return result

    @property
    def users(self) -> list[TelegramUser]:
        """
        Returns unique users.
        """

        users: dict[str, TelegramUser] = {}

        for chat in self.chats:

            for user in chat.users:

                key = (
                    user.id
                    or user.username
                    or user.full_name
                )

                if key:
                    users[key] = user

        return list(users.values())

    @property
    def chat_count(self) -> int:
        return len(self.chats)

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def user_count(self) -> int:
        return len(self.users)