# Project Instructions

## Stack

- Python
- Flask
- PostgreSQL
- SQLAlchemy
- Flask-Migrate
- pytest
- HTML
- CSS
- Vanilla JavaScript

## Architecture

Use the application factory pattern.

Business logic belongs in `app/services/`.

Database models belong in `app/models/`.

HTTP routes and request validation belong in `app/routes/`.

Templates belong in `app/templates/`.

Frontend JavaScript belongs in `app/static/js/`.

CSS belongs in `app/static/css/`.

Routes must not contain complex business logic.

## Database

PostgreSQL is the primary database.

Never use SQLite as a production fallback.

Database credentials must come from environment variables.

Use Flask-Migrate/Alembic for database schema changes.

Do not manually modify production database tables when a migration should be used.

## Security

Never hardcode passwords, secrets, database credentials, or API keys.

Never commit `.env` files.

Do not expose sensitive configuration values in frontend code.

## Testing

New business functionality should include tests when practical.

Existing functionality should not be intentionally broken.

Tests must run against PostgreSQL. Use `TEST_DATABASE_URL` for the test database.

Never use SQLite as a test database fallback.

## Code changes

Avoid modifying unrelated files.

Prefer small and focused changes.

Do not introduce new dependencies without explaining why.

Do not modify models, database migrations, or backend endpoints unless the task requires it.

Before making significant changes, inspect the existing implementation.

Preserve existing working behavior unless explicitly instructed otherwise.

## Harvest tracking system

The application is an agricultural harvest tracking system designed to work with USB barcode scanners.

Each worker has a unique barcode. During the day, a worker can register multiple harvest entries (tandas de cosecha).

The primary workflow is:

1. Scan or enter the worker's barcode.
2. Press Enter.
3. Find the worker.
4. Display worker information and daily accumulated weight.
5. Focus the weight field.
6. Enter the weight in kg for the new batch.
7. Press Enter or click the registration button.
8. Register the harvest entry.
9. Show confirmation with the new daily total.
10. Return focus to the barcode field.

This keyboard-first workflow must be preserved.

Weight values use Decimal precision (Numeric 10,3).

The daily total is calculated using a date range converted to UTC,
not a simple DATE() comparison.

## Communication

Before making broad or architectural changes:

1. Explain what you plan to change.
2. Identify the files you intend to modify.
3. Avoid unrelated refactors.
