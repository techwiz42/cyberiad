# Cyberiad

A multi-user, multi-agent discussion platform that enables collaborative conversations with specialized AI agents.

## Project Structure

The project consists of two main parts: the backend server and the frontend client.

### Backend (`/cyberiad`)

```
cyberiad/
├── src/
│   ├── cyberiad/              # Main package
│   │   ├── api/              # API endpoints
│   │   │   ├── auth.py       # Authentication routes
│   │   │   ├── threads.py    # Thread management
│   │   │   ├── messages.py   # Message handling
│   │   │   └── agents.py     # Agent management
│   │   ├── core/            # Core functionality
│   │   │   ├── security.py   # Security and rate limiting
│   │   │   ├── websockets.py # WebSocket manager
│   │   │   └── persistence.py # Message persistence
│   │   ├── db/              # Database
│   │   │   ├── models.py     # SQLAlchemy models
│   │   │   └── crud.py       # Database operations
│   │   ├── agents/          # Agent implementations
│   │   │   ├── base.py
│   │   │   ├── lawyer.py
│   │   │   └── accountant.py
│   │   └── utils/           # Utility functions
│   └── tests/               # Tests
├── alembic/                  # Database migrations
├── requirements.txt          # Python dependencies
└── docker/                   # Docker configuration
```

### Frontend (`/cyberiad-client`)

```
cyberiad-client/
├── src/
│   ├── app/                  # Next.js app directory 
│   ├── components/           # React components
│   │   ├── layout/          # Layout components
│   │   ├── thread/          # Thread components
│   │   ├── chat/            # Chat components
│   │   └── agents/          # Agent components
│   ├── hooks/               # Custom React hooks
│   ├── services/            # API services
│   ├── store/               # State management
│   └── types/               # TypeScript types
├── public/                  # Static assets
└── package.json            # Node dependencies
```

## Setup

### Backend Requirements

- Python 3.9+
- PostgreSQL
- Redis (for WebSocket state)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up database
createdb cyberiad
alembic upgrade head

# Start server
uvicorn cyberiad.main:app --reload
```

### Frontend Requirements

- Node.js 18+
- npm/yarn

```bash
# Install dependencies
cd cyberiad-client
npm install

# Start development server
npm run dev
```

## Environment Variables

### Backend (.env)
```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/cyberiad
JWT_SECRET_KEY=your-secret-key
OPENAI_API_KEY=your-openai-key
```

### Frontend (.env.local)
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

## Features

- Multi-user chat threads
- Specialized AI agents (Legal, Financial, Technical advisors)
- Real-time updates via WebSocket
- Message persistence and history
- User authentication and authorization
- Thread-based discussions
- Agent response coordination

## Development

- Backend API runs on `http://localhost:8000`
- Frontend development server runs on `http://localhost:3000`
- API documentation available at `http://localhost:8000/docs`

## Testing

### Backend
```bash
pytest src/tests
```

### Frontend
```bash
npm test
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details
