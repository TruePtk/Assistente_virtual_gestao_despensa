# Assistente virtual de gestão de despensa

Protótipo acadêmico de um assistente conversacional para gestão de despensa doméstica. O bot do Telegram registra compras a partir de fotos de notas fiscais, mantém um estoque SQLite isolado por usuário e interpreta pedidos em linguagem natural para consultar, adicionar ou dar baixa em itens. O projeto também avalia precisão e tempo de resposta do modelo.

## Demonstração

1. Inicie uma conversa com o bot e envie `/start`.
2. Cadastre itens por mensagem ou envie uma foto de uma nota fiscal.
3. Consulte o estoque com `/despensa` ou pergunte, por exemplo, “o que tem na despensa?”.
4. Registre o consumo por texto ou use os botões exibidos junto aos itens.

Exemplo de conversa (as respostas da IA podem variar):

```text
Você: Adicione 2 kg de arroz e 1 litro de leite.
Bot: Adicionado: 2 kg de arroz.
     Adicionado: 1 litro de leite.

Você: Usei meio litro de leite.
Bot: Baixa registrada! Restam 0.50 de leite.

Você: /despensa
Bot: 🥫 Sua Despensa:
     • 2.0 kg de arroz
     • 0.5 litro de leite
     [❌ Consumi: arroz] [❌ Consumi: leite]
```

Os nomes e quantidades dos exemplos pressupõem que as operações foram interpretadas dessa forma pelo modelo. `/despensa` lista os itens e mostra botões para registrar consumo; a quantidade exibida pode usar a representação numérica retornada pelo SQLite. Como se trata de um protótipo acadêmico, confirme o estoque quando a precisão for importante.

## Requisitos

- Python 3.12 ou superior.
- Um bot do Telegram e o token fornecido pelo [@BotFather](https://t.me/BotFather).
- Uma chave de API do Gemini, criada no [Google AI Studio](https://aistudio.google.com/app/apikey).

O projeto usa SQLite; não é necessário instalar um servidor de banco de dados. Na primeira execução, `database/database.py` cria `despensa.db` no diretório de onde o programa foi iniciado. O bot e os lembretes só ficam disponíveis enquanto o computador que executa o programa estiver ligado e conectado à internet.

## Instalação

Clone o repositório e entre na pasta do projeto. Crie e ative um ambiente virtual.

### Windows (PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Linux ou macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Configuração das chaves

Crie um arquivo chamado `.env` na raiz do projeto, no mesmo nível de `main.py` e `config.py`:

```dotenv
TELEGRAM_BOT_TOKEN=cole_aqui_o_token_do_BotFather
GEMINI_API_KEY=cole_aqui_a_chave_do_Google_AI_Studio
```

Substitua os textos de exemplo pelos valores reais, sem aspas. O programa carrega essas variáveis em `config.py` e interrompe a inicialização se alguma estiver ausente. Inicie o bot a partir da pasta do projeto para que o `.env` seja encontrado.

O `.gitignore` já exclui `.env` e `.venv`. Mantenha as chaves apenas nesse arquivo local: não as escreva no código, README, commits, capturas de tela ou mensagens públicas. Antes de enviar alterações, confira com `git status` se `.env` não aparece entre os arquivos a serem adicionados. Se uma chave for exposta, revogue-a no serviço correspondente e gere outra.

## Executar

Com o ambiente virtual ativo e o `.env` preenchido, execute na raiz do projeto:

```bash
python main.py
```

O bot usa polling para receber mensagens. Deixe o processo aberto enquanto quiser que ele responda; `Ctrl+C` encerra a execução.

## Mensagens e respostas

| Entrada | Comportamento |
| --- | --- |
| `/start` | Apresenta o assistente e explica como enviar uma nota ou perguntar sobre receitas. |
| `/despensa` | Lista os itens do usuário com botões para iniciar o registro de consumo. |
| `Adicione 3 latas de milho.` | A IA interpreta a intenção e o núcleo soma a quantidade a um item correspondente ou cria um novo. |
| `Usei 1 lata de milho.` | A IA identifica o item e a quantidade; o banco subtrai o valor. Se o estoque chegar a zero, o item é removido. |
| `O que tem na minha despensa?` | A interpretação retorna `consultar`; o bot mostra a mesma lista de `/despensa`. |
| `Consumi tudo de milho.` | Remove o item identificado. Para “consumir tudo da despensa”, a operação especial limpa todos os itens daquele usuário. |
| Pergunta geral | A IA pode responder sem alterar o estoque. |
| Foto da nota fiscal | O Gemini Vision extrai nome, quantidade, unidade e categoria. Essa é a forma de entrada recomendada pelo trabalho. |

Os botões de consumo oferecem `-1`, `-0.5` e `Acabou Tudo!`; o item também pode ser mantido ou ter o lembrete adiado. O bot agenda verificações de lembretes a cada hora e só os envia entre 9h e 20h, no máximo um por usuário em cada rodada.

Cadências configuradas: 5 dias para laticínios e hortifruti, 7 para outros, 15 para mercearia e doces, e 30 para limpeza. Depois de enviado, o mesmo item não volta a ser lembrado antes de 14 dias; “Lembrar depois” adia por 7 dias.

### Exemplo de leitura por foto

Ao enviar uma foto, o bot confirma que recebeu a imagem. Se a leitura funcionar, a resposta é semelhante a:

```text
✅ Itens adicionados pela leitura da foto:
• 2 kg de Goma de Tapioca (Mercearia)
• 1 unidade de Leite (Laticínios)
```

O trabalho avaliou a consulta pública da NFC-e pelo QR Code, mas registrou bloqueio ao acesso automatizado pela SEFAZ. Por isso, a monografia descreve a leitura por foto como o fluxo mantido para entrada de dados e não considera a consulta ao QR Code uma funcionalidade suportada.

**Diferença entre a monografia e o código atual:** `handlers/telegram.py` e `nfc_e_service.py` ainda contêm um caminho experimental que tenta consultar o QR Code antes de recorrer à leitura visual. Se a consulta for bloqueada, o código atual retorna erro em vez de tentar automaticamente a leitura da mesma imagem por foto. Portanto, o comportamento implementado ainda não está totalmente alinhado à decisão descrita na monografia; para cadastrar uma nota, use uma imagem sem QR Code NFC-e reconhecível ou ajuste o fluxo antes de uma demonstração.

## Como o JSON vira operações

Para mensagens de texto, `ai_config/ai_service.py` envia a mensagem ao Gemini e pede somente um objeto JSON. Uma mensagem com duas ações pode ser interpretada assim:

```json
{
  "operacoes": [
    {
      "acao": "consumir",
      "item_alvo": "leite",
      "quantidade": 1
    },
    {
      "acao": "adicionar",
      "item_alvo": "arroz",
      "quantidade": 2,
      "unidade_medida": "kg",
      "categoria": "Mercearia"
    }
  ]
}
```

O caminho no código é:

1. `ai_service.interpretar_intencao_usuario` limpa eventuais cercas Markdown e converte o texto com `json.loads`.
2. `handlers/core.py` percorre `operacoes` na ordem recebida. Para compatibilidade, também aceita o formato antigo de uma única ação no nível superior.
3. Em `adicionar`, compara nomes sem acentos e pontuação e tenta identificar singular/plural ou nomes parecidos. Um único item correspondente recebe a quantidade somada; sem correspondência, um novo registro é criado. Se houver mais de um candidato, não escolhe automaticamente e pede mais especificidade.
4. Em `consumir`, localiza o item e subtrai a quantidade. Uma quantidade igual ou menor que zero no estoque remove o registro. A operação especial com `item_alvo: "tudo"` esvazia a despensa daquele usuário.
5. `consultar` retorna os itens para o handler apresentar. `duvida_geral` devolve o texto de resposta da IA sem mexer no estoque.

As operações de estoque são gravadas em `itens_despensa` no SQLite e associadas ao ID do usuário do Telegram. As categorias padrão são `Mercearia`, `Laticínios`, `Hortifruti`, `Limpeza`, `Doces e Guloseimas` e `Outros`; uma categoria desconhecida é salva como `Outros`.

Para fotos, a extração produz um JSON com uma lista `itens`, cada um contendo nome, quantidade, unidade e categoria. O núcleo descarta registros sem nome ou com quantidade ausente, inválida, zero ou negativa, aceita quantidade com vírgula decimal e os encaminha à mesma lógica de soma/criação usada para adicionar por texto.

## Avaliação preliminar

A monografia descreve um piloto de interpretação com uma despensa fixa de 16 itens e 39 mensagens de teste, distribuídas em sete categorias: consulta (6), ausência de item (4), consumo (8), adição (6), operações compostas (6), casos armadilha como ambiguidades ou pedidos fora do tema (6) e variações de escrita (3). Cada mensagem foi executada três vezes, totalizando 117 execuções por rodada. A avaliação mede intenção correta, estado final correto, acerto, itens inventados, consistência entre repetições e tempo de resposta da interpretação e execução (sem o tempo de comunicação com o Telegram).

| Rodada | Acerto | Intenção correta | Itens inventados | Tempo médio | Consistência |
| --- | ---: | ---: | ---: | ---: | ---: |
| Inicial | 88,9% (104/117) | 100% | 0 | 8,88 s | 97,4% |
| Após correções | 99,1% (116/117) | 99,1% | 0 | 3,50 s | 97,4% |

Esses resultados são preliminares, não uma estimativa final de desempenho. As correções foram feitas com base nas mesmas perguntas usadas na avaliação, o que pode tornar a segunda rodada otimista. A monografia prevê um novo conjunto de perguntas executado uma vez na versão final. Também permanecem pendentes o teste de extração de fotos com gabarito transcrito, a comparação com um dashboard web e a avaliação de usabilidade com participantes usando o questionário SUS. O dashboard e o atalho do iOS são trabalhos em andamento ou futuros, não funcionalidades descritas como concluídas.

Na primeira rodada, as falhas principais envolveram expressões como “acabou” e “terminei”, mensagens com consulta seguida de outra operação e soma de quantidades em unidades incompatíveis. Após ajustes no prompt e no código, restou uma falha em uma de três execuções da mensagem “vê o que tem de leite e depois usa 1 ovo”. A consistência de 97,4% permaneceu igual nas duas rodadas: consistência mede repetição do resultado, mesmo quando ele está errado.

## Arquitetura

```text
Telegram ──> main.py / handlers/telegram.py
                    │
                    ├─ Texto ──> ai_config/ai_service.py ── JSON de operações
                    │                                       │
                    ├─ Foto ──> Gemini Vision ──────────────┤
                    └───────────────────────────────────────┘
                                      ↓
                               handlers/core.py
                                      ↓
                         database/database.py ── SQLite
```

- `main.py`: configura o bot, registra comandos e handlers, e agenda os lembretes.
- `config.py`: carrega e valida as variáveis de ambiente.
- `handlers/telegram.py`: integra mensagens, fotos e botões do Telegram com os casos de uso.
- `handlers/core.py`: interpreta os resultados da IA, aplica regras de estoque e coordena lembretes e notas.
- `ai_config/ai_service.py`: chama o Gemini para interpretar mensagens e extrair itens de notas.
- `nfc_e_service.py`: contém a tentativa experimental de decodificar QR Code e consultar páginas públicas de NFC-e.
- `database/database.py`: cria e consulta as tabelas de usuários, categorias e itens no SQLite.
- `despensa.template.db`: arquivo modelo do banco incluído no repositório; a execução usa `despensa.db`.

O fluxo principal descrito na monografia é Telegram → interpretação ou extração pelo Gemini → regras determinísticas → SQLite. A tentativa de consulta à SEFAZ ainda presente no código é experimental e não integra o fluxo recomendado após o bloqueio do acesso automatizado.

## Limitações e escopo

- O banco é local ao processo e depende do diretório de execução. Faça cópias de segurança de `despensa.db` se os dados forem importantes; esse arquivo é ignorado pelo Git.
- O bot, o banco e os lembretes são adequados ao protótipo e à baixa concorrência esperada; não há hospedagem ou disponibilidade contínua.
- Mensagens e fotos são processadas por serviços externos do Telegram e/ou Gemini. Uma foto enviada para leitura visual é transmitida ao Gemini.
- O WhatsApp foi substituído pelo Telegram devido à dificuldade de acesso à API. Um dashboard web, o comparativo entre interfaces e o atalho do iOS dependem de trabalho futuro.
- A leitura depende da qualidade da foto e da disponibilidade do serviço Gemini. Confira o estoque quando a interpretação for importante.
