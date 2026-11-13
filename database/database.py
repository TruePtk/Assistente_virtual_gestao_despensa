import sqlite3
import os
import math
from datetime import datetime, timedelta, timezone

# O banco de dados será salvo neste arquivo local
DB_FILE = "despensa.db"

def inicializar_banco():
    """Cria o arquivo despensa.db e as tabelas se não existirem."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        
        # Tabela de Usuários
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                telegram_id INTEGER PRIMARY KEY,
                nome TEXT,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela de Categorias
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL
            )
        ''')
        
        # Tabela de Itens da Despensa
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS itens_despensa (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                nome_produto TEXT NOT NULL,
                quantidade REAL NOT NULL,
                unidade_medida TEXT,
                categoria_id INTEGER,
                data_adicao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ultimo_consumo TIMESTAMP,
                ultimo_lembrete TIMESTAMP,
                lembrar_depois TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES usuarios (telegram_id),
                FOREIGN KEY (categoria_id) REFERENCES categorias (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shortcut_pairings (
                codigo_hash TEXT PRIMARY KEY,
                telegram_id INTEGER NOT NULL,
                expira_em TIMESTAMP NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shortcut_tokens (
                token_hash TEXT PRIMARY KEY,
                telegram_id INTEGER NOT NULL,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        colunas = {linha[1] for linha in cursor.execute("PRAGMA table_info(itens_despensa)")}
        for coluna in ("ultimo_consumo", "ultimo_lembrete", "lembrar_depois"):
            if coluna not in colunas:
                cursor.execute(f"ALTER TABLE itens_despensa ADD COLUMN {coluna} TIMESTAMP")
        
        # Insere categorias padrão se a tabela estiver vazia
        cursor.execute("SELECT COUNT(*) FROM categorias")
        if cursor.fetchone()[0] == 0:
            categorias = [('Mercearia',), ('Laticínios',), ('Hortifruti',), ('Limpeza',), ('Doces e Guloseimas',), ('Outros',)]
            cursor.executemany("INSERT INTO categorias (nome) VALUES (?)", categorias)
            
        conn.commit()

def cadastrar_usuario(telegram_id: int, nome: str):
    """Insere o usuário no banco, ignorando se já existir."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO usuarios (telegram_id, nome) 
            VALUES (?, ?)
        ''', (telegram_id, nome))
        conn.commit()

def criar_vinculacao_atalho(codigo_hash: str, telegram_id: int, validade_minutos: int = 15):
    """Armazena um código de vinculação de uso único e curta duração."""
    expira_em = (datetime.now(timezone.utc).replace(tzinfo=None)
                 + timedelta(minutes=validade_minutos)).strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM shortcut_pairings WHERE telegram_id = ?", (telegram_id,))
        conn.execute(
            "INSERT INTO shortcut_pairings (codigo_hash, telegram_id, expira_em) VALUES (?, ?, ?)",
            (codigo_hash, telegram_id, expira_em),
        )
        conn.commit()

def trocar_codigo_atalho_por_token(codigo_hash: str, telegram_id: int, token_hash: str) -> bool:
    """Consome o código uma única vez e cria um token persistente para o atalho."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            "SELECT 1 FROM shortcut_pairings WHERE codigo_hash = ? AND telegram_id = ? "
            "AND expira_em > CURRENT_TIMESTAMP",
            (codigo_hash, telegram_id),
        )
        if not cursor.fetchone():
            conn.rollback()
            return False
        cursor.execute("DELETE FROM shortcut_pairings WHERE codigo_hash = ?", (codigo_hash,))
        cursor.execute(
            "INSERT INTO shortcut_tokens (token_hash, telegram_id) VALUES (?, ?)",
            (token_hash, telegram_id),
        )
        cursor.execute(
            "INSERT OR IGNORE INTO usuarios (telegram_id, nome) VALUES (?, NULL)",
            (telegram_id,),
        )
        conn.commit()
        return True

def usuario_por_token_atalho(token_hash: str):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute(
            "SELECT telegram_id FROM shortcut_tokens WHERE token_hash = ?", (token_hash,)
        )
        resultado = cursor.fetchone()
        return resultado[0] if resultado else None

def revogar_token_atalho(token_hash: str) -> bool:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute("DELETE FROM shortcut_tokens WHERE token_hash = ?", (token_hash,))
        conn.commit()
        return cursor.rowcount > 0

def salvar_item_despensa(telegram_id: int, nome_produto: str, quantidade: float, unidade_medida: str, nome_categoria: str):
    """Salva o item extraído pela IA na despensa."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        
        # Busca o ID da categoria que veio da IA
        cursor.execute("SELECT id FROM categorias WHERE nome = ?", (nome_categoria,))
        resultado_cat = cursor.fetchone()
        
        if resultado_cat:
            categoria_id = resultado_cat[0]
        else:
            cursor.execute("SELECT id FROM categorias WHERE nome = 'Outros'")
            categoria_outros = cursor.fetchone()
            categoria_id = categoria_outros[0] if categoria_outros else None
        
        # Insere o produto
        cursor.execute('''
            INSERT INTO itens_despensa (telegram_id, nome_produto, quantidade, unidade_medida, categoria_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (telegram_id, nome_produto, quantidade, unidade_medida, categoria_id))
        
        conn.commit()

def adicionar_quantidade_item(item_id: int, telegram_id: int, quantidade: float) -> bool:
    """Soma quantidade a um item existente do usuário."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE itens_despensa
            SET quantidade = quantidade + ?,
                data_adicao = CURRENT_TIMESTAMP,
                ultimo_consumo = NULL,
                ultimo_lembrete = NULL,
                lembrar_depois = NULL
            WHERE id = ? AND telegram_id = ?
        ''', (quantidade, item_id, telegram_id))
        conn.commit()
        return cursor.rowcount > 0

def obter_despensa(telegram_id: int):
    """Retorna todos os itens cadastrados pelo usuário."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        # Busca o ID do item, nome, quantidade e unidade
        cursor.execute('''
            SELECT id, nome_produto, quantidade, unidade_medida 
            FROM itens_despensa 
            WHERE telegram_id = ?
        ''', (telegram_id,))
        return cursor.fetchall()

def obter_usuarios():
    """Retorna os usuários cadastrados para as tarefas recorrentes."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_id FROM usuarios")
        return [linha[0] for linha in cursor.fetchall()]

def obter_itens_para_lembrete(telegram_id: int):
    """Retorna itens ativos cujo adiamento já terminou."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT i.id, i.telegram_id, i.nome_produto, i.quantidade,
                   i.unidade_medida, i.data_adicao, i.ultimo_consumo,
                   i.ultimo_lembrete, i.lembrar_depois, c.nome
            FROM itens_despensa AS i
            LEFT JOIN categorias AS c ON c.id = i.categoria_id
            WHERE i.telegram_id = ?
              AND i.quantidade > 0
              AND (i.lembrar_depois IS NULL OR i.lembrar_depois <= CURRENT_TIMESTAMP)
            ORDER BY i.data_adicao ASC
        ''', (telegram_id,))
        return cursor.fetchall()

def registrar_lembrete(item_id: int, telegram_id: int) -> bool:
    """Registra que um lembrete foi enviado para o item."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE itens_despensa
            SET ultimo_lembrete = CURRENT_TIMESTAMP
            WHERE id = ? AND telegram_id = ?
        ''', (item_id, telegram_id))
        conn.commit()
        return cursor.rowcount > 0

def adiar_lembrete(item_id: int, telegram_id: int, dias: int = 7) -> bool:
    """Adia o próximo lembrete do item."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE itens_despensa
            SET ultimo_lembrete = CURRENT_TIMESTAMP,
                lembrar_depois = datetime('now', ?)
            WHERE id = ? AND telegram_id = ?
        ''', (f"+{dias} days", item_id, telegram_id))
        conn.commit()
        return cursor.rowcount > 0

def esvaziar_despensa(telegram_id: int) -> int:
    """Remove todos os itens da despensa do usuário e retorna a quantidade removida."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM itens_despensa WHERE telegram_id = ?",
            (telegram_id,),
        )
        conn.commit()
        return cursor.rowcount

def obter_item_por_nome(telegram_id: int, nome_produto: str):
    """Retorna o primeiro item do usuário com o nome informado."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, nome_produto, quantidade, unidade_medida
            FROM itens_despensa
            WHERE telegram_id = ? AND lower(nome_produto) = lower(?)
            ORDER BY id
            LIMIT 1
        ''', (telegram_id, nome_produto.strip()))
        return cursor.fetchone()

def consumir_quantidade_item(item_id: int, telegram_id: int, quantidade_subtrair: str) -> str:
    """
    Subtrai a quantidade de um item. 
    Se quantidade_subtrair for 'TUDO' ou a subtração zerar o item, ele é deletado.
    Retorna uma string com o status para o bot exibir.
    """
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        
        # Pega a quantidade atual e o nome do item
        cursor.execute("SELECT nome_produto, quantidade FROM itens_despensa WHERE id = ? AND telegram_id = ?", (item_id, telegram_id))
        item = cursor.fetchone()
        
        if not item:
            return "Item não encontrado."
            
        nome, qtd_atual = item

        if quantidade_subtrair == 'TUDO':
            cursor.execute(
                "DELETE FROM itens_despensa WHERE id = ? AND telegram_id = ?",
                (item_id, telegram_id),
            )
            conn.commit()
            return f"Você consumiu todo o estoque de {nome}. Item removido!"
            
        try:
            # Converte a quantidade para float para fazer a matemática
            qtd_sub = float(quantidade_subtrair)
            if not math.isfinite(qtd_sub) or qtd_sub <= 0:
                return "A quantidade consumida deve ser maior que zero."
            nova_qtd = qtd_atual - qtd_sub
            
            if nova_qtd <= 0:
                cursor.execute("DELETE FROM itens_despensa WHERE id = ?", (item_id,))
                conn.commit()
                return f"Estoque de {nome} zerado e removido da despensa!"
            else:
                cursor.execute('''
                    UPDATE itens_despensa
                    SET quantidade = ?, ultimo_consumo = CURRENT_TIMESTAMP,
                        ultimo_lembrete = NULL, lembrar_depois = NULL
                    WHERE id = ? AND telegram_id = ?
                ''', (nova_qtd, item_id, telegram_id))
                conn.commit()
                return f"Baixa registrada! Restam {nova_qtd:.2f} de {nome}."
        except ValueError:
            return "Erro ao calcular a quantidade."

# Executa a criação das tabelas assim que este arquivo for importado
inicializar_banco()
