from pydantic import BaseModel,Field
class CertificateInput(BaseModel):
 code:str=Field(min_length=2,max_length=120); month:str=Field(min_length=6,max_length=7)
 department:str=Field(min_length=1,max_length=100); factor:float=Field(ge=0); kwh_total:float=Field(gt=0)
class GreenReportInput(BaseModel):
 name:str=Field(min_length=2,max_length=120); month:str=Field(min_length=6,max_length=7)
 department:str=Field(min_length=1,max_length=100); kwh:float=Field(gt=0); grid_factor:float=Field(ge=0)
