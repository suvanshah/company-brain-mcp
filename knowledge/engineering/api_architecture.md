# API Architecture

## Overview
Our API follows RESTful principles with JSON responses.

## Authentication
- OAuth 2.0 for all endpoints
- API keys for service-to-service communication
- Rate limiting: 1000 requests/minute per user

## Endpoints

### Public Endpoints
- `GET /api/v1/products` - List products
- `GET /api/v1/products/{id}` - Get product details

### Authenticated Endpoints
- `POST /api/v1/orders` - Create order
- `GET /api/v1/orders/{id}` - Get order status
- `PUT /api/v1/orders/{id}` - Update order

### Admin Endpoints
- `GET /api/v1/admin/users` - List users
- `POST /api/v1/admin/users` - Create user
- `DELETE /api/v1/admin/users/{id}` - Delete user

## Response Format
All responses follow this structure:
```json
{
  "data": {},
  "meta": {
    "timestamp": "2024-01-01T00:00:00Z",
    "request_id": "uuid"
  }
}
```

## Error Handling
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 500: Internal Server Error
