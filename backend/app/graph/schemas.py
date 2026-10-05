from typing import Literal

from pydantic import BaseModel

GraphNodeType = Literal["person", "topic", "document"]


class GraphNodeOut(BaseModel):
    id: str
    type: GraphNodeType
    label: str
    subtitle: str | None = None


class GraphEdgeOut(BaseModel):
    source: str
    target: str
    weight: float


class TeamGraphOut(BaseModel):
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]
