import json
from google import genai
from google.genai import types
from config import GEMINI_API_KEY

# A nova biblioteca usa um Client instanciado
client = genai.Client(api_key=GEMINI_API_KEY)


def enviar_prompt_para_ia(prompt: str, partes: list | None = None) -> str:
    """Envia um prompt ao Gemini, usando o segundo modelo como fallback."""
    contents = [prompt, *(partes or [])]
    ultimo_erro = None

    for modelo in ("gemini-3.1-flash-lite", "gemini-3.5-flash-lite"):
        try:
            resposta = client.models.generate_content(
                model=modelo,
                contents=contents,
            )
            return resposta.text
        except Exception as erro:
            ultimo_erro = erro

    raise RuntimeError(f"Erro ao comunicar com a IA: {ultimo_erro}") from ultimo_erro


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
    Lembre o usuário dos comandos disponíveis: /despensa para ver a lista.
    """
    
    try:
        texto_limpo = enviar_prompt_para_ia(
            prompt,
            [
                types.Part.from_bytes(
                    data=bytes(foto_bytes),
                    mime_type="image/jpeg",
                )
            ],
        )
        return json.loads(texto_limpo.replace("```json", "").replace("```", "").strip())
    except json.JSONDecodeError:
        return {"erro": "Não foi possível extrair um JSON válido.", "raw": texto_limpo}
    except Exception as e:
        return {"erro": f"Erro na comunicação com a API: {str(e)}"}

def interpretar_intencao_usuario(texto_usuario: str) -> dict:
    """Usa o Gemini para entender o que o usuário quer fazer com a despensa."""
    
    prompt = f"""
    Analise a seguinte mensagem do usuário e determine sua intenção em relação a uma despensa.
    Retorne APENAS um JSON válido.
    
        Ações possíveis: "consumir", "adicionar", "consultar", "duvida_geral".

        Uma mensagem pode conter várias operações. Retorne sempre um objeto com a
        chave "operacoes", mesmo quando houver apenas uma operação:
        {{
            "operacoes": [
                {{
                    "acao": "consumir",
                    "item_alvo": "leite",
                    "quantidade": 1
                }},
                {{
                    "acao": "adicionar",
                    "item_alvo": "arroz",
                    "quantidade": 2,
                    "unidade_medida": "kg",
                    "categoria": "Mercearia"
                }}
            ],
            "resposta": "Mensagem para uma dúvida geral, quando aplicável."
        }}

        Para "consumir", use "quantidade" como número ou "TUDO".
        Quando o usuário quiser consumir tudo da despensa, retorne uma única operação
        com "acao": "consumir", "item_alvo": "tudo" e "quantidade": "TUDO".
        Para "adicionar", informe quantidade, unidade_medida e categoria.
        Para "consultar", não inclua item_alvo.
        Para "duvida_geral", inclua uma operação com "acao": "duvida_geral" e uma chave "resposta" com a resposta do bot.
        Não misture uma dúvida geral com operações de despensa.
        Lembre o usuário dos comandos disponíveis: /despensa para ver a lista.

        Mensagem: "{texto_usuario}"
    """
    
    try:
        texto_limpo = enviar_prompt_para_ia(prompt).replace("```json", "").replace("```", "").strip()
        return json.loads(texto_limpo)
    except Exception as e:
        print(f"Erro ao interpretar a intenção do usuário: {e}")
        return {"acao": "erro", "item_alvo": None}
