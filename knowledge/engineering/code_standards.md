# Code Standards

## Python
- Follow PEP 8 style guide
- Use type hints for all function signatures
- Maximum line length: 100 characters
- Use docstrings for all public functions

## JavaScript
- Use ESLint for linting
- Prefer const/let over var
- Use arrow functions for callbacks
- 2-space indentation

## Database
- Use snake_case for table names
- Use PascalCase for column names
- Always include created_at and updated_at timestamps
- Use foreign keys with ON DELETE CASCADE

## Git
- Commit messages should be in imperative mood
- Branch naming: feature/description, bugfix/description
- Pull requests require at least one approval
- All code must pass CI before merging

## Testing
- Minimum 80% code coverage
- Unit tests for all public functions
- Integration tests for API endpoints
- E2E tests for critical user flows
