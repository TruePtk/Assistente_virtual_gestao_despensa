import sqlite3
import os

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
                FOREIGN KEY (telegram_id) REFERENCES usuarios (telegram_id),
                FOREIGN KEY (categoria_id) REFERENCES categorias (id)
            )
        ''')
        
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

def salvar_item_despensa(telegram_id: int, nome_produto: str, quantidade: float, unidade_medida: str, nome_categoria: str):
    """Salva o item extraído pela IA na despensa."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        
        # Busca o ID da categoria que veio da IA
        cursor.execute("SELECT id FROM categorias WHERE nome = ?", (nome_categoria,))
        resultado_cat = cursor.fetchone()
        
        # Se não achar a categoria exata, joga para 'Outros' (que é o ID 6 na nossa lista acima)
        categoria_id = resultado_cat[0] if resultado_cat else 6 
        
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
            SET quantidade = quantidade + ?
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
            cursor.execute("DELETE FROM itens_despensa WHERE id = ?", (item_id,))
            conn.commit()
            return f"Você consumiu todo o estoque de {nome}. Item removido!"
            
        try:
            # Converte a quantidade para float para fazer a matemática
            qtd_sub = float(quantidade_subtrair)
            nova_qtd = qtd_atual - qtd_sub
            
            if nova_qtd <= 0:
                cursor.execute("DELETE FROM itens_despensa WHERE id = ?", (item_id,))
                conn.commit()
                return f"Estoque de {nome} zerado e removido da despensa!"
            else:
                cursor.execute("UPDATE itens_despensa SET quantidade = ? WHERE id = ?", (nova_qtd, item_id))
                conn.commit()
                return f"Baixa registrada! Restam {nova_qtd:.2f} de {nome}."
        except ValueError:
            return "Erro ao calcular a quantidade."

# Executa a criação das tabelas assim que este arquivo for importado
inicializar_banco()