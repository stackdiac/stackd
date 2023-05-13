
from pydantic import BaseModel


class Provider(BaseModel):
    """
    terraform provider
    """
    source: str
    version: str 
    name: str | None = None