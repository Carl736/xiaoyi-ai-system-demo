from pydantic import BaseModel
from typing import List,Optional
class Question(BaseModel):
    text: str
    document_ids:Optional[List[str]]=None