from google import genai
from google.genai import types
import os
import PIL.Image
import time
import json
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

pasta_fichas = "fichas"
dados_coletados = []

print(f"--- Lendo arquivos da pasta: {pasta_fichas} ---")

for arquivo in os.listdir(pasta_fichas):
    try:
        image_path = os.path.join(pasta_fichas, arquivo)
        
        if not arquivo.lower().endswith(('.png', '.jpg', '.jpeg')):
            continue

        img = PIL.Image.open(image_path)
        print(f"Imagem '{arquivo}' carregada! Processando...")

        prompt = """ 
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

        print("Enviando para o Gemini...")
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, img],
            config=types.GenerateContentConfig(
                temperature=0.1,
                top_p=0.95,
                top_k=64,
                max_output_tokens=8192,
                response_mime_type="application/json"
            )
        )

        print("\n--- RESPOSTA DA IA ---")
        print(response.text)
        print("-" * 30)
        
        # Limpeza e Append DENTRO do loop
        texto_limpo = response.text.replace("```json", "").replace("```", "")
        dados_json = json.loads(texto_limpo)
        dados_coletados.append(dados_json)

        time.sleep(2)

    except Exception as e:
        print(f"ERRO ao processar '{arquivo}': {e}")
        continue

# Geração do Excel FORA do loop
# ... (o resto do código permanece igual) ...

if dados_coletados:
    df = pd.json_normalize(dados_coletados)
    
    # Usa o ExcelWriter para acessar as propriedades de formatação
    with pd.ExcelWriter("relatorio_fichas.xlsx", engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Fichas")
        
        # Acessa a aba criada
        worksheet = writer.sheets["Fichas"]

        # Itera sobre todas as colunas para ajustar a largura
        for column in worksheet.columns:
            max_length = 0
            # Pega a letra da coluna (A, B, C...) baseada na primeira célula
            column_letter = column[0].column_letter 
            
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            
            # Define a largura final + uma margem de segurança de 2 caracteres
            adjusted_width = (max_length + 2)
            worksheet.column_dimensions[column_letter].width = adjusted_width

    print(f"Arquivo salvo com {len(df)} registros e colunas ajustadas.")