-- Add BANK_CARD to PostgreSQL entity_type enum.
--
-- Python:
--     EntityType.BANK_CARD = "bank_card"
--
-- PostgreSQL SQLAlchemy Enum stores the enum member NAME:
--     BANK_CARD

ALTER TYPE entity_type
ADD VALUE IF NOT EXISTS 'BANK_CARD';
