import os
from flask import Flask, jsonify, request, render_template
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# A inicialização padrão do Flask procura templates na pasta 'templates'
app = Flask(__name__)

# --- CONFIGURAÇÃO DA BASE DE DADOS ---
# Obtém o URL da base de dados e corrige o prefixo se necessário (de postgres:// para postgresql://)
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODELOS DA BASE DE DADOS (TABELAS) ---

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_completo = db.Column(db.String(150), nullable=False)
    usuario = db.Column(db.String(80), unique=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='atendente')

class Atendimento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entrada = db.Column(db.String(100))
    data = db.Column(db.Date, nullable=False)
    hora = db.Column(db.Time, nullable=False)
    cpf = db.Column(db.String(20))
    ra = db.Column(db.String(20))
    tipo_solicitante = db.Column(db.String(100))
    nome_aluno = db.Column(db.String(150), nullable=False)
    curso = db.Column(db.String(100))
    atendente = db.Column(db.String(150))
    motivo = db.Column(db.String(150))
    descricao = db.Column(db.Text, nullable=False)
    resolvido_fcr = db.Column(db.String(10))
    area_acionada = db.Column(db.String(100), nullable=True)

class Option(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    table_name = db.Column(db.String(50), nullable=False)
    nome = db.Column(db.String(150), unique=False, nullable=False)

# --- FUNÇÃO PARA INICIAR A BASE DE DADOS ---
def init_db():
    with app.app_context():
        db.create_all()
        # Verifica se o utilizador admin já existe
        if not Usuario.query.filter_by(usuario='admin').first():
            admin_pass = generate_password_hash('Cyy7030347044032[cYt]', method='pbkdf2:sha256')
            admin = Usuario(nome_completo='Administrador', usuario='admin', senha_hash=admin_pass, role='admin')
            db.session.add(admin)

            # Opções padrão
            options_data = {
                'canais': ['PRESENCIAL', 'WHATSAPP'], 'tipos': ['ALUNO', 'CANDIDATO', 'REPRESENTANTE'],
                'cursos': ['MEDICINA', 'DIREITO', 'PSICOLOGIA'], 'motivos': ['Académico', 'Financeiro', 'Solicitação de documentos'],
                'areas': ['Secretaria', 'Tesouraria', 'Coordenação']
            }
            for table, names in options_data.items():
                for name in names:
                    db.session.add(Option(table_name=table, nome=name))
            
            db.session.commit()

# --- ROTAS PRINCIPAIS (FRONTEND) ---
@app.route('/')
def index():
    # Usa render_template, o método padrão e mais robusto do Flask para servir páginas HTML.
    return render_template('index.html')

# --- ROTAS DA API (BACKEND) ---

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = Usuario.query.filter_by(usuario=data['username']).first()
    if user and check_password_hash(user.senha_hash, data['password']):
        return jsonify({
            'id': user.id,
            'nome_completo': user.nome_completo,
            'role': user.role
        })
    return jsonify({'error': 'Utilizador ou senha inválidos'}), 401

@app.route('/api/initial_data', methods=['GET'])
def get_initial_data():
    tables = ['usuarios', 'canais', 'tipos', 'cursos', 'motivos', 'areas']
    options = {}
    for table in tables:
        if table == 'usuarios':
            users = Usuario.query.order_by(Usuario.nome_completo).all()
            options[table] = [{'id': u.id, 'nome_completo': u.nome_completo, 'usuario': u.usuario, 'role': u.role} for u in users]
        else:
            items = Option.query.filter_by(table_name=table).order_by(Option.nome).all()
            options[table] = [{'id': i.id, 'nome': i.nome} for i in items]
    return jsonify({'options': options})

@app.route('/api/atendimentos', methods=['POST'])
def add_atendimento():
    data = request.get_json()
    new_atendimento = Atendimento(
        entrada=data['entrada'],
        data=datetime.strptime(data['data'], '%Y-%m-%d').date(),
        hora=datetime.strptime(data['hora'], '%H:%M:%S').time(),
        cpf=data.get('cpf'),
        ra=data.get('ra'),
        tipo_solicitante=data['tipo_solicitante'],
        nome_aluno=data['nome_aluno'],
        curso=data['curso'],
        atendente=data['atendente'],
        motivo=data['motivo'],
        descricao=data['descricao'],
        resolvido_fcr=data['resolvido_fcr'],
        area_acionada=data.get('area_acionada')
    )
    db.session.add(new_atendimento)
    db.session.commit()
    return jsonify({'id': new_atendimento.id}), 201

@app.route('/api/atendimentos/search', methods=['POST'])
def search_atendimentos():
    filters = request.get_json()
    query = Atendimento.query

    if filters.get('ra'):
        query = query.filter(Atendimento.ra.ilike(f"%{filters['ra']}%"))
    if filters.get('cpf'):
        query = query.filter(Atendimento.cpf.ilike(f"%{filters['cpf']}%"))
    if filters.get('nome'):
        query = query.filter(Atendimento.nome_aluno.ilike(f"%{filters['nome']}%"))
    if filters.get('motivo'):
        query = query.filter_by(motivo=filters['motivo'])
    if filters.get('data_inicio'):
        query = query.filter(Atendimento.data >= datetime.strptime(filters['data_inicio'], '%Y-%m-%d').date())
    if filters.get('data_fim'):
        query = query.filter(Atendimento.data <= datetime.strptime(filters['data_fim'], '%Y-%m-%d').date())
    
    results = query.order_by(Atendimento.id.desc()).all()
    atendimentos = [
        {
            'id': a.id, 'data': a.data.isoformat(), 'hora': a.hora.isoformat(),
            'ra': a.ra, 'cpf': a.cpf, 'nome_aluno': a.nome_aluno,
            'motivo': a.motivo, 'atendente': a.atendente, 'curso': a.curso,
            'tipo_solicitante': a.tipo_solicitante, 'resolvido_fcr': a.resolvido_fcr,
            'area_acionada': a.area_acionada, 'descricao': a.descricao
        } for a in results
    ]
    return jsonify(atendimentos)

@app.route('/api/find_student', methods=['POST'])
def find_student():
    data = request.get_json()
    if data['type'] == 'ra' and data['value']:
        student = Atendimento.query.filter_by(ra=data['value']).order_by(Atendimento.id.desc()).first()
    elif data['type'] == 'cpf' and data['value']:
        student = Atendimento.query.filter_by(cpf=data['value']).order_by(Atendimento.id.desc()).first()
    else:
        student = None

    if student:
        return jsonify({'nome_aluno': student.nome_aluno, 'ra': student.ra, 'cpf': student.cpf, 'curso': student.curso})
    return jsonify({'error': 'Estudante não encontrado'}), 404

@app.route('/api/change_password', methods=['POST'])
def change_password():
    data = request.get_json()
    user = Usuario.query.get(data['id'])
    if not user or not check_password_hash(user.senha_hash, data['oldPassword']):
        return jsonify({'error': 'Senha anterior incorreta'}), 400
    
    user.senha_hash = generate_password_hash(data['newPassword'], method='pbkdf2:sha256')
    db.session.commit()
    return jsonify({'message': 'Senha alterada com sucesso'}), 200

# --- ROTAS DE ADMINISTRAÇÃO ---

def get_admin_model(table_name):
    return Usuario if table_name == 'usuarios' else Option

@app.route('/api/admin/<table>', methods=['POST'])
def admin_add(table):
    Model = get_admin_model(table)
    data = request.get_json()
    if Model == Usuario:
        if not data.get('senha'):
            return jsonify({'error': 'A senha é obrigatória para novos utilizadores'}), 400
        hashed_pass = generate_password_hash(data['senha'], method='pbkdf2:sha256')
        new_item = Usuario(nome_completo=data['nome_completo'], usuario=data['usuario'], senha_hash=hashed_pass, role=data['role'])
    else:
        new_item = Option(table_name=table, nome=data['nome'])
    
    db.session.add(new_item)
    db.session.commit()
    return jsonify({'id': new_item.id}), 201

@app.route('/api/admin/<table>/<int:id>', methods=['PUT'])
def admin_update(table, id):
    Model = get_admin_model(table)
    item = Model.query.get_or_404(id)
    data = request.get_json()

    if Model == Usuario:
        item.nome_completo = data.get('nome_completo', item.nome_completo)
        item.usuario = data.get('usuario', item.usuario)
        item.role = data.get('role', item.role)
        if data.get('senha'):
            item.senha_hash = generate_password_hash(data['senha'], method='pbkdf2:sha256')
    else:
        item.nome = data.get('nome', item.nome)

    db.session.commit()
    return jsonify({'message': 'Item atualizado'}), 200

@app.route('/api/admin/<table>/<int:id>', methods=['DELETE'])
def admin_delete(table, id):
    Model = get_admin_model(table)
    item = Model.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({}), 204


if __name__ == '__main__':
    # Esta parte não é executada na Render, mas é útil para testes locais
    init_db()
    app.run(debug=True)

