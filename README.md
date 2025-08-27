# Order Management System

A modern Django-based order management system with real-time WebSocket notifications.

## Features

- **User Management**: Role-based access (Client, Worker, Admin)
- **Order Management**: Complete order lifecycle with status tracking
- **Real-time Notifications**: WebSocket-based updates
- **RESTful API**: Comprehensive API with JWT authentication
- **Admin Interface**: Advanced admin panel with custom actions

## Architecture

- **Django 5.2+** with Django REST Framework
- **Django Channels** for WebSocket support
- **PostgreSQL** database
- **JWT Authentication** with Simple JWT
- **Service Layer** pattern for business logic
- **Comprehensive Error Handling** with custom exceptions

## Quick Start

1. **Clone and Setup**:
   ```bash
   git clone <repository>
   cd Humo_test_task
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Environment Variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your database and secret key
   ```

3. **Database Setup**:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   python manage.py createsuperuser
   ```

4. **Run Development Server**:
   ```bash
   python manage.py runserver
   ```

## API Endpoints

- **Users**: `/api/v1/users/`
- **Orders**: `/api/v1/orders/`
- **WebSocket**: `ws://localhost:8000/ws/orders/`

## WebSocket Testing

Use tools like Postman or wscat to test WebSocket connections:

```bash
wscat -c "ws://localhost:8000/ws/orders/?token=YOUR_JWT_TOKEN"
```

## Production Deployment

- Use Redis for channel layers
- Configure proper CORS settings
- Set up logging and monitoring
- Use environment variables for secrets

## Testing

```bash
pytest
coverage run -m pytest
coverage report
```

## Code Quality

```bash
black .
flake8
isort .
```

## License

MIT License
