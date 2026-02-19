from pydantic import BaseModel
from typing import Optional

class SubjectTypeBase(BaseModel):
    name: str

class SubjectTypeCreate(SubjectTypeBase):
    pass

class SubjectTypeUpdate(BaseModel):
    name: Optional[str] = None

class SubjectTypeOut(SubjectTypeBase):
    id: int
    class Config:
        orm_mode = True


class SubjectBase(BaseModel):
    name: str
    type_id: Optional[int] = None

class SubjectOut(SubjectBase):
    id: int
    type: Optional[SubjectTypeOut] = None
    class Config:
        orm_mode = True
