import sqlite3
from flask import Flask, render_template, request, redirect, url_for, jsonify
import datetime
import csv
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)

# Configuração do Banco de Dados SQLite
def init_db():
    conn = sqlite3.connect('gestao.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS estoque (
                 id INTEGER PRIMARY KEY,
                 produto TEXT,
                 codigo_barras TEXT,
                 quantidade INTEGER,
                 validade DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS clientes (
                 id INTEGER PRIMARY KEY,
                 regiao TEXT,
                 cidade TEXT,
                 num_loja TEXT,
                 potencia_loja TEXT,
                 num_cim TEXT,
                 endereco TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS auditoria (
                 id INTEGER PRIMARY KEY,
                 acao TEXT,
                 data TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS entradas (
                 id INTEGER PRIMARY KEY,
                 produto_id INTEGER,
                 quantidade INTEGER,
                 data TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS saidas (
                 id INTEGER PRIMARY KEY,
                 produto_id INTEGER,
                 quantidade INTEGER,
                 cliente_id INTEGER,
                 data TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

# Função para log de auditoria
def log_auditoria(acao):
    conn = sqlite3.connect('gestao.db')
    c = conn.cursor()
    c.execute("INSERT INTO auditoria (acao, data) VALUES (?, ?)", (acao, datetime.datetime.now()))
    conn.commit()
    conn.close()

# Configuração da API do Google Drive 
SCOPES = ['https://www.googleapis.com/auth/drive.file']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'

def get_drive_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(requests.Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

# Rotas
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/estoque', methods=['GET', 'POST'])
def estoque():
    if request.method == 'POST':
        produto = request.form['produto']
        codigo_barras = request.form['codigo_barras']
        quantidade = int(request.form['quantidade'])
        validade = request.form['validade']
        conn = sqlite3.connect('gestao.db')
        c = conn.cursor()
        c.execute("INSERT INTO estoque (produto, codigo_barras, quantidade, validade) VALUES (?, ?, ?, ?)", 
                  (produto, codigo_barras, quantidade, validade))
        produto_id = c.lastrowid
        c.execute("INSERT INTO entradas (produto_id, quantidade, data) VALUES (?, ?, ?)", 
                  (produto_id, quantidade, datetime.datetime.now()))
        conn.commit()
        conn.close()
        log_auditoria(f"Entrada de produto: {produto} (ID: {produto_id})")
        return redirect(url_for('estoque'))
    conn = sqlite3.connect('gestao.db')
    c = conn.cursor()
    c.execute("SELECT * FROM estoque")
    itens = c.fetchall()
    vencidos = [item for item in itens if datetime.datetime.strptime(item[4], '%Y-%m-%d') < datetime.datetime.now()]
    conn.close()
    return render_template('estoque.html', itens=itens, vencidos=vencidos)

@app.route('/saida', methods=['GET', 'POST'])
def saida():
    if request.method == 'POST':
        codigo_barras = request.form['codigo_barras']
        quantidade = int(request.form['quantidade'])
        cliente_id = int(request.form['cliente_id'])
        conn = sqlite3.connect('gestao.db')
        c = conn.cursor()
        # Verifica cliente existe
        c.execute("SELECT id FROM clientes WHERE id = ?", (cliente_id,))
        if not c.fetchone():
            conn.close()
            return "Cliente não encontrado!", 400
        # Busca produto por codigo_barras
        c.execute("SELECT id, quantidade FROM estoque WHERE codigo_barras = ?", (codigo_barras,))
        produto = c.fetchone()
        if not produto or produto[1] < quantidade:
            conn.close()
            return "Produto não encontrado ou estoque insuficiente!", 400
        produto_id = produto[0]
        # Atualiza estoque
        c.execute("UPDATE estoque SET quantidade = quantidade - ? WHERE id = ?", (quantidade, produto_id))
        # Registra saida
        c.execute("INSERT INTO saidas (produto_id, quantidade, cliente_id, data) VALUES (?, ?, ?, ?)", 
                  (produto_id, quantidade, cliente_id, datetime.datetime.now()))
        conn.commit()
        conn.close()
        log_auditoria(f"Saída de produto ID {produto_id} para cliente {cliente_id}")
        return redirect(url_for('saida'))
    return render_template('saida.html')

@app.route('/clientes', methods=['GET', 'POST'])
def clientes():
    if request.method == 'POST':
        regiao = request.form['regiao']
        cidade = request.form['cidade']
        num_loja = request.form['num_loja']
        potencia_loja = request.form['potencia_loja']
        num_cim = request.form['num_cim']
        endereco = request.form['endereco']
        if not all([regiao, cidade, num_loja, potencia_loja, num_cim, endereco]):
            return "Campos obrigatórios faltando!", 400
        conn = sqlite3.connect('gestao.db')
        c = conn.cursor()
        c.execute("INSERT INTO clientes (regiao, cidade, num_loja, potencia_loja, num_cim, endereco) VALUES (?, ?, ?, ?, ?, ?)",
                  (regiao, cidade, num_loja, potencia_loja, num_cim, endereco))
        conn.commit()
        conn.close()
        log_auditoria(f"Cadastrado cliente: {num_loja}")
        return redirect(url_for('clientes'))
    conn = sqlite3.connect('gestao.db')
    c = conn.cursor()
    c.execute("SELECT * FROM clientes")
    clientes_list = c.fetchall()
    conn.close()
    return render_template('clientes.html', clientes=clientes_list)

@app.route('/auditoria')
def auditoria():
    conn = sqlite3.connect('gestao.db')
    c = conn.cursor()
    c.execute("SELECT * FROM auditoria ORDER BY data DESC")
    logs = c.fetchall()
    conn.close()
    return render_template('auditoria.html', logs=logs)

@app.route('/export_auditoria')
def export_auditoria():
    conn = sqlite3.connect('gestao.db')
    c = conn.cursor()
    c.execute("SELECT * FROM auditoria")
    logs = c.fetchall()
    conn.close()
    with open('auditoria.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['ID', 'Ação', 'Data'])
        writer.writerows(logs)
    return "Exportado para auditoria.csv"

# Relatórios
@app.route('/relatorio_entradas', methods=['GET', 'POST'])
def relatorio_entradas():
    if request.method == 'POST':
        data_inicio = request.form['data_inicio']
        data_fim = request.form['data_fim']
        conn = sqlite3.connect('gestao.db')
        c = conn.cursor()
        c.execute('''SELECT e.id, est.produto, e.quantidade, e.data 
                     FROM entradas e JOIN estoque est ON e.produto_id = est.id 
                     WHERE e.data BETWEEN ? AND ?''', (data_inicio, data_fim))
        dados = c.fetchall()
        conn.close()
        return render_template('relatorio.html', titulo='Relatório de Entradas', dados=dados, colunas=['ID', 'Produto', 'Quantidade', 'Data'])
    return render_template('form_periodo.html', tipo='entradas')

@app.route('/relatorio_saidas', methods=['GET', 'POST'])
def relatorio_saidas():
    if request.method == 'POST':
        data_inicio = request.form['data_inicio']
        data_fim = request.form['data_fim']
        conn = sqlite3.connect('gestao.db')
        c = conn.cursor()
        c.execute('''SELECT s.id, est.produto, s.quantidade, s.data 
                     FROM saidas s JOIN estoque est ON s.produto_id = est.id 
                     WHERE s.data BETWEEN ? AND ?''', (data_inicio, data_fim))
        dados = c.fetchall()
        conn.close()
        return render_template('relatorio.html', titulo='Relatório de Saídas', dados=dados, colunas=['ID', 'Produto', 'Quantidade', 'Data'])
    return render_template('form_periodo.html', tipo='saidas')

@app.route('/relatorio_saidas_clientes', methods=['GET', 'POST'])
def relatorio_saidas_clientes():
    if request.method == 'POST':
        data_inicio = request.form['data_inicio']
        data_fim = request.form['data_fim']
        conn = sqlite3.connect('gestao.db')
        c = conn.cursor()
        c.execute('''SELECT s.id, est.produto, s.quantidade, c.num_loja AS cliente, s.data 
                     FROM saidas s JOIN estoque est ON s.produto_id = est.id 
                     JOIN clientes c ON s.cliente_id = c.id 
                     WHERE s.data BETWEEN ? AND ?''', (data_inicio, data_fim))
        dados = c.fetchall()
        conn.close()
        return render_template('relatorio.html', titulo='Relatório de Saídas por Clientes', dados=dados, colunas=['ID', 'Produto', 'Quantidade', 'Cliente', 'Data'])
    return render_template('form_periodo.html', tipo='saidas_clientes')

@app.route('/backup_nuvem')
def backup_nuvem():
    try:
        service = get_drive_service()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_metadata = {'name': f'gestao_backup_{timestamp}.db'}
        media = MediaFileUpload('gestao.db', mimetype='application/octet-stream')
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        log_auditoria(f"Backup realizado no Google Drive: {file.get('id')}")
        return "Backup realizado com sucesso no Google Drive!"
    except Exception as e:
        return f"Erro no backup: {str(e)} (Verifique conexão e credentials.json)"

if __name__ == '__main__':
    import webbrowser
    url = 'http://127.0.0.1:5000/'
    webbrowser.open(url)
    app.run(debug=False)