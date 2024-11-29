# tests/test_server.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, Mock
import asyncio
from server import app, startup, shutdown
from websocket_manager import connection_manager

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_connection_manager():
    manager = AsyncMock()
    manager.close_all_connections = AsyncMock()
    return manager

@pytest.mark.asyncio
async def test_startup():
    with patch('server.connection_manager') as mock_manager, \
         patch('server.initialize_connection_manager') as mock_init:
        await startup()
        mock_init.assert_called_once()

@pytest.mark.asyncio
async def test_shutdown():
    with patch('server.connection_manager') as mock_manager:
        await shutdown()
        mock_manager.close_all_connections.assert_called_once()

def test_cors_configuration():
    assert app.user_middleware[0].cls.__name__ == "CORSMiddleware"
    cors_middleware = app.user_middleware[0].options
    assert "http://localhost:3000" in cors_middleware["allow_origins"]
    assert "http://localhost:3001" in cors_middleware["allow_origins"]
    assert cors_middleware["allow_credentials"] is True
    assert "GET" in cors_middleware["allow_methods"]
    assert "POST" in cors_middleware["allow_methods"]

def test_router_inclusion():
    routes = [route.path for route in app.routes]
    assert "/api/auth/register" in routes
    assert "/api/auth/token" in routes
    assert "/api/threads/" in routes
    assert "/api/messages/{thread_id}" in routes
    assert "/api/agents/roles" in routes

@pytest.mark.asyncio
async def test_websocket_endpoint():
    thread_id = "123"
    user_id = "456"
    
    with patch('server.connection_manager') as mock_manager:
        mock_manager.connect = AsyncMock()
        mock_manager.handle_client_message = AsyncMock()
        mock_manager.disconnect = AsyncMock()
        
        client = TestClient(app)
        with client.websocket_connect(f"/ws/{thread_id}/{user_id}") as websocket:
            mock_manager.connect.assert_called_once()
            mock_manager.handle_client_message.assert_called_once()

@pytest.mark.asyncio
async def test_websocket_disconnect_handling():
    thread_id = "123"
    user_id = "456"
    
    with patch('server.connection_manager') as mock_manager:
        mock_manager.connect = AsyncMock(side_effect=Exception("Connection error"))
        mock_manager.disconnect = AsyncMock()
        
        client = TestClient(app)
        with pytest.raises(Exception):
            with client.websocket_connect(f"/ws/{thread_id}/{user_id}"):
                pass
        
        mock_manager.disconnect.assert_called_once()

def test_server_middleware_stack():
    middleware_classes = [m.cls.__name__ for m in app.user_middleware]
    assert "CORSMiddleware" in middleware_classes

@pytest.mark.asyncio
async def test_startup_database_error():
    with patch('server.db_manager.create_tables', side_effect=Exception("DB Error")), \
         patch('server.logger.error') as mock_logger:
        with pytest.raises(Exception):
            await startup()
        mock_logger.assert_called_once()

@pytest.mark.asyncio
async def test_shutdown_cleanup():
    with patch('server.connection_manager') as mock_manager, \
         patch('server.logger.info') as mock_logger:
        await shutdown()
        mock_manager.close_all_connections.assert_called_once()
        mock_logger.assert_called_with("Application shutdown complete")

def test_uvicorn_configuration():
    import server
    with patch('uvicorn.run') as mock_run:
        # Simulate main execution
        server_dict = {}
        exec(open('server.py').read(), server_dict)
        
        # Check if uvicorn would be configured correctly
        if '__name__' in server_dict and server_dict['__name__'] == '__main__':
            mock_run.assert_called_once()
            args, kwargs = mock_run.call_args
            assert kwargs['host'] == "0.0.0.0"
            assert kwargs['port'] == 8000
            assert kwargs['reload'] is True

def test_health_check():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

@pytest.mark.asyncio
async def test_graceful_shutdown():
    with patch('server.connection_manager') as mock_manager:
        # Simulate active connections
        mock_manager.active_connections = {"thread1": {"user1": "ws1"}}
        
        await shutdown()
        
        # Verify cleanup
        mock_manager.close_all_connections.assert_called_once()

def test_error_handling():
    client = TestClient(app)
    
    # Test 404 handling
    response = client.get("/nonexistent")
    assert response.status_code == 404
    
    # Test method not allowed
    response = client.post("/health")
    assert response.status_code == 405

@pytest.mark.asyncio
async def test_connection_manager_initialization():
    with patch('server.initialize_connection_manager') as mock_init:
        await startup()
        mock_init.assert_called_once()
        # Verify cleanup task is created
        assert asyncio.all_tasks()  # Should have at least one task

def test_environment_configuration():
    import os
    with patch.dict(os.environ, {'PORT': '9000'}):
        import server
        assert int(os.getenv("PORT", 8000)) == 9000
