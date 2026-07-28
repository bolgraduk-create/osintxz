"""
Telegram collector exceptions.

Custom exceptions used by the Telegram collection module.

Responsibilities:

- provide typed exceptions
- improve error handling
- keep parser code clean

Does NOT:

- log errors
- recover from errors
"""


from __future__ import annotations


class TelegramCollectorError(Exception):
    """
    Base Telegram collector exception.
    """


class TelegramExportNotFoundError(
    TelegramCollectorError,
):
    """
    Telegram export file was not found.
    """


class TelegramExportFormatError(
    TelegramCollectorError,
):
    """
    Telegram export has invalid format.
    """


class TelegramExportVersionError(
    TelegramCollectorError,
):
    """
    Unsupported Telegram export version.
    """


class TelegramMessageParseError(
    TelegramCollectorError,
):
    """
    Failed to parse Telegram message.
    """


class TelegramUserParseError(
    TelegramCollectorError,
):
    """
    Failed to parse Telegram user.
    """


class TelegramAttachmentParseError(
    TelegramCollectorError,
):
    """
    Failed to parse Telegram attachment.
    """


class TelegramChatParseError(
    TelegramCollectorError,
):
    """
    Failed to parse Telegram chat.
    """