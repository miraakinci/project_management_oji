from pydantic import BaseModel, Field, ValidationError
from typing import List 
from datetime import date

class Task(BaseModel):
    name: str
    responsible_team: str
    duration: int = Field(gt=0) # Ensures duration is a positive number
    #start_date: date
    #end_date: date

class Deliverable(BaseModel):
    description: str
    tasks: List[Task]

class Benefit(BaseModel):
    description: str
    deliverables: List[Deliverable]

class Outcome(BaseModel):
    description: str
    benefits: List[Benefit]

class ProjectFlow(BaseModel):
    title: str
    outcomes: List[Outcome]
