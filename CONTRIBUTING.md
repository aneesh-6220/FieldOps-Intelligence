# Contributing

Thank you for improving FieldOps Intelligence.

1. Create a focused branch and describe the operating problem being addressed.
2. Keep UI handlers thin; place workflow rules in services and calculations in analytics modules.
3. Use `Decimal` for money and enums for persisted lifecycle values.
4. Add unit tests for formulas and integration tests for transactional behavior.
5. Run `ruff check .`, `ruff format --check .`, `mypy app scripts`, and `pytest` before opening a pull request.
6. Use synthetic data only. Never commit customer records, credentials, database files, or exports.

Changes should remain useful across field-service categories rather than assuming one trade.

