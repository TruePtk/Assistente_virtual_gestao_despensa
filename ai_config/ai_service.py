import json
from google import genai
from google.genai import types
from config import GEMINI_API_KEY

# A nova biblioteca usa um Client instanciado
client = genai.Client(api_key=GEMINI_API_KEY)

def processar_nota_fiscal(foto_bytes: bytearray) -> dict:
    """Envia a imagem da nota para o Gemini e retorna um dicionário (JSON) dos itens."""
    
    prompt = """
    Você é um assistente de extração de dados. Analise esta imagem de nota fiscal de supermercado.
    Extraia os itens comprados e retorne APENAS um JSON válido, sem formatação markdown (```json).
    
    Categorize os itens de forma lógica para uma despensa (ex: Laticínios, Limpeza, Hortifruti, Mercearia).
    Traduza abreviações comuns de mercado para o nome real do produto.
    
    Formato esperado:
    {
      "itens": [
        {
          "nome": "Goma de Tapioca",
          "quantidade": 2,
          "unidade_medida": "kg",
          "categoria": "Mercearia"
        }
      ]
    }
    """
    
    try:
        # Faz a chamada usando o novo padrão da API, já corrigindo o erro do bytearray
        resposta = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=[
                prompt,
                types.Part.from_bytes(
                    data=bytes(foto_bytes), # Conversão feita aqui!
                    mime_type='image/jpeg'
                )
            ]
        )
        
        # Limpa possível formatação markdown
        texto_limpo = resposta.text.replace("```json", "").replace("```", "").strip()
        dados_estruturados = json.loads(texto_limpo)
        return dados_estruturados
        
    except json.JSONDecodeError:
        return {"erro": "Não foi possível extrair um JSON válido.", "raw": resposta.text}
    except Exception as e:
        return {"erro": f"Erro na comunicação com a API: {str(e)}"}