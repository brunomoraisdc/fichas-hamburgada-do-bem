from typing import Optional

from pydantic import BaseModel


class Crianca(BaseModel):
    nome: Optional[str] = None
    idade: Optional[int] = None
    sala: Optional[str] = None
    numero_ficha: Optional[str] = None


class Responsavel(BaseModel):
    nome: Optional[str] = None
    rg: Optional[str] = None
    telefone_principal: Optional[str] = None
    telefone_secundario: Optional[str] = None


class Autorizacoes(BaseModel):
    pode_sair_sozinho: Optional[bool] = None


class FichaExtraida(BaseModel):
    crianca: Crianca
    responsavel: Responsavel
    autorizacoes: Autorizacoes


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    dados: Optional[FichaExtraida] = None
    campos_incertos: list[str] = []
    erro: Optional[str] = None


class ValidateRequest(BaseModel):
    job_id: str
    dados: FichaExtraida
