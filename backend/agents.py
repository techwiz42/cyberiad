from typing import Dict, List, Optional
from pydantic import BaseModel, Field
import openai
from enum import Enum
import os

class AgentRole(str, Enum):
    LAWYER = "lawyer"
    ACCOUNTANT = "accountant"
    PSYCHOLOGIST = "psychologist"
    BUSINESS_ANALYST = "business_analyst"
    ETHICS_ADVISOR = "ethics_advisor"
    MODERATOR = "moderator"

class AgentPrompt(BaseModel):
    role: str
    context: str
    disclaimer: str
    guidelines: List[str]

class AgentResponse(BaseModel):
    content: str
    metadata: Dict = Field(default_factory=dict)
    citations: Optional[List[str]] = None

AGENT_PROMPTS = {
    AgentRole.LAWYER: AgentPrompt(
        role="Legal Advisor",
        context="""You are an AI legal advisor. While you can provide general legal information 
        and explanations, you must always emphasize that you are not a substitute for a licensed attorney.""",
        disclaimer="""IMPORTANT: This is AI-generated legal information, not legal advice. 
        Consult with a licensed attorney for specific legal advice.""",
        guidelines=[
            "Always provide context for legal concepts",
            "Cite relevant laws and regulations when possible",
            "Emphasize when issues require professional legal consultation",
            "Focus on explaining legal concepts rather than giving specific advice"
        ]
    ),
    AgentRole.ACCOUNTANT: AgentPrompt(
        role="Financial Advisor",
        context="""You are an AI financial advisor. You can explain financial concepts 
        and general accounting principles while emphasizing you're not a certified accountant.""",
        disclaimer="""This is AI-generated financial information, not professional financial advice. 
        Consult with a certified accountant or financial advisor for specific guidance.""",
        guidelines=[
            "Explain financial concepts clearly",
            "Use real-world examples when appropriate",
            "Emphasize risk and uncertainty in financial matters",
            "Direct complex queries to professional consultation"
        ]
    ),
    # Add other agent roles similarly
}

class Agent:
    def __init__(self, role: AgentRole):
        self.role = role
        self.prompt = AGENT_PROMPTS[role]
        self.model = "gpt-4"  # or your preferred model
        
    def _build_prompt(self, message: str, thread_context: Optional[str] = None) -> List[Dict]:
        """Build the complete prompt with role context and message."""
        messages = [
            {"role": "system", "content": self.prompt.context},
            {"role": "system", "content": self.prompt.disclaimer}
        ]
        
        if thread_context:
            messages.append({"role": "system", "content": f"Previous context: {thread_context}"})
            
        messages.append({"role": "user", "content": message})
        return messages

    async def generate_response(self, message: str, thread_context: Optional[str] = None) -> AgentResponse:
        """Generate a response using the OpenAI API."""
        try:
            messages = self._build_prompt(message, thread_context)
            
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            # Process the response
            content = response.choices[0].message.content
            
            # Add disclaimer to response
            full_response = f"{content}\n\n{self.prompt.disclaimer}"
            
            return AgentResponse(
                content=full_response,
                metadata={
                    "role": self.role,
                    "model": self.model,
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens
                }
            )
            
        except Exception as e:
            raise Exception(f"Error generating response: {str(e)}")

class AgentManager:
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        
    def get_agent(self, role: AgentRole) -> Agent:
        """Get or create an agent for a specific role."""
        if role not in self.agents:
            self.agents[role] = Agent(role)
        return self.agents[role]
    
    async def get_response(self, role: AgentRole, message: str, thread_context: Optional[str] = None) -> AgentResponse:
        """Get a response from a specific agent."""
        agent = self.get_agent(role)
        return await agent.generate_response(message, thread_context)

# Create agent manager instance
agent_manager = AgentManager()
