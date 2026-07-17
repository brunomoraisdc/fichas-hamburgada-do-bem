import io
import json
import os

import PIL.Image
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

PROMPT = """
Contexto:
Você é um especialista em OCR (Reconhecimento Óptico de Caracteres) e extração de dados estruturados. Sua tarefa é converter a imagem de uma "Ficha de Autorização" do evento "Hamburgada do Bem" em um objeto JSON estrito.

Instruções de Extração:
Fidelidade: Transcreva exatamente como escrito, mantendo maiúsculas/minúsculas conforme o formulário.
Campos Vazios: Se um campo não estiver preenchido, retorne null.
Seleção de Opções (Checkboxes): Para o campo "Pode ir embora sozinho?", identifique qual opção foi marcada ("SIM" ou "NÃO") e retorne um valor booleano.
Tratamento de Erros: Se não tiver certeza de um caractere, coloque-o entre colchetes [ ].

Esquema de Saída (JSON):
{
"crianca": {
    "nome": "string",
    "idade": "integer",
    "sala": "string",
    "numero_ficha": "string"
},
"responsavel": {
    "nome": "string",
    "rg": "string",
    "telefone_principal": "string",
    "telefone_secundario": "string"
},
"autorizacoes": {
    "pode_sair_sozinho": "boolean"
}
}
"""


class ExtractionError(Exception):
    pass


def extract_ficha(image_bytes: bytes) -> dict:
    try:
        img = PIL.Image.open(io.BytesIO(image_bytes))
        img.load()
    except Exception as e:
        raise ExtractionError(f"Imagem inválida: {e}") from e

    try:
        response = _client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[PROMPT, img],
            config=types.GenerateContentConfig(
                temperature=0.1,
                top_p=0.95,
                top_k=64,
                max_output_tokens=8192,
                response_mime_type="application/json",
            ),
        )
    except Exception as e:
        raise ExtractionError(f"Falha ao chamar o Gemini: {e}") from e

    texto_limpo = response.text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(texto_limpo)
    except json.JSONDecodeError as e:
        raise ExtractionError(f"Resposta da IA não é um JSON válido: {e}") from e


def find_uncertain_fields(data: dict, prefix: str = "") -> list[str]:
    """Percorre o dict extraído e retorna os caminhos (ex: 'crianca.nome') de
    campos que a IA marcou como incertos com colchetes '[ ]'."""
    uncertain: list[str] = []
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            uncertain.extend(find_uncertain_fields(value, path))
        elif isinstance(value, str) and "[" in value and "]" in value:
            uncertain.append(path)
    return uncertain
