```
cyberiad/
├── README.md
├── requirements.txt
├── .env
├── .gitignore
├── alembic/                    # Database migrations
│   ├── versions/
│   ├── env.py
│   └── alembic.ini
├── src/
│   ├── cyberiad/              # Main package
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI application entry point
│   │   ├── config.py         # Configuration management
│   │   ├── constants.py      # Application constants
│   │   ├── api/              # API endpoints
│   │   │   ├── __init__.py
│   │   │   ├── auth.py       # Authentication routes
│   │   │   ├── threads.py    # Thread management routes
│   │   │   ├── messages.py   # Message routes
│   │   │   ├── agents.py     # Agent routes
│   │   │   └── websocket.py  # WebSocket routes
│   │   ├── core/             # Core functionality
│   │   │   ├── __init__.py
│   │   │   ├── security.py   # Security and rate limiting
│   │   │   ├── websockets.py # WebSocket manager
│   │   │   └── persistence.py # Message persistence
│   │   ├── db/               # Database
│   │   │   ├── __init__.py
│   │   │   ├── session.py    # Database session management
│   │   │   ├── models.py     # SQLAlchemy models
│   │   │   └── crud.py       # Database operations
│   │   ├── schemas/          # Pydantic models
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── thread.py
│   │   │   └── message.py
│   │   ├── services/         # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── thread.py
│   │   │   └── message.py
│   │   ├── agents/           # Agent system
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── lawyer.py
│   │   │   ├── accountant.py
│   │   │   └── psychologist.py
│   │   └── utils/            # Utility functions
│   │       ├── __init__.py
│   │       └── helpers.py
│   └── tests/                # Tests
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_api/
│       ├── test_core/
│       └── test_services/
├── scripts/                   # Utility scripts
│   ├── start.sh
│   └── setup_db.sh
└── docker/                    # Docker configuration
    ├── Dockerfile
    └── docker-compose.yml
```

This structure follows Python best practices and separates concerns into distinct modules:

1. `src/cyberiad/`: Main package directory
   - `api/`: Route definitions
   - `core/`: Core system functionality
   - `db/`: Database models and operations
   - `schemas/`: Data validation models
   - `services/`: Business logic
   - `agents/`: Agent implementations
   - `utils/`: Helper functions

2. `alembic/`: Database migration management

3. `tests/`: Comprehensive test suite

4. `docker/`: Container configuration

Would you like me to:
1. Create any specific module in detail?
2. Explain the rationale behind any part of the structure?
3. Set up the Docker configuration?
4. Create the initial setup scripts?
