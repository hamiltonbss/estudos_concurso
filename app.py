from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from datetime import datetime, timedelta
import sqlite3
import os
from werkzeug.utils import secure_filename

# Configuração inicial do Flask
app = Flask(__name__)
app.secret_key = 'secret_key_estudos'
app.config['DATABASE'] = os.path.join(os.path.dirname(__file__), 'data', 'database.db')
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'data', 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'txt'}
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1MB

# Garante que os diretórios existam
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.dirname(app.config['DATABASE']), exist_ok=True)

# Context processor para injetar variáveis em todos os templates
@app.context_processor
def inject_now():
    return {
        'now': datetime.now(),
        'app_name': 'Controle de Estudos'
    }

# Filtro personalizado para formatação de datas
@app.template_filter('datetimeformat')
def datetimeformat(value, format='%d/%m/%Y'):
    if value is None:
        return ""
    if isinstance(value, str):
        value = datetime.strptime(value, '%Y-%m-%d')
    return value.strftime(format)

# Funções auxiliares do banco de dados
def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS concursos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            banca TEXT,
            data_prova TEXT NOT NULL,
            data_criacao TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS disciplinas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_concurso INTEGER NOT NULL,
            nome TEXT NOT NULL,
            prioridade TEXT CHECK(prioridade IN ('alta', 'media', 'baixa')) DEFAULT 'media',
            peso INTEGER DEFAULT 1,
            FOREIGN KEY (id_concurso) REFERENCES concursos(id) ON DELETE CASCADE
        )''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS topicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_disciplina INTEGER NOT NULL,
            nome TEXT NOT NULL,
            prioridade TEXT CHECK(prioridade IN ('alta', 'media', 'baixa')) DEFAULT 'media',
            horas_estimadas INTEGER DEFAULT 1,
            estudado BOOLEAN DEFAULT 0,
            nivel_compreensao TEXT CHECK(nivel_compreensao IN ('facil', 'medio', 'dificil')),
            data_estudo TEXT,
            horas_estudadas REAL DEFAULT 0,
            FOREIGN KEY (id_disciplina) REFERENCES disciplinas(id) ON DELETE CASCADE
        )''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessoes_estudo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_topico INTEGER NOT NULL,
            data TEXT NOT NULL,
            horas REAL NOT NULL,
            nivel_compreensao TEXT CHECK(nivel_compreensao IN ('facil', 'medio', 'dificil')),
            observacoes TEXT,
            FOREIGN KEY (id_topico) REFERENCES topicos(id) ON DELETE CASCADE
        )''')
        
        conn.commit()
    except Exception as e:
        print(f"Erro ao inicializar o banco de dados: {str(e)}")
        raise
    finally:
        conn.close()

# Funções auxiliares para arquivos
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Rotas principais
@app.route('/')
def index():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT c.*, 
               COUNT(t.id) as total_topicos,
               SUM(CASE WHEN t.estudado THEN 1 ELSE 0 END) as topicos_estudados
        FROM concursos c
        LEFT JOIN disciplinas d ON c.id = d.id_concurso
        LEFT JOIN topicos t ON d.id = t.id_disciplina
        GROUP BY c.id
        ORDER BY c.data_prova
        ''')
        
        concursos = []
        for row in cursor.fetchall():
            progresso = (row['topicos_estudados'] / row['total_topicos'] * 100) if row['total_topicos'] > 0 else 0
            concursos.append({
                'id': row['id'],
                'nome': row['nome'],
                'banca': row['banca'],
                'data_prova': row['data_prova'],
                'progresso': round(progresso, 1)
            })
        
        return render_template('index.html', concursos=concursos)
    except Exception as e:
        flash(f'Erro ao carregar concursos: {str(e)}', 'error')
        return render_template('index.html', concursos=[])
    finally:
        conn.close()

@app.route('/adicionar_concurso', methods=['POST'])
def adicionar_concurso():
    nome = request.form.get('nome')
    banca = request.form.get('banca')
    data_prova = request.form.get('data_prova')
    
    if not nome or not data_prova:
        flash('Preencha pelo menos nome e data da prova!', 'error')
        return redirect(url_for('index'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO concursos (nome, banca, data_prova)
        VALUES (?, ?, ?)
        ''', (nome, banca, data_prova))
        conn.commit()
        flash('Concurso adicionado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao adicionar concurso: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('index'))

@app.route('/concurso/<int:id_concurso>')
def view_concurso(id_concurso):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Informações do concurso
        cursor.execute('SELECT * FROM concursos WHERE id = ?', (id_concurso,))
        concurso = cursor.fetchone()
        
        if not concurso:
            flash('Concurso não encontrado!', 'error')
            return redirect(url_for('index'))
        
        # Disciplinas e tópicos
        cursor.execute('''
        SELECT d.*, 
               COUNT(t.id) as total_topicos,
               SUM(CASE WHEN t.estudado THEN 1 ELSE 0 END) as topicos_estudados
        FROM disciplinas d
        LEFT JOIN topicos t ON d.id = t.id_disciplina
        WHERE d.id_concurso = ?
        GROUP BY d.id
        ORDER BY d.prioridade DESC, d.nome
        ''', (id_concurso,))
        
        disciplinas = []
        for disciplina in cursor.fetchall():
            progresso = (disciplina['topicos_estudados'] / disciplina['total_topicos'] * 100) if disciplina['total_topicos'] > 0 else 0
            disciplinas.append({
                'id': disciplina['id'],
                'nome': disciplina['nome'],
                'prioridade': disciplina['prioridade'],
                'peso': disciplina['peso'],
                'progresso': round(progresso, 1)
            })
        
        # Dias restantes
        data_prova = datetime.strptime(concurso['data_prova'], '%Y-%m-%d')
        dias_restantes = (data_prova - datetime.now()).days
        
        return render_template('concurso.html',
                            concurso=concurso,
                            disciplinas=disciplinas,
                            dias_restantes=dias_restantes)
    except Exception as e:
        flash(f'Erro ao carregar concurso: {str(e)}', 'error')
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route('/disciplina/<int:id_disciplina>')
def view_disciplina(id_disciplina):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Informações da disciplina
        cursor.execute('''
        SELECT d.*, c.nome as nome_concurso, c.data_prova
        FROM disciplinas d
        JOIN concursos c ON d.id_concurso = c.id
        WHERE d.id = ?
        ''', (id_disciplina,))
        disciplina = cursor.fetchone()
        
        if not disciplina:
            flash('Disciplina não encontrada!', 'error')
            return redirect(url_for('index'))
        
        # Tópicos
        cursor.execute('''
        SELECT * FROM topicos
        WHERE id_disciplina = ?
        ORDER BY prioridade DESC, nome
        ''', (id_disciplina,))
        topicos = cursor.fetchall()
        
        # Progresso
        total_topicos = len(topicos)
        topicos_estudados = sum(1 for t in topicos if t['estudado'])
        progresso = (topicos_estudados / total_topicos * 100) if total_topicos > 0 else 0
        
        # Dias restantes
        data_prova = datetime.strptime(disciplina['data_prova'], '%Y-%m-%d')
        dias_restantes = (data_prova - datetime.now()).days
        
        return render_template('disciplina.html',
                            disciplina=disciplina,
                            topicos=topicos,
                            progresso=round(progresso, 1),
                            dias_restantes=dias_restantes)
    except Exception as e:
        flash(f'Erro ao carregar disciplina: {str(e)}', 'error')
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route('/adicionar_disciplina/<int:id_concurso>', methods=['POST'])
def adicionar_disciplina(id_concurso):
    nome = request.form.get('nome')
    prioridade = request.form.get('prioridade', 'media')
    peso = request.form.get('peso', 1)
    
    if not nome:
        flash('Nome da disciplina é obrigatório!', 'error')
        return redirect(url_for('view_concurso', id_concurso=id_concurso))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO disciplinas (id_concurso, nome, prioridade, peso)
        VALUES (?, ?, ?, ?)
        ''', (id_concurso, nome, prioridade, peso))
        conn.commit()
        flash('Disciplina adicionada com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao adicionar disciplina: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('view_concurso', id_concurso=id_concurso))

@app.route('/adicionar_topico/<int:id_disciplina>', methods=['POST'])
def adicionar_topico(id_disciplina):
    nome = request.form.get('nome')
    prioridade = request.form.get('prioridade', 'media')
    horas_estimadas = request.form.get('horas_estimadas', 1)
    
    if not nome:
        flash('Nome do tópico é obrigatório!', 'error')
        return redirect(url_for('view_disciplina', id_disciplina=id_disciplina))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO topicos (id_disciplina, nome, prioridade, horas_estimadas)
        VALUES (?, ?, ?, ?)
        ''', (id_disciplina, nome, prioridade, horas_estimadas))
        conn.commit()
        flash('Tópico adicionado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao adicionar tópico: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('view_disciplina', id_disciplina=id_disciplina))

@app.route('/importar_topicos/<int:id_disciplina>', methods=['POST'])
def importar_topicos(id_disciplina):
    if 'arquivo' not in request.files:
        flash('Nenhum arquivo enviado', 'error')
        return redirect(url_for('view_disciplina', id_disciplina=id_disciplina))
    
    arquivo = request.files['arquivo']
    if arquivo.filename == '':
        flash('Nenhum arquivo selecionado', 'error')
        return redirect(url_for('view_disciplina', id_disciplina=id_disciplina))
    
    if not allowed_file(arquivo.filename):
        flash('Tipo de arquivo não permitido. Use apenas .txt', 'error')
        return redirect(url_for('view_disciplina', id_disciplina=id_disciplina))
    
    try:
        filename = secure_filename(arquivo.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        arquivo.save(filepath)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            topicos = [linha.strip() for linha in f if linha.strip()]
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for topico in topicos:
            cursor.execute('''
            INSERT INTO topicos (id_disciplina, nome)
            VALUES (?, ?)
            ''', (id_disciplina, topico))
        
        conn.commit()
        flash(f'{len(topicos)} tópicos importados com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao importar tópicos: {str(e)}', 'error')
    finally:
        if 'conn' in locals():
            conn.close()
        if os.path.exists(filepath):
            os.remove(filepath)
    
    return redirect(url_for('view_disciplina', id_disciplina=id_disciplina))

@app.route('/registrar_estudo/<int:id_topico>', methods=['POST'])
def registrar_estudo(id_topico):
    horas = request.form.get('horas')
    nivel_compreensao = request.form.get('nivel_compreensao', 'medio')
    observacoes = request.form.get('observacoes', '')
    
    if not horas:
        flash('Informe as horas estudadas!', 'error')
        return redirect(url_for('view_disciplina', id_disciplina=get_disciplina_id(id_topico)))
    
    try:
        horas = float(horas)
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Registrar sessão de estudo
        cursor.execute('''
        INSERT INTO sessoes_estudo (id_topico, data, horas, nivel_compreensao, observacoes)
        VALUES (?, datetime('now'), ?, ?, ?)
        ''', (id_topico, horas, nivel_compreensao, observacoes))
        
        # Atualizar status do tópico
        cursor.execute('''
        UPDATE topicos 
        SET estudado = 1,
            nivel_compreensao = ?,
            data_estudo = datetime('now'),
            horas_estudadas = horas_estudadas + ?
        WHERE id = ?
        ''', (nivel_compreensao, horas, id_topico))
        
        conn.commit()
        flash('Estudo registrado com sucesso!', 'success')
    except ValueError:
        flash('Horas devem ser um número válido!', 'error')
    except Exception as e:
        flash(f'Erro ao registrar estudo: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('view_disciplina', id_disciplina=get_disciplina_id(id_topico)))

def get_disciplina_id(id_topico):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id_disciplina FROM topicos WHERE id = ?', (id_topico,))
        return cursor.fetchone()['id_disciplina']
    finally:
        conn.close()

@app.route('/atualizar_status_topico/<int:id_topico>', methods=['POST'])
def atualizar_status_topico(id_topico):
    estudado = request.form.get('estudado', 0)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Atualiza apenas o status de estudado
        cursor.execute('UPDATE topicos SET estudado = ? WHERE id = ?', (estudado, id_topico))
        
        conn.commit()
        flash('Status do tópico atualizado!', 'success')
    except Exception as e:
        flash(f'Erro ao atualizar tópico: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('view_disciplina', id_disciplina=get_disciplina_id(id_topico)))

@app.route('/gerar_cronograma/<int:id_concurso>', methods=['GET', 'POST'])
def gerar_cronograma(id_concurso):
    if request.method == 'POST':
        horas_por_dia = float(request.form.get('horas_por_dia', 3))
    else:
        horas_por_dia = 3  # Valor padrão
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Informações do concurso
        cursor.execute('SELECT * FROM concursos WHERE id = ?', (id_concurso,))
        concurso = cursor.fetchone()
        
        if not concurso:
            flash('Concurso não encontrado!', 'error')
            return redirect(url_for('index'))
        
        # Obter tópicos não estudados para estudo principal
        cursor.execute('''
        SELECT t.id, t.nome, d.nome as disciplina, d.prioridade
        FROM topicos t
        JOIN disciplinas d ON t.id_disciplina = d.id
        WHERE d.id_concurso = ? AND t.estudado = 0
        ORDER BY d.prioridade DESC, t.prioridade DESC, d.peso DESC, t.nome
        ''', (id_concurso,))
        topicos_estudo = cursor.fetchall()
        
        # Obter tópicos já estudados para revisão/exercícios
        cursor.execute('''
        SELECT t.id, t.nome, d.nome as disciplina, d.prioridade
        FROM topicos t
        JOIN disciplinas d ON t.id_disciplina = d.id
        WHERE d.id_concurso = ? AND t.estudado = 1
        ORDER BY d.prioridade DESC, t.data_estudo ASC, t.prioridade DESC
        ''', (id_concurso,))
        topicos_revisao = cursor.fetchall()
        
        # Calcular cronograma
        data_prova = datetime.strptime(concurso['data_prova'], '%Y-%m-%d')
        dias_restantes = (data_prova - datetime.now()).days
        cronograma = []
        data_atual = datetime.now().date()
        indice_revisao = 0
        
        for i, topico_estudo in enumerate(topicos_estudo):
            # Estudo principal (2/3 do tempo)
            horas_estudo = horas_por_dia * 2 / 3
            horas_str = formatar_horas(horas_estudo)
            
            cronograma.append({
                'data': data_atual.strftime('%Y-%m-%d'),
                'tipo': 'Estudo',
                'disciplina': topico_estudo['disciplina'],
                'topico': topico_estudo['nome'],
                'horas': horas_str
            })
            
            # Exercícios (1/3 do tempo) - pega um tópico já estudado
            horas_exercicios = horas_por_dia * 1 / 3
            horas_ex_str = formatar_horas(horas_exercicios)
            
            topico_exercicio = {
                'disciplina': 'Nenhuma',
                'topico': 'Revisão geral'
            }
            
            if topicos_revisao:
                topico_exercicio = topicos_revisao[indice_revisao % len(topicos_revisao)]
                indice_revisao += 1
            
            cronograma.append({
                'data': data_atual.strftime('%Y-%m-%d'),
                'tipo': 'Exercícios',
                'disciplina': topico_exercicio['disciplina'],
                'topico': f"Exercícios: {topico_exercicio['nome']}",
                'horas': horas_ex_str
            })
            
            data_atual += timedelta(days=1)
            if data_atual >= data_prova.date():
                break
        
        return render_template('cronograma.html',
                            concurso=concurso,
                            cronograma=cronograma,
                            horas_por_dia=horas_por_dia,
                            dias_restantes=dias_restantes)
    except Exception as e:
        flash(f'Erro ao gerar cronograma: {str(e)}', 'error')
        return redirect(url_for('view_concurso', id_concurso=id_concurso))
    finally:
        conn.close()

def formatar_horas(horas_decimais):
    """
    Converte horas decimais para formato 'Xh Ymin'
    Exemplo: 1.5 → '1h 30min'
    """
    horas = int(horas_decimais)
    minutos = round((horas_decimais - horas) * 60)
    
    if minutos == 0:
        return f"{horas}h"
    elif horas == 0:
        return f"{minutos}min"
    else:
        return f"{horas}h {minutos}min"

# Inicialização do aplicativo
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True)