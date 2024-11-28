from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import openai
from swarm import Agent

MODEL = "gpt-4"

class AgentRole(str, Enum):
    DOCTOR = "doctor"
    LAWYER = "lawyer" 
    ACCOUNTANT = "accountant"
    ETHICIST = "ethicist"
    ENVIRONMENTAL_SCIENTIST = "environmental_scientist"
    FINANCIER = "financier"
    BUSINESSMAN = "businessman"

class AgentResponse(BaseModel):
    content: str
    metadata: Dict[str, Any] = {}
    citations: Optional[List[str]] = None

DOCTOR = Agent(
    name="doctor",
    instructions="As a medical professional, I share medical information but not medical advice. Always recommend consulting a licensed physician.",
    model=MODEL
)

LAWYER = Agent(
    name="lawyer",
    instructions="As a legal professional, I provide general legal information but not legal advice. Always recommend consulting a licensed attorney.", 
    model=MODEL
)

ACCOUNTANT = Agent(
    name="accountant",
    instructions="As an accounting professional, I provide general financial information but not specific advice. Always recommend consulting a certified accountant.",
    model=MODEL
)

ETHICIST = Agent(
    name="ethicist", 
    instructions="As an ethics expert, I analyze ethical dilemmas using established frameworks and present multiple perspectives on complex issues.",
    model=MODEL
)

ENVIRONMENTAL_SCIENTIST = Agent(
    name="environmental_scientist",
    instructions="As an environmental scientist, I provide scientific analysis of environmental issues using data and research.",
    model=MODEL
)

FINANCIER = Agent(
    name="financier",
    instructions="As a finance expert, I discuss markets, investments, and economic trends but cannot give specific investment advice.",
    model=MODEL
)

BUSINESSMAN = Agent(
    name="businessman",
    instructions="As a business expert, I provide insights on strategy, management, and operations but cannot give specific business advice.",
    model=MODEL
)

AGENTS = {
    "doctor": DOCTOR,
    "lawyer": LAWYER,
    "accountant": ACCOUNTANT,
    "ethicist": ETHICIST,
    "environmental_scientist": ENVIRONMENTAL_SCIENTIST,
    "financier": FINANCIER,
    "businessman": BUSINESSMAN
}

class AgentSystem:
    def __init__(self):
        self.current_agent = None
        self.history: List[Dict[str, str]] = []
    
    def transfer_to(self, agent_name: str) -> Agent:
        if agent_name in AGENTS:
            self.current_agent = AGENTS[agent_name]
        return self.current_agent

agent_system = AgentSystem()

class AgentManager:
    def __init__(self):
        self.current_agent = None
        self.history: List[Dict[str, str]] = []

    def transfer_to(self, agent_name: str) -> Agent:
        if agent_name in AGENTS:
            self.current_agent = AGENTS[agent_name]
        return self.current_agent

agent_manager = AgentManager()
