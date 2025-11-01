import sqlite3
from contextlib import closing
import atexit
import time
import unicodedata
import matplotlib
matplotlib.use('Agg')
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from cs50 import SQL
from flask_cors import CORS
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
from pytz import timezone
import os, time, requests, threading
import pandas as pd
import logging
logging.getLogger('matplotlib').setLevel(logging.WARNING)
import subprocess
import requests
import re
from twilio.rest import Client
from dotenv import load_dotenv
import jwt
import json
import os, re, unicodedata 


from werkzeug.utils import secure_filename
var = False 
manipule = False
if manipule:
    subprocess.run(['python','manipule.py'])

# Inicialização do app Flask e SocketIO
app = Flask(
    __name__,
    static_folder='/data',      # pasta que vai servir arquivos
    static_url_path='/data'    # endereço para acessar esses arquivos
)

load_dotenv()
app.config['SECRET_KEY'] = os.getenv("MOST_SECRET_KEY",'quero-quero17')
socketio = SocketIO(app, cors_allowed_origins="*")
import shutil


SECRET_KEY = os.getenv("MOST_SECRET_KEY", 'quero-quero17')

print('SECRET_KEY',SECRET_KEY)
ACCOUNT_SID = os.getenv("ACCOUNT_SID_TWILIO",'ACe2b44d7bd27f18525eb33dd4ea8b891a')
AUTH_TOKEN  = os.getenv("AUTH_TOKEN_TWILIO",'a03519e493ce0f003228acfaa3e669c2')
VERIFY_SID  = os.getenv("VERIFY_SID",'VAda3089a24c0b290e57138ff2c44f7016') 



client = Client(ACCOUNT_SID, AUTH_TOKEN)

CORS(
    app,
    resources={r"/*": {"origins": '*'}},
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)



connected_carts = {}


def _register_carrinho_room(carrinho):
    """Associate the current Socket.IO session with a cart room."""
    if not carrinho:
        return None

    try:
        sid = getattr(request, 'sid', None)
    except RuntimeError:
        sid = None
    if not sid:
        return carrinho

    current = connected_carts.get(sid)
    if current == carrinho:
        return carrinho

    if current:
        leave_room(current, sid=sid)

    join_room(carrinho, sid=sid)
    connected_carts[sid] = carrinho
    return carrinho


def emit_for_carrinho(event, payload, *, broadcast, carrinho=None, include_self=True):
    """Emit helper that limits broadcasts to the caller's cart when requested."""
    if broadcast and carrinho:
        socketio.emit(event, payload, room=carrinho, include_self=include_self)
    elif broadcast:
        socketio.emit(event, payload, include_self=include_self)
    else:
        emit(event, payload, include_self=include_self)


def decode_number_jwt(token: str) -> int:
    decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    # decoded é dict; o sub tem o número
    print(decoded['sub'])
    return int(decoded["sub"])

@app.route("/validate_table_number_on_qr", methods=['POST'])
def validate_table_number_on_qr():
    try:
        print('validate')
        data = request.get_json()
        print('data',data)
        numero = data.get('numero')
        print('numero',numero)
        if not numero:
            return jsonify({'valid': False}), 200
        tableNumber = decode_number_jwt(numero)
        print('tablenumver',tableNumber)
        if 1 <= tableNumber <= 80:
            return jsonify({'valid': True,'tableNumber':tableNumber}), 200
        return jsonify({'valid': False}), 200
    except Exception as e:
        print('erro ao validar numero:', e)
        return jsonify({'valid': False}), 200



@app.route("/auth/sms/create", methods=["POST"])
def send_verification():
    try:
        print('creatingsms')
        phone = request.json.get("phone")
        print('phone',phone)
        verification = client.verify.v2.services('VAda3089a24c0b290e57138ff2c44f7016').verifications.create(to='+5513978258866', channel='sms')
        print(verification.sid)
        return jsonify({"status": 'pending'}), 200
    except Exception as e:
        print('erro no envio:', e)
        return jsonify({"status": 'error'}), 200

@app.route("/auth/sms/check", methods=["POST"])
def check_verification():
    try:
        print('verification')
        phone = request.json.get("phone")
        code = request.json.get("code")
        chk = client.verify.v2.services(VERIFY_SID).verification_checks.create(to=phone, code=code)
        print(chk)
        return jsonify({"status": 'approved'}), 200  # 'approved' se ok
    except Exception as e:
        print('erro na verificacao:', e)
        return jsonify({"status": 'denied'}), 200

@app.route('/pegar_pagamentos_comanda', methods=['POST'])
def pegar_pagamentos_comanda():
    data = request.get_json()
    comanda = data.get('comanda')
    carrinho = data.get('carrinho', 'NossoPoint')
    dia = datetime.now(brazil).date()
    pagamentos = db.execute('SELECT * FROM pagamentos WHERE comanda = ? AND dia = ? AND ordem = 0 AND carrinho = ?',comanda,dia,carrinho)
    if not pagamentos:
        pagamentos = []
    return {'pagamentos': pagamentos}

@socketio.on('excluir_pedido')
def excluir_pedido(data):
    try:
        pedido_id = data.get('id')
        carrinho = data.get('carrinho', 'NossoPoint')
        db.execute('DELETE FROM pedidos WHERE id = ?', pedido_id)
    except Exception as e:
        print('Erro ao excluir pedido:', e)
    getPedidos({'emitir': True, 'carrinho': carrinho})
    getComandas({'emitir': True, 'carrinho': carrinho})
    getPedidosCC({'emitir': True, 'carrinho': carrinho})
    handle_get_cardapio(data.get('comanda'), carrinho)
    
@app.route('/excluir_pagamento', methods=['POST'])
def excluir_pagamento():
    try:
        data = request.get_json()
        pagamento_id = data.get('pagamento_id')
        ids = db.execute('SELECT ids FROM pagamentos WHERE id = ?', pagamento_id)
        comanda = data.get('comanda')
        carrinho = data.get('carrinho', 'NossoPoint')
        if ids and ids[0]['ids']:
            ids_list = json.loads(ids[0]['ids'])
            print('ids_list', ids_list)
            for row in ids_list:
                db.execute('UPDATE pedidos SET quantidade_paga = quantidade_paga - ?, preco = preco_unitario *NULLIF((quantidade-(quantidade_paga - ?)),0) WHERE id = ? AND dia = ?',row['quantidade'],row['quantidade'],row['id'],datetime.now(brazil).date())
        db.execute('DELETE FROM pagamentos WHERE id = ?', pagamento_id)
        
        handle_get_cardapio(comanda, carrinho)
        return jsonify({'status': 'success'}),200
    except Exception as e:
        print('Erro ao excluir pagamento:', e)
        return jsonify({'status': 'error', 'message': str(e)}), 500

if var:
    DATABASE_PATH = "/data/dados.db"
    if not os.path.exists(DATABASE_PATH):
        shutil.copy("dados.db", DATABASE_PATH)
    db = SQL("sqlite:///" + DATABASE_PATH)
else:
    DATABASE_PATH = "data/dados.db"
    db=SQL("sqlite:///" + DATABASE_PATH)

brazil = timezone('America/Sao_Paulo')

os.makedirs(app.static_folder, exist_ok=True)



# def now_utc_iso():
#     return datetime.now(pytz.utc).isoformat()
# def expires_in_minutes_iso(minutes: int):
#     return (datetime.now(pytz.utc) + timedelta(minutes=minutes)).isoformat()
# def generate_code(n: int = 6) -> str:
#     return f"{random.randint(0, 10**n - 1):0{n}d}"


@app.route("/")
def home():
    return "Aplicação funcionando!", 200



@app.route('/validate_token_on_qr', methods=['POST'])
def validate_token_on_qr():
    try:
        print('entrou validate token')
        print('validate token')
        data = request.get_json()
        print('data',data)
        token = data.get('token')
        print('token',token)
        exist = db.execute('SELECT dataUpdateToken FROM clientes WHERE token = ?', token)
        if exist:
            data_update = exist[0]['dataUpdateToken']
            if isinstance(data_update, str):
                try:
                    # tenta converter do formato padrão ISO (YYYY-MM-DD)
                    data_update_date = datetime.strptime(data_update, "%Y-%m-%d").date()
                except ValueError:
                    # se vier num formato inesperado, tenta com hora
                    data_update_date = datetime.fromisoformat(data_update).date()
            else:
                data_update_date = data_update
            print('data_update',data_update_date)
            if data_update_date < datetime.now(brazil).date() + timedelta(days=5):
                print('valid token')
                return jsonify({'valid': True}), 200
        print('invalid token or expired')
        return jsonify({'valid': False}), 200
    except Exception as e:
        print('erro ao validar token:', e)
        return jsonify({'valid': False}), 200

@app.route('/guardar_login', methods=['POST'])
def guardar_login():
    
    print('entrou guardar login')
    data = request.get_json()
    number = str(data.get('numero'))
    

    if not number:
        print('sem numero')
        return jsonify({"error": "Campo 'number' é obrigatório."}), 400
    else:
        print('number',number)
    
    # Busca 1 usuário; evite depender de != 'bloqueado' no WHERE para mensagens claras
    
    payload = {
    "sub": f"{number}",      # identificador do usuário (pode ser id, CPF, etc.)
    "name": f"nome:{number}",  # nome do usuário
    "iat": int(time.time()),  # emitido em (timestamp)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    print('token',token)
    rows = db.execute('SELECT numero, nome, status FROM clientes WHERE numero = ? LIMIT 1', number)
    print('rows')
    if not rows:
        db.execute('INSERT INTO clientes (numero,nome,status,token,dataUpdateToken) VALUES (?,?,?,?,?)',number,f'nome:{number}','aprovado',token,datetime.now().date())
        rows = [{'numero':number,'nome':f'nome:{number}','status':'aprovado'}]
        print('novo usuario inserido')
    
    else:
        db.execute('UPDATE clientes SET token = ?, dataUpdateToken = ? WHERE numero = ?',token,datetime.now().date(),number)

    user = rows[0]
    if user.get('status') == 'bloqueado':
        print('usuario bloqueado')
        return jsonify({"error": "Usuário bloqueado."}), 403

    
    
    return jsonify({"authToken": token}), 200


@app.route('/salvarTokenCargo', methods=['POST'])
#!!
def salvarTokenCargo():
    data = request.get_json()
    username = data.get('username')
    cargo = data.get('cargo')
    token = data.get('token')
    carrinho = data.get('carrinho')
    print(f'data {data}, username {username}, token {token}')
    if db.execute('SELECT * FROM tokens WHERE token =?',token):
        db.execute('DELETE FROM tokens WHERE token = ?',token)
    if token and token!='semtoken':
        db.execute('INSERT INTO tokens (username,cargo,token,carrinho) VALUES (?,?,?,?)',username,cargo,token,carrinho)
    

    return "cargo e user inserido com sucesso"

def enviar_notificacao_expo(cargo,titulo,corpo,token_user,carrinho, canal="default"):
    print(f'cargo {cargo} titulo, {titulo},corpo {corpo} canal {canal}')
    if cargo:
        tokens = db.execute('SELECT token FROM tokens WHERE carrinho = ? AND cargo = ? AND token != ? GROUP BY token',carrinho,cargo,'semtoken')
    else:
        tokens = db.execute('SELECT token FROM tokens WHERE token != ? AND carrinho = ? GROUP BY token','semtoken', carrinho)
    tokens = [row for row in tokens if row['token'] != token_user]
    respostas = []
    for row in tokens:
        token = row['token']
        url = "https://exp.host/--/api/v2/push/send"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        payload = {
            "to": token,
            "title": titulo,
            "body": corpo,
            "sound": "default",
            "android_channel_id": canal  # precisa estar igual ao definido no app
        }
        res = requests.post(url, json=payload, headers=headers)
        respostas.append(res.json())  # Armazena o conteúdo da resposta, não o objeto
    print(respostas)
    return respostas



def atualizar_faturamento_diario():
    db.execute('UPDATE usuarios SET liberado = ? WHERE cargo != ?',0,'ADM')
    db.execute('DELETE FROM tokens WHERE cargo!=? AND username != ?','ADM','cozinha_principal')
    dia = datetime.now(brazil).date()
    db.execute('INSERT INTO pedidos (pedido,comanda,dia, ordem) VALUES (?,?,?,?)','Comanda Aberta','controle de estoque',dia,0)
    db.execute('INSERT INTO pedidos (pedido,comanda,dia, ordem) VALUES (?,?,?,?)','Comanda Aberta','pago na hora',dia,0)
    end_p_dict = db.execute('SELECT products,status FROM promotions WHERE endDate < ? ',datetime.now(brazil).date().strftime('%Y-%m-%d'))
    if end_p_dict:
        db.execute('UPDATE promotions SET status = ? WHERE endDate < ?','expired',datetime.now(brazil).date().strftime('%Y-%m-%d'))
        for row in end_p_dict:
            itens = json.loads(row.get('products',[]))
            for item in itens:
                db.execute('UPDATE cardapio SET preco = preco_base WHERE id = ?',item['id'])




# Agendador para rodar à meia-noite
scheduler = BackgroundScheduler()
scheduler.add_job(atualizar_faturamento_diario, 'cron', hour=0, minute=5, timezone = brazil)
scheduler.start()

# Garante que o scheduler pare quando encerrar o servidor
atexit.register(lambda: scheduler.shutdown())

@app.route('/opcoes', methods=['POST'])
def opc():
    #!!
    print('entrou no opcoes')
    data = request.get_json()
    item = data.get('pedido')
    carrinho=data.get('carrinho')
    print(item) 
    opcoes = db.execute('SELECT opcoes FROM cardapio WHERE item = ? AND carrinho = ?', item,carrinho)
    if opcoes:
        palavra = ''
        selecionaveis = []
        dados = []
        for i in opcoes[0]['opcoes']:
            if i == '(':
                nome_selecionavel = palavra
                print(nome_selecionavel)
                palavra = ''
            elif i == '-':
                selecionaveis.append(palavra)
                palavra = ''
            elif i == ')':
                selecionaveis.append(palavra)
                dados.append({nome_selecionavel: selecionaveis})
                selecionaveis = []
                palavra = ''
            else:
                palavra += i
        print(dados)
        return {'options': dados}


@app.route('/pegar_pedidos', methods=['POST'])
def pegar_pedidos():
    # Pegando os dados do JSON enviado na requisição
    data = request.get_json()
    comanda = data.get('comanda')
    ordem = data.get('ordem')
    carrinho = data.get('carrinho')
    if int(ordem) != 0:
        
        print(f'ORDEM : {ordem}')
        dia = datetime.now(brazil).date()
        dados = db.execute('''
                SELECT pedido, id, ordem, SUM(quantidade) AS quantidade, SUM(preco) AS preco
                FROM pedidos WHERE comanda = ? AND ordem = ? AND dia = ? AND pedido != ? AND carrinho = ?
                GROUP BY pedido, (preco/quantidade)
            ''', comanda, int(ordem),dia, 'Comanda Aberta', carrinho)
    
        return{'data':dados,'preco':''}
    else:
        print('ordem 0')
        handle_get_cardapio(comanda, carrinho)
        return{'status':'success'}





@app.route('/verificar_username', methods=['POST'])
def verificar_usu():
    data = request.json
    username = data.get('username')
    print(username)
    senha = data.get('senha')
    print(senha)
    existe = db.execute(
        'SELECT * FROM usuarios WHERE username =? AND senha =? AND liberado=?', username, senha, '1')
    if existe:
        print('true')
        return {'data': True, 'cargo': existe[0]['cargo'], 'carrinho':existe[0]['carrinho']}
    else:
        print('false')
        return {'data': False}


@app.route('/verificar_quantidade', methods=['POST'])
def verif_quantidade():
    #!!
    data = request.json  # Use request.json para pegar o corpo da requisição
    item = data.get('item')
    quantidade = data.get('quantidade')
    carrinho = data.get('carrinho')
    print(f'Item: {item}, Quantidade: {quantidade}')

    categoria = db.execute(
        'SELECT categoria_id FROM cardapio WHERE item = ? AND carrinho =?', item, carrinho)

    if categoria and categoria[0]['categoria_id'] == 1:
        verificar_estoque = db.execute(
            'SELECT quantidade,estoque_ideal FROM estoque WHERE item = ?AND carrinho =?', item, carrinho)

        if verificar_estoque:
            estoque_atual = float(verificar_estoque[0]['quantidade'])
            if estoque_atual - float(quantidade) < 0:
                print('estoque insuficiente')
                return {'erro': 'Estoque insuficiente', 'quantidade': estoque_atual}
            elif estoque_atual:
                estoque_ideal = verificar_estoque[0]['estoque_ideal']
                if estoque_ideal:
                    alerta = 7 if item!='tropical' and item!='red bull' else 3
                    if estoque_atual<alerta:
                        print('estoque baixo')
                        return {'erro': False, 'quantidade': estoque_atual}
    print('estoque ok')
    return {'erro': False}

@app.route('/transferir_comanda', methods=['POST'])
def transferir_comanda():
    try:
        data = request.get_json()
        comanda_origem = data.get('comanda_origem')
        comanda_destino = data.get('comanda_destino')
        carrinho = data.get('carrinho')

        if not comanda_origem or not comanda_destino:
            return jsonify({'error': 'Both source and destination comandas must be provided.'}), 400

        if comanda_origem == comanda_destino:
            return jsonify({'error': 'Source and destination comandas must be different.'}), 400

        # Fetch orders from the source comanda
        db.execute("UPDATE pedidos SET comanda = ? WHERE comanda = ? AND ordem = ? AND dia = ? AND carrinho = ?", comanda_destino, comanda_origem, 0, datetime.now().date(), carrinho)
        db.execute("UPDATE pagamentos SET comanda = ? WHERE comanda = ? AND ordem = ? AND dia = ? AND carrinho = ?", comanda_destino, comanda_origem, 0, datetime.now().date(), carrinho)
        getPedidos({'emitir': True, 'carrinho': carrinho})
        getComandas({'emitir': True, 'carrinho': carrinho})
        handle_get_cardapio(comanda_destino, carrinho)
        
        return jsonify({'message': 'Orders transferred successfully.'}), 200
        
    except Exception as e:
        print('erro ao transferir comanda:', e)
        return jsonify({'error': str(e)}), 500

@app.route('/updatePrinted', methods=['POST'])
def update_printed():
    data = request.json or {}
    pedido_id = data.get('pedidoId')
    carrinho = data.get('carrinho')
    if not pedido_id:
        return jsonify({'status': 'error', 'message': 'pedidoId ausente'}), 400

    # CORREÇÃO: definir printed = 1 e passar parâmetros corretamente
    db.execute('UPDATE pedidos SET printed = ? WHERE id = ? AND carrinho = ?', 1, pedido_id, carrinho)
    return jsonify({'status': 'success'}), 200


@app.route('/getPendingPrintOrders', methods=['POST'])
def get_pending_print_orders():
    print('getPendingPrintOrders')
    data = request.json or {}
    carrinho = data.get('carrinho')

    # opcional: permitir que o cliente mande printed/ordem; manter defaults
    printed = 0
    ordem = 0

    dia = datetime.now(brazil).date()
    inicio_limite = (datetime.now(brazil) - timedelta(minutes=25)).strftime('%H:%M')

    # CORREÇÃO: usar tupla de parâmetros
    pedidos = db.execute(
        'SELECT * FROM pedidos WHERE printed = ? AND ordem = ? AND dia = ? AND inicio > ? AND categoria = ? AND carrinho = ? ORDER BY inicio ASC',
        printed, ordem, dia, inicio_limite, 1, carrinho
    )
    pedidos_formatados = []
    if pedidos:
        for row in pedidos:
            mesa = row['comanda']
            pedido = row['pedido']
            quantidade = row['quantidade']
            extra = row['extra']
            hora = row['inicio']
            id = row['id']
            username = row['username']
            pedidos_formatados.append({
                'mesa': mesa,
                'pedido': pedido,
                'quantidade': quantidade,
                'extra': extra,
                'hora': hora,
                'id': id,
                'sendBy': username
            })


    # Se seu db.execute retorna cursor, talvez precise fetchall()
    # pedidos = db.execute(...).fetchall()

    print('pedidos', pedidos)
    return jsonify({'pedidos': pedidos_formatados}), 200

@socketio.on('connect')
def handle_connect():
    print(f'Cliente conectado:{request.sid}')


@socketio.on('getCardapio')
def getCardapio(data):
    emitirBroadcast = data.get('emitir')
    carrinho = data.get('carrinho')
    print("Carrinho", carrinho)
    _register_carrinho_room(carrinho)
    dataCardapio = db.execute("SELECT * FROM cardapio WHERE carrinho = ? ORDER BY item ASC", carrinho)
    if emitirBroadcast:
        emit_for_carrinho('respostaCardapio', {'dataCardapio': dataCardapio}, broadcast=True, carrinho=carrinho)
    else:
        emit_for_carrinho('respostaCardapio', {'dataCardapio': dataCardapio}, broadcast=False, carrinho=carrinho)

@socketio.on('getCarrinhos')
def getCarrinhos(data):
    if isinstance(data, dict):
        emitirBroadcast = data.get('emitir', True)
        carrinho = data.get('carrinho')
    else:
        emitirBroadcast = data if isinstance(data, bool) else True
        carrinho = None

    if carrinho:
        _register_carrinho_room(carrinho)

    carrinhos = db.execute('SELECT * FROM carrinhos')
    print('getCarrinhos')
    print('carrinhos',carrinhos)
    emit_for_carrinho('respostaCarrinhos', {'carrinhos': carrinhos}, broadcast=emitirBroadcast, carrinho=carrinho)


@socketio.on('getPedidosCC')
def getPedidosCC(data):
    print('getPedidos')
    if isinstance(data, dict):
        emitirBroadcast = data.get('emitir', True)
        carrinho = data.get('carrinho')
    else:
        emitirBroadcast = data if isinstance(data, bool) else True
        carrinho = 'NossoPoint'

    print('emitirBroadcast', emitirBroadcast)
    print('carrinho', carrinho)
    _register_carrinho_room(carrinho)
    dia = datetime.now(brazil).date()
    dataPedidos = db.execute('SELECT * FROM pedidos WHERE dia = ? AND pedido != ? AND carrinho = ?',dia,'Comanda Aberta',carrinho)
    if not dataPedidos:
        dataPedidos = []
    if emitirBroadcast:
        emit_for_carrinho('respostaPedidosCC', {'dataPedidos': dataPedidos}, broadcast=True, carrinho=carrinho)
    else:
        emit_for_carrinho('respostaPedidosCC', {'dataPedidos': dataPedidos}, broadcast=False, carrinho=carrinho)

@socketio.on('getPedidos')
def getPedidos(data):
    print('getPedidos')
    if isinstance(data, dict):
        emitirBroadcast = data.get('emitir', True)
        carrinho = data.get('carrinho')
    print('emitirBroadcast', emitirBroadcast)
    print('carrinho', carrinho)
    _register_carrinho_room(carrinho)
    dia = datetime.now(brazil).date()
    dataPedidos = db.execute('SELECT * FROM pedidos WHERE dia = ? AND pedido != ? AND carrinho = ?',dia,'Comanda Aberta',carrinho)
    if not dataPedidos:
        dataPedidos = []
    if emitirBroadcast:
        emit_for_carrinho('respostaPedidos', {'dataPedidos': dataPedidos}, broadcast=True, carrinho=carrinho)
    else:
        emit_for_carrinho('respostaPedidos', {'dataPedidos': dataPedidos}, broadcast=False, carrinho=carrinho)

@socketio.on('getItensPromotion')
def getPedidosPromotion(data):
    #!!
    emitirBroadcast=data.get('emitir')
    carrinho = data.get("carrinho")
    _register_carrinho_room(carrinho)
    dataCardapio = db.execute('SELECT id,item FROM cardapio WHERE carrinho = ?', carrinho)
    if dataCardapio:
        emit_for_carrinho('respostaItensPromotion', {'dataCardapio': dataCardapio}, broadcast=emitirBroadcast, carrinho=carrinho)

@socketio.on('getEstoque')
def getEstoque(data):
    emitirBroadcast=data.get('emitir')
    carrinho=data.get('carrinho')
    _register_carrinho_room(carrinho)
    dataEstoque=db.execute('SELECT * FROM estoque WEHRE carrinho = ? ORDER BY item', carrinho)
    if dataEstoque:
        emit_for_carrinho('respostaEstoque', {'dataEstoque': dataEstoque}, broadcast=emitirBroadcast, carrinho=carrinho)

@socketio.on('getEstoqueGeral')
def getEstoqueGeral(data):
    emitirBroadcast=data.get('emitir')
    carrinho=data.get('carrinho')
    _register_carrinho_room(carrinho)
    dataEstoqueGeral=db.execute('SELECT * FROM estoque_geral WHERE carrinho = ? ORDER BY item', carrinho)
    if dataEstoqueGeral:
        emit_for_carrinho('respostaEstoqueGeral', {'dataEstoqueGeral': dataEstoqueGeral}, broadcast=emitirBroadcast, carrinho=carrinho)


@socketio.on('getComandas')
def getComandas(data):
    if isinstance(data, dict):
        emitirBroadcast = data.get('emitir', True)
        carrinho = data.get('carrinho')

    _register_carrinho_room(carrinho)
    dia = datetime.now(brazil).date()
    sql_abertas = """
        SELECT comanda
        FROM pedidos
        WHERE ordem = ? AND dia = ? AND carrinho = ?
        GROUP BY comanda
        ORDER BY
        CASE
            WHEN comanda GLOB '[0-9]*' THEN CAST(comanda AS INTEGER)
            ELSE NULL
        END,
        comanda ASC
        """
    dados_comandaAberta = db.execute(sql_abertas, 0, dia, carrinho)

    dados_comandaFechada = db.execute(
        'SELECT comanda,ordem FROM pedidos WHERE ordem !=? AND dia = ? AND carrinho = ? GROUP BY comanda ORDER BY comanda ASC', 0,dia, carrinho)
    if dados_comandaAberta or dados_comandaFechada:
        if emitirBroadcast:
            emit_for_carrinho('respostaComandas', {'dados_comandaAberta': dados_comandaAberta, 'dados_comandaFechada': dados_comandaFechada}, broadcast=True, carrinho=carrinho)
        else:
            emit_for_carrinho('respostaComandas', {'dados_comandaAberta': dados_comandaAberta, 'dados_comandaFechada': dados_comandaFechada}, broadcast=False, carrinho=carrinho)


@socketio.on('users')
def users(data):
    emitirBroadcast=data.get('emitir')
    carrinho=data.get('carrinho')
    _register_carrinho_room(carrinho)
    users = db.execute('SELECT * from usuarios WHERE carrinho = ?', carrinho)
    emit_for_carrinho('usuarios', {'users': users}, broadcast=emitirBroadcast, carrinho=carrinho)


@socketio.on('disconnect')
def handle_disconnect():
    try:
        sid = getattr(request, 'sid', None)
    except RuntimeError:
        sid = None
    if sid:
        carrinho = connected_carts.pop(sid, None)
        if carrinho:
            leave_room(carrinho, sid=sid)
    print('Cliente desconectado')

# Manipulador para inserir dados


@socketio.on('refresh')
def refresh():
    handle_connect()

@socketio.on('EditingEstoque')
def editEstoque(data):
    print('editar estoque')
    carrinho = data.get('carrinho')
    tipo = data.get('tipo')
    item = data.get('item')
    novoNome = data.get('novoNome')
    quantidade = data.get('quantidade')
    estoque_ideal = data.get('estoqueIdeal')
    estoque = data.get('estoque')
    usuario = data.get('username')
    token_user = data.get('token')
    mudar_os_dois = data.get('mudar_os_dois')
    print("item", tipo)
    print("item", item)
    print("item", quantidade)
    print("item", estoque_ideal)
    print("estoque", estoque)
    alteracao = f'{item}'
    if not item: emit(f'{estoque}Alterado', {'erro':'Item nao identificado'})
    if tipo == 'Adicionar':
        tipo = 'Adicionou'
        if estoque_ideal:
            alteracao+=f' com estoque ideal de {estoque_ideal}'
        print("Entrou no adicionar")                                            
        if db.execute(f'SELECT item FROM {estoque} WHERE item = ? AND carrinho = ?',item, carrinho): emit(f'{estoque}Alterado',{'erro':'Nome Igual'})
        db.execute(f"INSERT INTO {estoque} (item,quantidade,estoque_ideal,carrinho) VALUES (?,?,?,?)",item,quantidade,estoque_ideal, carrinho)
        if mudar_os_dois:
            alteracao+=' em ambos os estoques'
            estoque_sec = 'estoque' if estoque=='estoque_geral' else 'estoque_geral'
            if not db.execute(f'SELECT item FROM {estoque_sec} WHERE item = ? AND carrinho = ?',item, carrinho): db.execute(f"INSERT INTO {estoque_sec} (item,quantidade,estoque_ideal,carrinho) VALUES (?,?,?,?)",item,0,0,carrinho)

    elif tipo == 'Remover':
        tipo='Removeu'
        db.execute(f"DELETE FROM {estoque} WHERE item=? AND carrinho = ?",item, carrinho)
        if mudar_os_dois:
            alteracao+=' de ambos os estoques'
            estoque_sec = 'estoque' if estoque=='estoque_geral' else 'estoque_geral'
            db.execute(f"DELETE FROM {estoque_sec} WHERE item=? AND carrinho = ?",item, carrinho)
    else:
        alteracao+=': alterou'
        tipo='Editou'
        antigo = db.execute(f'SELECT estoque_ideal FROM {estoque} WHERE item = ? AND carrinho = ?',item, carrinho)
        antig = 'inexistente' if not antigo else antigo[0]['estoque_ideal']
        if estoque_ideal and novoNome:
            if type(antig)!=str and int(estoque_ideal) != antig:
                alteracao += f' estoque ideal de {int(antig)} para {float(estoque_ideal)} e {item} para {novoNome}'
            else: alteracao+=f' {item} para {novoNome}'
            
            db.execute(f"UPDATE {estoque} SET item=?, estoque_ideal=? WHERE item=? AND carrinho = ?",novoNome, estoque_ideal,item, carrinho )
        elif estoque_ideal:
            if type(antig)!=str and int(estoque_ideal) != antig:
                alteracao+= f' estoque ideal de {int(antig)} para {estoque_ideal}'
            db.execute(f"UPDATE {estoque} SET estoque_ideal=? WHERE item=? AND carrinho = ?",estoque_ideal,item, carrinho)
        elif novoNome:
            alteracao+= f' Nome do {item} para {novoNome}'
            db.execute(f"UPDATE {estoque} SET item=? WHERE item=? AND carrinho = ?",novoNome,item, carrinho) 
            if mudar_os_dois:
                alteracao+=f' em ambos os estoques'
                estoque_sec = 'estoque' if estoque=='estoque_geral' else 'estoque_geral'
                db.execute(f"UPDATE {estoque_sec} SET item=? WHERE item=? AND carrinho = ?",novoNome,item, carrinho)

    insertAlteracoesTable(estoque,alteracao,tipo,f'Botao + no Editar {estoque}',usuario, carrinho)
    alteracao=f"{usuario} {tipo} {alteracao}"
    enviar_notificacao_expo('ADM','Estoque Editado',alteracao,token_user)
    if mudar_os_dois:
        getEstoqueGeral({'emitir':True,'carrinho':carrinho})
        getEstoque({'emitir':True,'carrinho':carrinho})
    elif estoque=='estoque_geral':
        getEstoqueGeral({'emitir':True,'carrinho':carrinho})
    else: getEstoque({'emitir':True,'carrinho':carrinho})
            
@socketio.on("editCargo")
def edit_cargo(data):
    carrinho = data.get('carrinho')
    print('editcargo')
    usuario=data.get("usuario")
    print (usuario)
    cargo=data.get("cargo")
    print(cargo)
    db.execute("UPDATE usuarios SET cargo = ? WHERE username = ? AND carrinho = ?", cargo, usuario, carrinho)
    users({'emitir':True,'carrinho':carrinho})
    
     



import json

def somar_extra_por_unidade(selection):
    """
    Soma 'valor_extra' das opções selecionadas na estrutura recebida.
    Aceita:
      - [ {nome, options:[{nome, valor_extra, ...}, ...]}, ... ]
      - { nome, options:[...] }
      - [ {nome, valor_extra}, ... ]  (lista de opções avulsas)
    Ignora options com 'selecionado': False
    """
    def _sum_from_groups(groups):
        total = 0.0
        for g in groups:
            if not isinstance(g, dict):
                continue
            opts = g.get('options') or g.get('opcoes') or []
            if not isinstance(opts, list):
                continue
            for opt in opts:
                if not isinstance(opt, dict):
                    continue
                if opt.get('selecionado') is False:
                    continue
                try:
                    total += float(opt.get('valor_extra') or 0)
                except Exception:
                    pass
        return total

    if not selection:
        return 0.0

    # caso seja dict de 1 grupo
    if isinstance(selection, dict):
        # se já parecer "grupo", trata como lista de grupos com 1 elemento
        if isinstance(selection.get('options') or selection.get('opcoes'), list):
            return _sum_from_groups([selection])
        # se for um dict genérico: tente encontrar 'groups/opcoes/options'
        groups = selection.get('groups') or selection.get('opcoes') or selection.get('options') or []
        if isinstance(groups, dict):
            groups = [groups]
        if isinstance(groups, list):
            # se cair aqui como lista de opções avulsas, embrulha
            if groups and isinstance(groups[0], dict) and 'valor_extra' in groups[0] and 'options' not in groups[0]:
                groups = [{'nome': 'Opções', 'options': groups}]
            return _sum_from_groups(groups)
        return 0.0

    # caso seja list
    if isinstance(selection, list):
        if not selection:
            return 0.0
        # se é lista de grupos? (primeiro tem 'options')
        first = selection[0]
        if isinstance(first, dict) and ('options' in first or 'opcoes' in first):
            return _sum_from_groups(selection)
        # se é lista de opções avulsas
        if isinstance(first, dict) and 'valor_extra' in first and 'options' not in first:
            return _sum_from_groups([{'nome': 'Opções', 'options': selection}])
        return 0.0

    return 0.0

@socketio.on('insert_order')
def handle_insert_order(data):
    try:
        dia = datetime.now(brazil).date()

        # ---------- Helpers ----------
        def to_list(x):
            if isinstance(x, list):
                return x
            if x is None:
                return []
            return [x]

        def parse_json_maybe(val):
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except Exception:
                    return val
            return val

        def get_or_default(seq, idx, default):
            if isinstance(seq, list):
                return seq[idx] if idx < len(seq) else default
            return seq if not isinstance(seq, (list, tuple)) else default

        # ---------- Campos base ----------
        comanda       = data.get('comanda') or ""
        pedidos       = to_list(data.get('pedidosSelecionados'))
        quantidades   = to_list(data.get('quantidadeSelecionada'))
        horario       = datetime.now(brazil).strftime('%H:%M')
        username      = data.get('username')
        preco_flag    = data.get('preco')  # brinde (mantém compat.)
        nomes         = to_list(data.get('nomeSelecionado'))
        token_user    = data.get('token_user')
        carrinho      = data.get('carrinho')
        _register_carrinho_room(carrinho)

        # opções estruturadas (podem vir str/json/list/dict)
        opcoesSelecionadas = parse_json_maybe(data.get('opcoesSelecionadas')) or []

        # "extraSelecionados" é texto livre (lista 1-para-1 com pedidos)
        extra_list    = to_list(data.get('extraSelecionados'))

        # ---------- Metadados de entrega (novos) ----------
        modo_entrega  = data.get('modo_entrega')      # 'carrinho' | 'residencial' | None
        carrinho_nome = (data.get('carrinho') or '').strip()  # ex: 'NossoPoint'
        endereco_cli  = (data.get('endereco') or '').strip()

        # define remetente/endereço conforme o modo
        if (modo_entrega or '').lower() == 'residencial':
            remetente_padrao     = 'Residencial'
            endereco_entrega_pad = endereco_cli
        else:
            # padrão/retrocompativel: carrinho
            remetente_padrao     = f'Carrinho:{carrinho_nome or carrinho}'
            endereco_entrega_pad = None  # sem endereço no modo carrinho

        # ---------- Seleção de opções por índice ----------
        def selecionar_opcoes_por_indice(idx):
            """
            Retorna a seleção de opções referente ao item idx.
            Aceita:
            A) lista alinhada por item: [ [grupos...], [grupos...] ]
            B) lista de grupos (apenas 1 item): [ {nome, options:[...]}, ... ]
            C) dict único de grupo: { nome, options:[...] }
            D) lista de opções avulsas: [ {nome, valor_extra}, ... ]
            """
            sel = opcoesSelecionadas
            if isinstance(sel, list):
                # alinhado por item?
                if idx < len(sel) and (isinstance(sel[idx], (list, dict))):
                    return sel[idx]
                # se há só 1 item no pedido, pode ter vindo a lista de grupos inteira
                if len(pedidos) == 1:
                    return sel
                return []
            elif isinstance(sel, dict):
                return sel
            else:
                return []

        # ---------- Soma de valor_extra (por unidade) ----------
        def somar_extra_por_unidade(selection):
            def _sum_from_groups(groups):
                total = 0.0
                for g in groups:
                    if not isinstance(g, dict):
                        continue
                    opts = g.get('options') or g.get('opcoes') or []
                    if not isinstance(opts, list):
                        continue
                    for opt in opts:
                        if not isinstance(opt, dict):
                            continue
                        # se vier um flag explicito "selecionado": False, ignora
                        if opt.get('selecionado') is False:
                            continue
                        try:
                            total += float(opt.get('valor_extra') or 0)
                        except Exception:
                            pass
                return total

            if not selection:
                return 0.0

            if isinstance(selection, dict):
                if isinstance(selection.get('options') or selection.get('opcoes'), list):
                    return _sum_from_groups([selection])
                groups = selection.get('groups') or selection.get('opcoes') or selection.get('options') or []
                if isinstance(groups, dict):
                    groups = [groups]
                if isinstance(groups, list):
                    if groups and isinstance(groups[0], dict) and 'valor_extra' in groups[0] and 'options' not in groups[0]:
                        groups = [{'nome': 'Opções', 'options': groups}]
                    return _sum_from_groups(groups)
                return 0.0

            if isinstance(selection, list):
                if not selection:
                    return 0.0
                first = selection[0]
                if isinstance(first, dict) and ('options' in first or 'opcoes' in first):
                    return _sum_from_groups(selection)
                if isinstance(first, dict) and 'valor_extra' in first and 'options' not in first:
                    return _sum_from_groups([{'nome': 'Opções', 'options': selection}])
                return 0.0

            return 0.0

        # ---------- Logs úteis ----------
        print("[insert_order] username:", username)
        print("[insert_order] comanda:", comanda)
        print("[insert_order] pedidos:", pedidos)
        print("[insert_order] quantidades:", quantidades)
        print("[insert_order] horario:", horario)
        print("[insert_order] nomes:", nomes)
        print("[insert_order] carrinho:", carrinho)
        print("[insert_order] modo_entrega:", modo_entrega, "| carrinho:", carrinho_nome, "| endereco:", endereco_cli)
        print("[insert_order] opcoesSelecionadas:", opcoesSelecionadas)

        # se nomes não veio, preenche com "-1"
        if not nomes:
            nomes = ["-1"] * len(pedidos)

        # ---------- Loop por item ----------
        for i, pedido in enumerate(pedidos):
            pedido = str(pedido).strip()
            if not pedido:
                continue

            quantidade = float(get_or_default(quantidades, i, 1) or 1)

            # preço/categoria do cardápio
            preco_unitario_row = db.execute(
                'SELECT preco, categoria_id FROM cardapio WHERE item = ?', pedido
            )

            if preco_unitario_row:
                categoria = preco_unitario_row[0]['categoria_id']
                if comanda != 'controle de estoque':
                    preco_base = float(preco_unitario_row[0]['preco'])
                else:
                    preco_base = 0.0
            else:
                categoria = 4
                preco_base = 0.0
                print('[insert_order] item não encontrado no cardápio:', pedido)

            # campos por item
            extra_txt      = (get_or_default(extra_list, i, "") or "").strip()
            nome_cliente   = get_or_default(nomes, i, "-1") or "-1"
            selecao_opcoes = selecionar_opcoes_por_indice(i)
            extra_unidade  = somar_extra_por_unidade(selecao_opcoes)
            opcoes_json    = json.dumps(selecao_opcoes or [], ensure_ascii=False)

            # ETA por categoria + notificação
            horario_entrega = None
            if categoria == 3:
                horario_entrega = (datetime.now(brazil) + timedelta(minutes=40)).strftime('%H:%M')
                enviar_notificacao_expo('Cozinha', 'Novo Pedido',
                                        f'{quantidade} {pedido} {extra_txt} na {comanda}', token_user, carrinho)
            elif categoria == 2:
                horario_entrega = (datetime.now(brazil) + timedelta(minutes=15)).strftime('%H:%M')
                enviar_notificacao_expo('Colaborador', 'Novo Pedido',
                                        f'{quantidade} {pedido} {extra_txt} na {comanda}', token_user, carrinho)

            # cálculo de preço
            preco_unitario_final = preco_base + float(extra_unidade or 0)
            preco_total          = preco_unitario_final * quantidade

            # remetente/endereço (por item; cai no padrão se não vier nada)
            remetente        = remetente_padrao
            endereco_entrega = endereco_entrega_pad

            # ---------- INSERT ----------
            if preco_flag:  # brinde: força 0
                db.execute(
                    'INSERT INTO pedidos (comanda, pedido, quantidade, preco, categoria, inicio, estado, extra, opcoes, username, ordem, nome, remetente, endereco_entrega, dia, horario_para_entrega, carrinho) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    comanda, pedido, quantidade, 0, categoria, horario, 'A Fazer',
                    extra_txt, opcoes_json, username, 0, nome_cliente, remetente, endereco_entrega, dia, horario_entrega, carrinho
                )

            elif not preco_unitario_row:  # fora do cardápio
                db.execute(
                    'INSERT INTO pedidos (comanda, pedido, quantidade, preco, categoria, inicio, estado, extra, opcoes, username, ordem, nome, remetente, endereco_entrega, dia, horario_para_entrega, carrinho) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    comanda, pedido, quantidade, 0, categoria, horario, 'A Fazer',
                    extra_txt, opcoes_json, username, 0, nome_cliente, remetente, endereco_entrega, dia, horario_entrega, carrinho
                )

            else:
                db.execute(
                    'INSERT INTO pedidos (comanda, pedido, quantidade, preco, preco_unitario, categoria, inicio, estado, extra, opcoes, username, ordem, nome, remetente, endereco_entrega, dia, horario_para_entrega, carrinho) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    comanda, pedido, quantidade,
                    preco_total, preco_unitario_final, categoria, horario, 'A Fazer',
                    extra_txt, opcoes_json, username, 0, nome_cliente, remetente, endereco_entrega, dia, horario_entrega, carrinho
                )

            # ---------- Eventos/estoque ----------
            if categoria == 1:
                new_id = db.execute("SELECT last_insert_rowid() AS id")[0]['id']
                hora   = datetime.now(brazil).strftime('%H:%M')
                emit_for_carrinho(
                    'emitir_pedido_restante',
                    {'mesa': comanda, 'pedido': pedido, 'quantidade': quantidade,
                     'extra': extra_txt, 'hora': hora, 'sendBy': username, 'id': new_id},
                    broadcast=True,
                    carrinho=carrinho,
                )
            elif categoria == 3:
                new_id = db.execute("SELECT last_insert_rowid() AS id")[0]['id']
                hora   = datetime.now(brazil).strftime('%H:%M')
                emit_for_carrinho(
                    'emitir_pedido_cozinha',
                    {'mesa': comanda, 'pedido': pedido, 'quantidade': quantidade,'remetente': remetente, 'endereco_entrega': endereco_entrega,'prazo': horario_entrega,
                     'extra': extra_txt, 'hora': hora, 'sendBy': username, 'id': new_id},
                    broadcast=True,
                    carrinho=carrinho,
                )

            quantidade_anterior = db.execute('SELECT quantidade FROM estoque WHERE item = ? AND carrinho = ?', pedido, carrinho)
            if quantidade_anterior:
                quantidade_nova = float(quantidade_anterior[0]['quantidade']) - quantidade
                db.execute('UPDATE estoque SET quantidade = ? WHERE item = ? AND carrinho = ?', quantidade_nova, pedido, carrinho)
                if quantidade_nova < 10:
                    emit_for_carrinho('alerta_restantes', {'quantidade': quantidade_nova, 'item': pedido}, broadcast=True, carrinho=carrinho)
                getEstoque({'emitir':True,'carrinho':carrinho})

        # Atualizações finais
        faturamento({'emitir': True, 'carrinho': carrinho})
        getPedidos({'emitir': True, 'carrinho': carrinho})
        getPedidosCC({'emitir': True, 'carrinho': carrinho})
        getComandas({'emitir': True, 'carrinho': carrinho})
        handle_get_cardapio(comanda, carrinho)

    except Exception as e:
        print("Erro ao inserir ordem:", e)
        emit('error', {'message': str(e)})



@socketio.on('faturamento')
def faturamento(data):

    if isinstance(data, dict):
        change = data.get('change', 0)
        dia = datetime.now(brazil).date() + timedelta(days=(change))
        dia_formatado = dia.strftime('%d/%m')
        emitir = data.get('emitir', True)
        carrinho = data.get('carrinho')
    else:
        dia = datetime.now(brazil).date()
        emitir = data if isinstance(data, bool) else True
        dia_formatado = dia.strftime('%d/%m')
        carrinho = 'NossoPoint'

    _register_carrinho_room(carrinho)
        
    metodosDict=db.execute("SELECT forma_de_pagamento,SUM(valor_total) AS valor_total FROM pagamentos WHERE dia =? AND carrinho = ? GROUP BY forma_de_pagamento",dia,carrinho)
    dinheiro=0
    credito=0
    debito=0
    pix=0
    for row in metodosDict:
        if row["forma_de_pagamento"]=="dinheiro":
            dinheiro+=row["valor_total"]
        elif row["forma_de_pagamento"]=="credito":
            credito+=row["valor_total"]
        elif row["forma_de_pagamento"]=="debito":
            debito+=row["valor_total"]
        elif row["forma_de_pagamento"]=="pix":
            pix+=row["valor_total"]

    # Executar a consulta e pegar o resultado
    caixinha = db.execute("SELECT COALESCE(SUM(caixinha),0) AS total_caixinha FROM pagamentos WHERE dia = ? AND carrinho = ?", dia, carrinho)
    caixinha = caixinha[0]['total_caixinha'] or 0
    dezporcento = db.execute("SELECT COALESCE(SUM(dez_por_cento),0) AS total_dezporcento FROM pagamentos WHERE dia = ? AND carrinho = ?", dia, carrinho)
    dezporcento = dezporcento[0]['total_dezporcento'] or 0
    desconto = db.execute("SELECT SUM(valor) AS total_desconto FROM pagamentos WHERE dia = ? AND tipo = ? AND carrinho = ?", dia, 'desconto', carrinho)
    desconto = desconto[0]['total_desconto'] or 0
        
    total_recebido = db.execute("SELECT SUM(valor_total) AS total_recebido FROM pagamentos WHERE dia = ? AND tipo = ? AND carrinho = ?", dia, 'normal', carrinho)
    total_recebido = total_recebido[0]['total_recebido'] or 0
    pedidosQuantDict = db.execute("""
        SELECT categoria,
               SUM(quantidade) AS quantidade_total,
               SUM(preco_unitario*NULLIF(quantidade,0))      AS preco_total
        FROM pedidos
        WHERE dia = ?
          AND pedido != ? AND carrinho = ?
        GROUP BY categoria
        ORDER BY categoria ASC
    """, dia, 'Comanda Aberta', carrinho)
    print('predidosQuantDict', pedidosQuantDict)
    drink = restante = porcao = 0
    faturamento_previsto = 0
    for row in pedidosQuantDict:
        cat = row.get('categoria')
        qtd = row.get('quantidade_total') or 0
        if cat == '1':
            restante = qtd
        elif cat == '2':
            drink = qtd
        elif cat == '3':
            porcao = qtd
        faturamento_previsto += (row.get('preco_total') or 0)

    pedidos = (drink or 0) + (restante or 0) + (porcao or 0)
    vendas_user = []
    vendas_user =db.execute('SELECT username, SUM(preco_unitario *NULLIF(quantidade,0)) AS valor_vendido, SUM(quantidade)  AS quant_vendida FROM pedidos WHERE dia = ? AND carrinho = ? GROUP BY username ORDER BY SUM(preco_unitario*NULLIF(quantidade,0)) DESC',dia, carrinho)
    print('vendas_user', vendas_user)

    emit_for_carrinho(
        'faturamento_enviar',
        {'dia': str(dia_formatado),
         'faturamento': total_recebido,
         'faturamento_previsto': faturamento_previsto,
         'drink': drink,
         'porcao': porcao,
         "restante": restante,
         "pedidos": pedidos,
         "caixinha": caixinha,
         "dezporcento": dezporcento,
         "desconto": desconto,
         "pix": pix,
         "debito": debito,
         "credito": credito,
         "dinheiro": dinheiro,
         "vendas_user": vendas_user},
        broadcast=emitir,
        carrinho=carrinho,
    )
    


@socketio.on('alterarValor')
def alterarValor(data):
    dia = datetime.now(brazil).date()
    valor = float(data.get('valor'))
    comanda = data.get('comanda')
    carrinho = data.get('carrinho')
    print(valor)
    horario = datetime.now(brazil).strftime('%H:%M')
    db.execute('INSERT INTO pagamentos(valor,valor_total,comanda,ordem,tipo,dia,horario,carrinho) VALUES (?,?,?,?,?,?,?,?)',valor,valor,comanda,0,'desconto',dia,horario,carrinho)
    faturamento({'emitir': True, 'carrinho': carrinho})
    handle_get_cardapio(comanda, carrinho)



from decimal import Decimal, InvalidOperation

# ... seu setup (brazil tz, db, socketio, etc.)
def _json_safe(o):
    if isinstance(o, Decimal):
        # envie como string para manter precisão (ou use float() se preferir número)
        return f"{o:.2f}"
    if isinstance(o, dict):
        return {k: _json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_safe(v) for v in o]
    return o
def _to_int(x, default=0):
    try:
        if x is None or x == '':
            return default
        return int(x)
    except (ValueError, TypeError):
        try:
            return int(float(str(x).replace(',', '.')))
        except Exception:
            return default

def _to_decimal(x, default=Decimal('0.00')):
    if x is None or x == '':
        return default
    try:
        return Decimal(str(x).replace(',', '.'))
    except (InvalidOperation, ValueError, TypeError):
        return default

def _ajusta_estoque(item_nome, delta_estoque, carrinho):
    """
    Aplica delta no estoque:
      delta_estoque > 0  => aumenta estoque
      delta_estoque < 0  => diminui estoque
    """
    if not item_nome:
        return

    # Lê quantidade atual (se houver)
    row = db.execute('SELECT quantidade FROM estoque WHERE item = ? AND carrinho = ?', item_nome, carrinho)
    if row:
        atual = _to_int(row[0]['quantidade'], 0)
        novo = max(0, atual + _to_int(delta_estoque, 0))  # evita negativo
        db.execute('UPDATE estoque SET quantidade = ? WHERE item = ? AND carrinho = ?', novo, item_nome, carrinho)
    else:
        # Se não existe o item no estoque e delta for positivo, cria; se negativo, cria 0.
        qtd = max(0, _to_int(delta_estoque, 0))
        db.execute('INSERT INTO estoque (item, quantidade, carrinho) VALUES (?, ?, ?)', item_nome, qtd, carrinho)


#helpers atualizar pedido
def _to_int(v, default=0):
    try:
        if v is None or v == '':
            return default
        return int(float(str(v).replace(',', '.')))
    except Exception:
        return default

def _to_decimal(v, default=0.0):
    try:
        if v is None or v == '':
            return default
        return float(str(v).replace(',', '.'))
    except Exception:
        return default

def _normalize_horario(h):
    if not h:
        return None
    s = str(h).strip()
    if re.fullmatch(r'\d{1,2}:\d{2}', s):
        hh, mm = s.split(':', 1)
        try:
            hh = max(0, min(23, int(hh)))
            mm = max(0, min(59, int(mm)))
            return f"{hh:02d}:{mm:02d}"
        except Exception:
            return None
    return None

# --------- NOVO: limpeza profunda de opcoes ---------
_KEY_FIXES = {
    'max_selected?': 'max_selected',
    'obrigatorio?':  'obrigatorio',
    'valor_extra?':  'valor_extra',
    # pode expandir aqui se surgirem outras
}

def _coerce_value_for_key(k, v):
    """Força tipos esperados para algumas chaves conhecidas."""
    base = k.rstrip('?')
    if base == 'max_selected':
        return _to_int(v, 0)
    if base == 'obrigatorio':
        # aceita "true"/"false", 1/0, "1"/"0"
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        return s in ('1', 'true', 'on', 'yes', 'y', 'sim')
    if base == 'valor_extra':
        return _to_decimal(v, 0.0)
    return v

def _deep_sanitize_opcoes(obj):
    """Remove '?' de chaves, força tipos, percorre recursivamente dict/list."""
    if isinstance(obj, dict):
        new_d = {}
        for k, v in obj.items():
            # renomeia chaves que terminam com '?'
            k2 = _KEY_FIXES.get(k, k.rstrip('?'))
            # recursão no valor
            v2 = _deep_sanitize_opcoes(v)
            # força tipos para chaves conhecidas
            v2 = _coerce_value_for_key(k2, v2)
            new_d[k2] = v2
        return new_d
    if isinstance(obj, list):
        return [_deep_sanitize_opcoes(x) for x in obj]
    # strings “normais”: apenas retorna (não removo '?' de conteúdo textual do usuário)
    return obj

def _normalize_opcoes(val):
    """
    Garante que 'opcoes' seja uma STRING JSON sem '?' “solto” e com chaves corretas.
    - Se for dict/list: limpa recursivamente, força tipos, dumps
    - Se for string: tenta limpar '?' problemáticos e validar
    - Fallback: "[]"
    """
    if val is None:
        return "[]"

    # Já objeto/array
    if isinstance(val, (list, dict)):
        try:
            clean = _deep_sanitize_opcoes(val)
            s = json.dumps(clean, ensure_ascii=False, separators=(',', ':'))
            # safety net final: remove qualquer '?' perdido
            if '?' in s:
                s = s.replace('?', '')
            return s
        except Exception:
            return "[]"

    # String -> limpar marcadores '?' que surgem do editor
    s = str(val).strip()
    # remoções dirigidas (quando o ? está grudado ao nome da chave)
    s = re.sub(r'("max_selected")\s*\?', r'\1', s)
    s = re.sub(r'("obrigatorio")\s*\?',  r'\1', s)
    s = re.sub(r'("valor_extra")\s*\?',  r'\1', s)
    # safety net: tira qualquer '?' remanescente
    s = s.replace('?', '')

    try:
        obj = json.loads(s)
        clean = _deep_sanitize_opcoes(obj)
        out = json.dumps(clean, ensure_ascii=False, separators=(',', ':'))
        if '?' in out:
            out = out.replace('?', '')
        return out
    except Exception:
        return "[]"
def update_pedidos_opcoes_sqlite(params):
    with closing(sqlite3.connect(DATABASE_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        with conn:
            conn.execute(
                """
                UPDATE pedidos
                   SET comanda = :comanda,
                       pedido = :pedido,
                       quantidade = :quantidade,
                       quantidade_paga = :quantidade_paga,
                       preco_unitario = :preco_unitario,
                       preco = :preco,
                       extra = :extra,
                       opcoes = :opcoes,
                       horario_para_entrega = :horario,
                       carrinho = :carrinho
                 WHERE id = :id AND dia = :dia
                """,
                params
            )
def insertAlteracoesTableSql(tabela, alteracao, tipo, tela, usuario, carrinho):
    #!!
    hoje = datetime.now(brazil).date()
    horario = datetime.now(brazil).strftime('%H:%M')

    # 🚫 não usar db.execute aqui
    with closing(sqlite3.connect(DATABASE_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        with conn:
            conn.execute(
                """
                INSERT INTO alteracoes (tabela,alteracao,tipo,usuario,tela,dia,horario, carrinho)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (tabela, alteracao, tipo, usuario, tela, hoje, horario,carrinho)
            )

@socketio.on('atualizar_pedidos')
def handle_atualizar_pedidos(data):
    dia = datetime.now(brazil).date()
    p = data.get('pedidoAlterado') or {}
    usuario = data.get('usuario')
    token_user = data.get('token')
    carrinho = data.get('carrinho')

    if not p or 'id' not in p:
        return emit('erro_pedidos', {'msg': 'Payload inválido para atualizar_pedidos'})

    atual_rows = db.execute(
        '''SELECT comanda, pedido, quantidade, quantidade_paga, preco_unitario, preco, extra, opcoes, horario_para_entrega
           FROM pedidos WHERE id = ? AND dia = ?''',
        p['id'], dia
    )
    if not atual_rows:
        return emit('erro_pedidos', {'msg': 'Pedido não encontrado para hoje'})

    atual = atual_rows[0]

    # --- normalizações seguras ---
    novo = {
        'comanda':              p.get('comanda', atual['comanda']),
        'pedido':               p.get('pedido',  atual['pedido']),
        'quantidade':           _to_int(p.get('quantidade', atual['quantidade'])),
        'quantidade_paga':      _to_int(p.get('quantidade_paga', atual.get('quantidade_paga'))),
        'preco_unitario':       _to_decimal(p.get('preco_unitario', atual.get('preco_unitario'))),
        'preco':                _to_decimal(p.get('preco', atual['preco'])),
        'extra':                p.get('extra',   atual['extra']),
        'opcoes':               _normalize_opcoes(p.get('opcoes',  atual.get('opcoes'))),
        'horario_para_entrega': _normalize_horario(p.get('horario_para_entrega', atual.get('horario_para_entrega'))),
    }

    # log de alterações (sem quebrar se algum valor for None)
    alteracoes = [f"{p.get('pedido', atual['pedido'])}, "]
    for k in ['comanda','pedido','quantidade','quantidade_paga','preco_unitario','preco','extra','opcoes','horario_para_entrega']:
        old_v = atual.get(k)
        new_v = novo.get(k)
        if str(old_v) != str(new_v):
            alteracoes.append(f"{k} de {old_v} para {new_v} ")

    old_item = atual['pedido']
    new_item = novo['pedido']


    try:
        db.execute('BEGIN')

        # normalizações finais
        opcoes_str  = _normalize_opcoes(novo['opcoes'])
        horario_str = _normalize_horario(novo['horario_para_entrega'])
        dia_str     = dia.isoformat()

        params = {
        "comanda": novo['comanda'],
        "pedido": new_item,
        "quantidade": _to_int(novo['quantidade']),
        "quantidade_paga": _to_int(novo['quantidade_paga']),
        "preco_unitario": str(_to_decimal(novo['preco_unitario'])),
        "preco": str(_to_decimal(novo['preco'])),
        "extra": novo['extra'],
        "opcoes": opcoes_str,
        "horario": horario_str,
        "id": p['id'],
        "dia": dia_str,
        "carrinho": carrinho,
        }

                                

        update_pedidos_opcoes_sqlite(params)


        if new_item != old_item:
            _ajusta_estoque(old_item, +_to_int(atual['quantidade']), carrinho)
            _ajusta_estoque(new_item, -_to_int(novo['quantidade']), carrinho)
        else:
            delta_estoque = _to_int(atual['quantidade']) - _to_int(novo['quantidade'])
            if delta_estoque != 0:
                _ajusta_estoque(new_item, delta_estoque, carrinho)

        db.execute('COMMIT')
    except Exception as e:
        db.execute('ROLLBACK')
        print('Erro ao atualizar pedido:', e)
        return emit('erro_pedidos', {'msg': 'Falha ao atualizar pedido', 'erro': str(e)})



    alter_str = ''.join(alteracoes) if alteracoes else f"{novo['pedido']} (sem alterações detectadas)"
    insertAlteracoesTableSql('pedidos', alter_str, 'editou', 'Tela Pedidos', usuario, carrinho)
    enviar_notificacao_expo('ADM', 'Pedido Editado', f'{usuario} Editou {alter_str}', token_user, usuario, carrinho)

    getPedidos({'emitir': True, 'carrinho': carrinho})
    handle_get_cardapio(str(novo['comanda']), carrinho)


@socketio.on('desfazer_pagamento')
def desfazer_pagamento(data):
    dia = datetime.now(brazil).date()
    comanda = data.get('comanda')
    carrinho = data.get('carrinho')
    ids_dict = db.execute('''
        SELECT ids FROM pagamentos
        WHERE id = (
            SELECT id FROM pagamentos
            WHERE comanda = ? AND ordem = ? AND dia = ? AND carrinho = ?
            ORDER BY id DESC
            LIMIT 1
        )
    ''', comanda, 1, dia, carrinho)
    print('ids_dict', ids_dict)
    if ids_dict:
        ids = ids_dict[0]['ids']
        print('ids', ids)
        if ids:
            print('tem ids')
            ids_list = json.loads(ids)
            print('ids_list', ids_list)
            for row in ids_list:
                db.execute('UPDATE pedidos SET quantidade_paga = quantidade_paga - ?, preco = preco_unitario *NULLIF((quantidade-(quantidade_paga - ?)),0) WHERE id = ? AND dia = ?',row['quantidade'],row['quantidade'],row['id'],dia)
    db.execute('''
        DELETE FROM pagamentos
        WHERE id = (
            SELECT id FROM pagamentos
            WHERE comanda = ? AND ordem = ? AND dia = ? AND carrinho = ?
            ORDER BY id DESC
            LIMIT 1
        )
    ''', comanda, 1, dia, carrinho)

    db.execute('UPDATE pagamentos SET ordem = ordem - ? WHERE comanda = ? AND dia = ? AND ordem != ? AND carrinho = ?',1,comanda,dia,0,carrinho)
    db.execute('UPDATE pedidos SET ordem = ordem - ? WHERE comanda = ? AND dia = ? AND ordem != ? AND carrinho = ?',1,comanda,dia,0,carrinho)
    faturamento({'emitir': True, 'carrinho': carrinho})
    handle_get_cardapio(comanda, carrinho)



@socketio.on('delete_comanda')
def handle_delete_comanda(data):
    try:
        #!!
        dia = datetime.now(brazil).date()
        carrinho = data.get('carrinho')  # valor padrão
        _register_carrinho_room(carrinho)
        
        # Identificar a comanda recebida
        comanda = data.get('fcomanda')
        valor_pago = float(data.get('valor_pago'))
        caixinha = data.get('caixinha',0)
        dez_por_cento = data.get('dez_por_cento',0)
        if not caixinha:
            caixinha=0
        else:
            caixinha=float(caixinha)
        if not dez_por_cento:
            dez_por_cento=0
        else:
            dez_por_cento=float(dez_por_cento)

        forma_de_pagamento = data.get('forma_de_pagamento')
        print('forma de pagamento', forma_de_pagamento)
        dia = datetime.now(brazil).date()
        print(f'Data de hoje: {dia}')
        db.execute('INSERT INTO pagamentos (valor,valor_total,caixinha,dez_por_cento,tipo,ordem,dia,forma_de_pagamento,comanda,horario,carrinho) VALUES (?,?,?,?,?,?,?,?,?,?,?)',valor_pago,valor_pago+caixinha+dez_por_cento,caixinha,dez_por_cento,'normal',0,dia,forma_de_pagamento,comanda,datetime.now(brazil).strftime('%H:%M'),carrinho)
            
           

        db.execute('UPDATE pedidos SET ordem = ordem +? WHERE comanda = ? AND dia = ? AND carrinho = ?',1,comanda, dia, carrinho)
        db.execute('UPDATE pagamentos SET ordem = ordem + ? WHERE comanda = ? AND dia = ? AND carrinho = ?',1,comanda,dia,carrinho)
        faturamento({'emitir': True, 'carrinho': carrinho})
        getComandas({'emitir': True, 'carrinho': carrinho})
        getPedidos({'emitir': True, 'carrinho': carrinho})
        handle_get_cardapio(comanda, carrinho)
        emit_for_carrinho('comanda_deleted', {'fcomanda': comanda}, broadcast=True, carrinho=carrinho)

    except Exception as e:
        print("Erro ao apagar comanda:", e)
        emit('error', {'message': str(e)})


@socketio.on('pagar_parcial')
def pagar_parcial(data):
    comanda = data.get('fcomanda')
    carrinho = data.get('carrinho')
    print(f'pagar parcial comanda : {comanda}')
    valor_pago = float(data.get('valor_pago'))
    forma_de_pagamento = data.get('forma_de_pagamento')
    caixinha = data.get('caixinha',0)
    dez_por_cento = data.get('dez_por_cento',0)
    if not caixinha:
        caixinha=0
    else:
        caixinha=float(caixinha)
    if not dez_por_cento:
        dez_por_cento=0
    else:
        dez_por_cento=float(dez_por_cento)
    
    dia = datetime.now(brazil).date()
    
    totalComandaDict = db.execute('SELECT SUM(preco) AS total FROM pedidos WHERE comanda = ? AND ordem = ? AND dia = ? AND carrinho = ?', comanda, 0,dia, carrinho)
    valorTotalDict = db.execute('SELECT SUM(valor_total) as total FROM pagamentos WHERE dia = ? AND comanda = ? AND ordem = ? AND tipo = ? AND carrinho = ?',dia,comanda,0,'normal',carrinho)
    
    if valorTotalDict and valorTotalDict[0]['total']:
        valorTotal = valorTotalDict[0]['total']
    else:
        valorTotal = 0

    db.execute('INSERT INTO pagamentos (valor,valor_total,caixinha,dez_por_cento,tipo,ordem,dia,forma_de_pagamento,comanda,horario,carrinho) VALUES (?,?,?,?,?,?,?,?,?,?,?)',valor_pago,valor_pago+caixinha+dez_por_cento,caixinha,dez_por_cento,'normal',0,dia,forma_de_pagamento,comanda,datetime.now(brazil).strftime('%H:%M'),carrinho)
    faturamento({'emitir': True, 'carrinho': carrinho})
    if valorTotal+valor_pago>=totalComandaDict[0]['total']:
        db.execute('UPDATE pagamentos SET ordem = ordem + ? WHERE dia = ? AND comanda = ? AND carrinho = ?',1,dia,comanda,carrinho)
        handle_delete_comanda({'fcomanda':comanda, 'carrinho':carrinho})
    
    handle_get_cardapio(comanda, carrinho)


@socketio.on('get_ingredientes')
def get_ingredientes(data):
    carrinho = data.get('carrinho')
    item = data.get('ingrediente')
    ingredientes = db.execute(
        'SELECT instrucoes FROM cardapio WHERE item = ? AND carrinho = ?', item, carrinho)

    if ingredientes:
        ingrediente = ingredientes[0]['instrucoes']
        data = []
        letras = ''
        key = ''
        dado = ''
        for j in ingrediente:
            if j == ':':
                key = letras
                letras = ''
            elif j == '-':
                dado = letras
                letras = ''
                data.append({'key': key, 'dado': dado})
            else:
                letras += j
        print(data)
        emit('ingrediente', {
             'data': data})



@socketio.on('inserir_preparo')
def inserir_preparo(data):
    id = data.get('id')
    carrinho = data.get('carrinho')
    estado = data.get('estado')
    horario = datetime.now(pytz.timezone(
        "America/Sao_Paulo")).strftime('%H:%M')
    print(f'id: {id}, estado: {estado}, horario: {horario}')

    if estado == 'Pronto':
        print('entrou no pronto')
        db.execute('UPDATE pedidos SET fim = ? WHERE id = ? AND carrinho = ?', horario, id)
    elif estado == 'Em Preparo':
        print('entrou no em preparo')
        db.execute('UPDATE pedidos SET comecar = ? WHERE id = ?', horario, id)
    
    db.execute('UPDATE pedidos SET estado = ? WHERE id = ?',estado,
               id)
    print('depois do update')
    getPedidos({'emitir':True, 'carrinho': carrinho})
    getPedidosCC({'emitir':True, 'carrinho': carrinho})


@socketio.on('atualizar_estoque_geral')
def atualizar_estoque_geral(data):
    carrinho = data.get('carrinho')
    usuario = data.get('username')
    itensAlterados = data.get('itensAlterados')
    token_user = data.get('token')
    for i in itensAlterados:
        item = i['item']
        quantidade = i['quantidade']
        quantidadeAnterior=db.execute("SELECT quantidade FROM estoque_geral WHERE item =? AND carrinho = ?",item, carrinho)
        if quantidadeAnterior: anterior=quantidadeAnterior[0]['quantidade']
        db.execute('UPDATE estoque_geral SET quantidade = ? WHERE item = ? AND carrinho = ?',
                   float(quantidade), item, carrinho)
        insertAlteracoesTable('estoque geral',f'{i["item"]} de {int(anterior)} para {i["quantidade"]}','editou','Editar Estoque Geral',usuario, carrinho)
        enviar_notificacao_expo('ADM','Estoque Geral Atualizado',f'{usuario} Editou {i["item"]} de {int(anterior)} para {i["quantidade"]}',token_user, carrinho)
    getEstoqueGeral({'emitir':True, 'carrinho': carrinho})


@socketio.on('atualizar_estoque')
def atualizar_estoque(data):
    carrinho = data.get('carrinho')
    usuario = data.get('username')
    itensAlterados = data.get('itensAlterados')
    token_user = data.get('token')
    for i in itensAlterados:
        item = i['item']
        anterior=''
        quantidade = i['quantidade']
        quantidadeAnterior=db.execute("SELECT quantidade FROM estoque WHERE item=? AND carrinho = ?",item, carrinho)
        if quantidadeAnterior:anterior=quantidadeAnterior[0]['quantidade']
        db.execute('UPDATE estoque SET quantidade = ? WHERE item = ? AND carrinho = ?',
                   float(quantidade), item, carrinho)
        insertAlteracoesTable('estoque carrinho',f'{i["item"]} de {int(anterior)} para {i["quantidade"]}','editou','Editar Estoque',usuario, carrinho)
        enviar_notificacao_expo('ADM','Estoque Atualizado',f'{usuario} Editou {i["item"]} de {int(anterior)} para {i["quantidade"]}',token_user, carrinho)
        
        
    getEstoque({'emitir':True, 'carrinho': carrinho})


@socketio.on('atualizar_comanda')
def atualizar__comanda(data):
    print(data)
    itensAlterados = data.get('itensAlterados')
    print(itensAlterados)
    comanda = data.get('comanda')
    usuario = data.get('username')
    carrinho = data.get('carrinho')
    dia = datetime.now(brazil).date()
    token_user = data.get('token')
    for i in itensAlterados:

        item = i['pedido']
        antes_dic = db.execute('SELECT quantidade FROM pedidos WHERE pedido = ? AND ordem = ? AND dia = ? AND carrinho = ?',item,0,dia, carrinho)
        antes = antes_dic[0]['quantidade']

        quantidade = float(i['quantidade'])
        print(f'quantidade = {quantidade}')
        if quantidade == 0:
            quantidade_total_dic = db.execute('''SELECT quantidade,id FROM pedidos
            WHERE pedido = ? AND comanda = ? AND ordem = ? AND dia = ? AND carrinho = ?;
                ''', item, comanda,dia, 0, carrinho)
            quantidade_total = 0
            for j in quantidade_total_dic:
                quantidade_total += float(j['quantidade'])
            verifEstoq = db.execute(
                'SELECT * FROM estoque WHERE item = ? AND carrinho = ?', item, carrinho)
            if verifEstoq:
                db.execute(
                    'UPDATE estoque SET quantidade = quantidade + ? WHERE item = ? AND carrinho = ?', quantidade_total, item, carrinho)
                
                insertAlteracoesTable('Pedido Editado',f'{i["pedido"]} de {antes} para {i["quantidade"]}','editou','Editar Comanda',usuario, carrinho)
                enviar_notificacao_expo('ADM','Comanda Editada',f'{usuario} Editou {i["pedido"]} de {antes} para {i["quantidade"]}',token_user, carrinho)


            db.execute(
                'DELETE FROM pedidos WHERE pedido = ? AND comanda = ? AND ordem = ? AND dia = ? AND carrinho = ?', item, comanda, 0,dia,carrinho)
        else:
            print(i['preco'])
            preco = float(i['preco'])/quantidade
            print(f'quantidade {quantidade}')
            print(f'preco {preco}')
            quantidade_total_dic = db.execute('''SELECT quantidade,id FROM pedidos
                WHERE pedido = ? AND comanda = ? AND ordem = ? AND preco / quantidade = ? AND dia = ? AND carrinho = ?;
                    ''', item, comanda, 0, preco,dia, carrinho)
            quantidade_total = 0
            for j in quantidade_total_dic:
                quantidade_total += float(j['quantidade'])
            quantidade_atualizada = (quantidade_total - quantidade)*-1
            print(f'quantidade atualizada acima {quantidade_atualizada}')
            preco_atualizado = preco*quantidade_atualizada

            if quantidade_atualizada < 0:
                quantidade_atualizada *= -1
                ids = db.execute(
                    'SELECT id,quantidade FROM pedidos WHERE pedido = ? AND comanda = ? AND ordem = ? AND dia = ? AND carrinho = ?', item, comanda, 0,dia, carrinho)
                verifEstoq = db.execute(
                    'SELECT * FROM estoque WHERE item = ? AND carrinho = ?', item, carrinho)
                if verifEstoq:
                    db.execute(
                        'UPDATE estoque SET quantidade = quantidade + ? WHERE item = ? AND carrinho = ?', quantidade_atualizada, item, carrinho)
                insertAlteracoesTable('Pedido Editado',f'{i["pedido"]} de {antes} para {i["quantidade"]} na comanda:{comanda} ','editou','Editar Comanda',usuario, carrinho)
                enviar_notificacao_expo('ADM','Comanda Editada',f'{usuario} Editou {i["pedido"]} de {antes} para {i["quantidade"]} na comanda:{comanda}',token_user, carrinho)

                for k in ids:
                    if quantidade_atualizada > 0:
                        print(f'quantidade atualizada {quantidade_atualizada}')
                        print(f'k["quantidade"] {k["quantidade"]}')
                        if float(k['quantidade']) <= quantidade_atualizada:
                            db.execute(
                                'DELETE FROM pedidos WHERE id = ? AND dia = ?', k['id'],dia)
                            quantidade_atualizada -= float(k['quantidade'])
                        else:
                            db.execute(
                                'UPDATE pedidos SET  preco = preco/quantidade * (quantidade - ?),quantidade = quantidade - ? WHERE id = ? AND dia = ?', quantidade_atualizada, quantidade_atualizada, k['id'],dia)
                            quantidade_atualizada -= float(k['quantidade'])

            else:
                print(quantidade_total_dic)

                db.execute('UPDATE pedidos SET quantidade = quantidade + ?,preco = preco + ? WHERE pedido = ? AND comanda = ? AND ordem = ? AND id = ? AND dia = ?',
                           quantidade_atualizada, preco_atualizado, item, comanda, 0, quantidade_total_dic[0]['id'],dia)
                verifEstoq = db.execute(
                    'SELECT * FROM estoque WHERE item = ? AND carrinho = ?', item, carrinho)
                if verifEstoq:
                    db.execute(
                        'UPDATE estoque SET quantidade = quantidade - ? WHERE item = ? AND carrinho = ?', quantidade_atualizada, item, carrinho)
                insertAlteracoesTable('Pedido Editado',f'{i["pedido"]} de {antes} para {i["quantidade"]} na comanda:{comanda}','editou','Editar Comanda',usuario, carrinho)
                enviar_notificacao_expo('ADM','Comanda Editada',f'{usuario} Editou {i["pedido"]} de {antes} para {i["quantidade"]} na comanda:{comanda}',token_user, carrinho)
            db.execute('''
                            DELETE FROM pedidos
                            WHERE id IN (
                                SELECT id
                                FROM (
                                    SELECT id
                                    FROM pedidos
                                    WHERE comanda = ?
                                    AND ordem = 0
                                    AND dia = ?
                                    AND pedido != ?
                                    AND carrinho = ?
                                    GROUP BY pedido
                                    HAVING SUM(quantidade) = 0
                                ) subquery
                            );
                        ''', comanda,dia, 'Comanda Aberta', carrinho)
    
    getEstoque({'emitir':True, 'carrinho': carrinho})
    getPedidos({'emitir': True, 'carrinho': carrinho})
    getComandas({'emitir': True, 'carrinho': carrinho})
    handle_get_cardapio(comanda, carrinho)

@socketio.on('transferir_para_estoque_carrinho')
def transferir_para_estoque_carrinho(data):
    itensAlterados = data.get('itensAlterados')
    token = data.get('token')
    usuario = data.get('username')
    carrinho = data.get('carrinho')
    for i in itensAlterados:
        
        quantidade_antiga = db.execute('SELECT quantidade FROM estoque_geral WHERE item = ? AND carrinho = ?',i['item'], carrinho)
        existe_no_estoque = db.execute('SELECT quantidade FROM estoque WHERE item = ? AND carrinho = ?',i['item'], carrinho)
        if quantidade_antiga and existe_no_estoque:
            quantidade_antig = float(quantidade_antiga[0]['quantidade'])
            quantidade = float(i['quantidade'])
            db.execute('UPDATE estoque SET quantidade = quantidade + ? WHERE item = ? AND carrinho = ?',quantidade_antig-quantidade,i['item'], carrinho)
            getEstoque({'emitir':True, 'carrinho': carrinho})
            insertAlteracoesTable('Estoque Carrinho',f'{i["item"]} de {existe_no_estoque[0]["quantidade"]} para {quantidade_antig-quantidade}','editou','Transferir para Estoque Carrinho',usuario, carrinho)
            enviar_notificacao_expo('ADM','Estoque Carrinho Tranferir',f'{usuario} Editou {i["item"]} de {existe_no_estoque[0]["quantidade"]} para {quantidade_antig-quantidade}',token, carrinho)
    atualizar_estoque_geral(data)
            

@socketio.on('get_cardapio')
def handle_get_cardapio(data, carrinho_param=None):
    print('get_cardapio')
    try:
        dia = datetime.now(brazil).date()  # valor padrão
        
        if type(data) == str:
            print('if')
            fcomanda = data
            ordem = 0
            # Se carrinho_param foi passado, use ele
            if carrinho_param:
                carrinho = carrinho_param
        else:
            print('else')
            fcomanda = data.get('fcomanda')
            ordem = data.get('ordem')
            carrinho = data.get('carrinho')
            # Se carrinho_param foi passado, use ele (prioridade)
            if carrinho_param:
                carrinho = carrinho_param

        _register_carrinho_room(carrinho)

        if ordem == 0:
            valor_pago = db.execute('SELECT SUM(valor) AS total FROM pagamentos WHERE comanda = ? AND ordem = ? AND dia = ? AND tipo = ? AND carrinho = ?', fcomanda, ordem,dia,'normal',carrinho)
            print('valor_pago', valor_pago)
            preco_pago = 0
            if valor_pago and valor_pago[0]['total']:
                
                preco_pago = float(valor_pago[0]['total'])
            
            desconto = db.execute('SELECT SUM(valor) AS total FROM pagamentos WHERE comanda = ? AND ordem = ? AND dia = ? AND tipo = ? AND carrinho = ?', fcomanda, ordem,dia,'desconto',carrinho)
            if desconto and desconto[0]['total']:
                desconto_valor = float(desconto[0]['total'])
            else:
                desconto_valor = 0
            
            total_comanda = db.execute('SELECT SUM(preco_unitario*quantidade) AS total FROM pedidos WHERE comanda = ? AND ordem = ? AND dia = ? AND pedido != ? AND carrinho = ?', fcomanda, ordem,dia, 'Comanda Aberta', carrinho)
            preco_total = 0
            print('total_comanda', total_comanda)
            if total_comanda and total_comanda[0]['total']:
                
                print(total_comanda)
                preco_total = float(total_comanda[0]['total'])
            

                dados = db.execute('''
                    SELECT pedido,id,ordem,nome,extra,opcoes, SUM(quantidade) AS quantidade, SUM(quantidade_paga) as quantidade_paga, SUM(preco) AS preco
                    FROM pedidos WHERE comanda =? AND ordem = ? AND dia = ? AND carrinho = ? GROUP BY pedido, preco_unitario
                ''', fcomanda, ordem,dia, carrinho)
                nomes = db.execute(
                    'SELECT nome FROM pedidos WHERE comanda = ? AND ordem = ? AND nome != ? AND dia = ? AND pedido != ? AND carrinho = ? GROUP BY nome', fcomanda, ordem, '-1',dia, 'Comanda Aberta', carrinho)
                if not nomes or not nomes[0]['nome']:
                    nomes = []
                preco_a_pagar = preco_total-preco_pago-desconto_valor
                emit_for_carrinho('preco', {'preco_a_pagar': preco_a_pagar, 'preco_total': preco_total, 'preco_pago': preco_pago,
                               'dados': dados, 'comanda': fcomanda, 'nomes': nomes, 'desconto': desconto_valor}, broadcast=True, carrinho=carrinho)
            else:
                print('primeiro else')
                emit_for_carrinho('preco', {'preco_a_pagar': 0, 'preco_total': 0, 'preco_pago': 0, 'dados': [], 'nomes': [],
                               'comanda': fcomanda}, broadcast=True, carrinho=carrinho)
        else:
            print('segundo else')
            dados = db.execute('''
                    SELECT pedido,id,ordem,nome,extra,opcoes, SUM(quantidade) AS quantidade, SUM(quantidade_paga) as quantidade_paga, SUM(preco) AS preco
                    FROM pedidos WHERE comanda =? AND ordem = ? AND dia = ? AND carrinho = ? GROUP BY pedido, preco_unitario
                ''', fcomanda, ordem,dia, carrinho)
            emit_for_carrinho('preco', {'preco_a_pagar': 0, 'preco_total': 0, 'preco_pago': 0, 'dados': dados, 'nomes': '',
                           'comanda': fcomanda}, broadcast=True, carrinho=carrinho)


    except Exception as e:
        print("Erro ao calcular preço:", e)




@socketio.on('permitir')
def permitir(data):
    #!!
    id = data.get('id')
    carrinho = data.get('carrinho')
    # Corrigido para buscar 'numero', que está vindo do frontend
    numero = data.get('numero')
    db.execute('UPDATE usuarios SET liberado = ? WHERE id = ?',
               numero, id)  # Atualiza a coluna 'liberado'
    users({'emitir':True, 'carrinho': carrinho})



@socketio.on('Delete_user')
def delete_user(data):
    #!!
    id = data.get('id')
    carrinho = data.get('carrinho')
    db.execute('DELETE FROM usuarios WHERE id = ?',id)
    users({'emitir':True, 'carrinho': carrinho})

@socketio.on('cadastrar')
def cadastro(data):
    print('entrou')
    carrinho=data.get('carrinho')
    username = data.get('username')
    cargo = data.get('cargo')
    print(username)
    senha = data.get('senha')
    print(senha)
    db.execute('INSERT INTO usuarios (username,senha,cargo,liberado, carrinho) VALUES (?,?,?,?,?)',
               username, senha, cargo, '1',carrinho)
    print('sucesso'
          )
    users({'emitir':True, 'carrinho': carrinho})

def _bool_int(v):
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, (int, float)):
        return 1 if int(v) != 0 else 0
    s = str(v).strip().lower()
    return 1 if s in ("1", "true", "t", "yes", "y", "sim") else 0

def _slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "n-a"

def _parse_opcoes(obj):
    """Aceita string JSON ou lista já estruturada; retorna lista saneara no formato:
       [{nome, ids, max_selected:int, obrigatorio:0/1, options:[{nome, valor_extra:float, esgotado:0/1}]}]
    """
    if obj is None:
        return []
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except Exception:
            return []

    out = []
    if isinstance(obj, list):
        for g in obj:
            try:
                nome = (g.get("nome") or g.get("titulo") or "").strip()
                if not nome:
                    continue
                ids = str(g.get("ids") or "")
                max_selected = int(g.get("max_selected") or 1)
                if max_selected < 1:
                    max_selected = 1
                obrigatorio = _bool_int(g.get("obrigatorio"))

                opts_in = g.get("options") or []
                opts_out = []
                for o in opts_in:
                    onome = str(o.get("nome") or "").strip()
                    if not onome:
                        continue
                    extra = float(o.get("valor_extra") or 0.0)
                    esgotado = _bool_int(o.get("esgotado"))
                    opts_out.append({
                        "nome": onome,
                        "valor_extra": extra,
                        "esgotado": esgotado,
                    })
                if opts_out:
                    out.append({
                        "nome": nome,
                        "ids": ids,
                        "max_selected": max_selected,
                        "obrigatorio": obrigatorio,
                        "options": opts_out,
                    })
            except Exception:
                # ignora grupo problemático
                pass
    return out

def _sync_opcoes_rows(id_cardapio: int, item_nome: str, grupos: list, carrinho):
    """Limpa e re-insere as linhas em `opcoes` para este cardápio."""
    db.execute("DELETE FROM opcoes WHERE id_cardapio = ? AND carrinho = ?", id_cardapio, carrinho)
    now = datetime.now().isoformat(timespec="seconds")
    for g in grupos:
        gname = g["nome"]
        gslug = _slugify(g.get("grupo_slug") or gname)
        for o in g.get("options", []):
            oname = o["nome"]
            oslug = _slugify(o.get("opcao_slug") or oname)
            extra = float(o.get("valor_extra") or 0.0)
            esgotado = _bool_int(o.get("esgotado"))
            db.execute(
                """
                INSERT INTO opcoes
                  (id_cardapio, item, nome_grupo, opcao, valor_extra, esgotado_bool, grupo_slug, opcao_slug, updated_at, carrinho)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                id_cardapio, item_nome, gname, oname, extra, esgotado, gslug, oslug, now, carrinho
            )


@socketio.on('adicionarCardapio')
def adicionarCardapio(data):
    item = (data.get('item') or '').strip()
    preco = data.get('preco')
    categoria = data.get('categoria')
    usuario = data.get('username')
    token_user = data.get('token')
    carrinho = data.get('carrinho')

    if not item or preco is None or not categoria:
        emit('Erro', {'erro': 'Alguma categoria faltando'})
        return

    if categoria == 'Bebida':
        categoria_id = 2
    elif categoria == 'Porção':
        categoria_id = 3
    else:
        categoria_id = 1

    # opcoes saneadas
    grupos = _parse_opcoes(data.get('opcoes'))
    opcoes_json = json.dumps(grupos, ensure_ascii=False)

    # INSERT cardapio + pegar id
    db.execute(
        'INSERT INTO cardapio (item, categoria_id, preco, opcoes, carrinho) VALUES (?,?,?,?,?)',
        item, categoria_id, float(preco), opcoes_json, carrinho
    )
    # SQLite: id da última inserção na mesma conexão
    new_id = db.execute("SELECT last_insert_rowid() AS id")[0]["id"]

    # sincroniza linhas da tabela `opcoes`
    _sync_opcoes_rows(new_id, item, grupos, carrinho)

    alteracoes = f'item: {item} preco: {preco} categoria: {categoria} (com opcoes)'
    insertAlteracoesTable('Cardapio', alteracoes, 'Adicionou', 'Tela Cardapio', usuario, carrinho)
    enviar_notificacao_expo('ADM', 'Item Adicionado Cardapio', f"{usuario} Adicionou {alteracoes}", token_user, carrinho)
    getCardapio({'emitir':True, 'carrinho': carrinho})






@socketio.on('editarCardapio')
def editarCardapio(data):
    item = (data.get('item') or '').strip()
    preco = data.get('preco')
    categoria = data.get('categoria')
    novoNome = (data.get('novoNome') or '').strip()
    raw_opcoes = data.get('opcoes')
    carrinho = data.get('carrinho')

    usuario = data.get('username')
    token_user = data.get('token')

    if not (item and preco is not None and categoria):
        emit('Erro', {'erro': 'Dados insuficientes'})
        return

    if categoria == 'Restante':
        categoria_id = 1
    elif categoria == 'Porção':
        categoria_id = 3
    elif categoria == 'Bebida':
        categoria_id = 2
    else:
        categoria_id = 1

    # pega antigo para log
    dadoAntigo = db.execute('SELECT * FROM cardapio WHERE item = ? AND carrinho = ?', item, carrinho)
    dadoAntigo = dadoAntigo[0] if dadoAntigo else {}

    # se vier opcoes, saneia e serializa; senão mantém (não mexe no JSON nem na tabela opcoes)
    grupos = None
    opcoes_json = None
    if raw_opcoes is not None:
        grupos = _parse_opcoes(raw_opcoes)
        opcoes_json = json.dumps(grupos, ensure_ascii=False)

    # UPDATE principal
    if opcoes_json is not None and novoNome:
        db.execute(
            "UPDATE cardapio SET item = ?, preco = ?, categoria_id = ?, opcoes = ? WHERE item = ? AND carrinho = ?",
            novoNome, float(preco), categoria_id, opcoes_json, item, carrinho
        )
    elif opcoes_json is not None:
        db.execute(
            "UPDATE cardapio SET preco = ?, categoria_id = ?, opcoes = ? WHERE item = ? AND carrinho = ?",
            float(preco), categoria_id, opcoes_json, item, carrinho
        )
    elif novoNome:
        db.execute(
            "UPDATE cardapio SET item = ?, preco = ?, categoria_id = ? WHERE item = ? AND carrinho = ?",
            novoNome, float(preco), categoria_id, item, carrinho
        )
    else:
        db.execute(
            "UPDATE cardapio SET preco = ?, categoria_id = ? WHERE item = ? AND carrinho = ?",
            float(preco), categoria_id, item, carrinho
        )

    # chave atual para buscar id
    chaveBusca = novoNome if novoNome else item
    dadoAtualizado = db.execute('SELECT * FROM cardapio WHERE item = ?  AND carrinho = ? ORDER BY id DESC LIMIT 1', chaveBusca, carrinho)
    dadoAtualizado = dadoAtualizado[0] if dadoAtualizado else {}

    # sincroniza tabela `opcoes`
    if dadoAtualizado:
        id_cardapio = dadoAtualizado.get("id")
        if grupos is not None:
            _sync_opcoes_rows(id_cardapio, chaveBusca, grupos, carrinho)
        elif novoNome:
            # só renomeou item — reflita em `opcoes.item`
            db.execute("UPDATE opcoes SET item = ? WHERE id_cardapio = ? AND carrinho = ?", chaveBusca, id_cardapio, carrinho)

    # log diffs
    alteracoes = f'{item}, '
    dif = {k for k in (dadoAtualizado.keys() & dadoAntigo.keys())
           if dadoAtualizado[k] != dadoAntigo.get(k)}
    for key in dif:
        alteracoes += f'{key} de {dadoAntigo.get(key)} para {dadoAtualizado.get(key)}'

    insertAlteracoesTable('Cardapio', alteracoes, 'Editou', 'Tela Cardapio', usuario, carrinho)
    enviar_notificacao_expo('ADM', 'Cardapio editado', f"{usuario} Editou {alteracoes}", token_user, carrinho)
    getCardapio({'emitir':True, 'carrinho': carrinho})


  

@socketio.on('removerCardapio')
def removerCardapio(data):
    item=data.get('item')
    usuario = data.get('username')
    token_user = data.get('token')
    carrinho = data.get('carrinho')
    print("Removendo item:", item)
    db.execute("DELETE FROM cardapio WHERE item=? AND carrinho = ?",item, carrinho)

    insertAlteracoesTable('Cardapio',item,'Removeu','Tela Cardapio',usuario, carrinho)
    enviar_notificacao_expo('ADM','Item Removido Cardapio',f"{usuario} Removeu {item} do Cardapio",token_user, carrinho)
    getCardapio({'emitir':True, 'carrinho': carrinho})
    


@socketio.on('getItemCardapio')
def getItemCardapio(data):
    item = data.get('item')
    carrinho = data.get('carrinho')
    print(item) 
    opcoes = db.execute('SELECT opcoes FROM cardapio WHERE item = ? AND carrinho = ?', item, carrinho)
    if opcoes:
        palavra = ''
        selecionaveis = []
        dados = []
        if opcoes[0]['opcoes'] is None or opcoes[0]['opcoes'] == '':
            emit('respostaGetItemCardapio',{'opcoes':[{'titulo':'','conteudo':[]}]} , broadcast=False)
            return
        for i in opcoes[0]['opcoes']:
            if i == '(':
                nome_selecionavel = palavra
                print(nome_selecionavel)
                palavra = ''
            elif i == '-':
                selecionaveis.append(palavra)
                palavra = ''
            elif i == ')':
                selecionaveis.append(palavra)
                dados.append({'titulo':nome_selecionavel,'conteudo':selecionaveis})
                selecionaveis = []
                palavra = ''
            else:
                palavra += i

        print(dados)
        emit('respostaGetItemCardapio',{'opcoes':dados}, broadcast=False)

def insertAlteracoesTable(tabela,alteracao,tipo,tela,usuario, carrinho):
    hoje = datetime.now(brazil).date()
    horario = datetime.now(pytz.timezone(
        "America/Sao_Paulo")).strftime('%H:%M')
    print(tabela,alteracao,tipo,usuario)
    db.execute('INSERT INTO alteracoes (tabela,alteracao,tipo,usuario,tela,dia,horario, carrinho) VALUES (?,?,?,?,?,?,?,?)',tabela,alteracao,tipo,usuario,tela,hoje,horario, carrinho)
    getAlteracoes({'emitir':True, 'carrinho': carrinho})

@socketio.on('getAlteracoes')
def getAlteracoes(data):
    carrinho = data.get('carrinho')
    emitir = data.get('emitir')
    _register_carrinho_room(carrinho)
    print("Entrou GEtalteracoes")
    if type(emitir)!=bool:
        emiti=emitir.get('emitir')
        change=emitir.get('change')
        hoje = datetime.now(brazil).date() + timedelta(days=int(change))
        dia_mes = hoje.strftime('%d/%m')
    else:
        emiti = emitir
        hoje = datetime.now(brazil).date()
        dia_mes = hoje.strftime('%d/%m')

    data=db.execute("SELECT * FROM alteracoes WHERE dia = ? AND carrinho = ?",hoje, carrinho)
    emit_for_carrinho('respostaAlteracoes', {"alteracoes":data,"hoje":str(dia_mes)}, broadcast=emiti, carrinho=carrinho)

@socketio.on('faturamento_range')
def faturamento_range(data):
    print('Fsturamento rangeeeeeeeeeeeeeeee')
    # --------- Entrada / defaults ---------
    date_from = (data or {}).get('date_from') or (data or {}).get('start')
    date_to   = (data or {}).get('date_to')   or (data or {}).get('end')
    emitir    = bool((data or {}).get('emitir', False))
    carrinho  = (data or {}).get('carrinho')

    _register_carrinho_room(carrinho)

    if not date_from or not date_to:
        emit_for_carrinho('faturamento_enviar', {
            'dia': 'Período inválido',
            'faturamento': 0, 'faturamento_previsto': 0,
            'drink': 0, 'porcao': 0, 'restante': 0, 'pedidos': 0,
            'caixinha': 0, 'dezporcento': 0, 'desconto': 0,
            'pix': 0, 'debito': 0, 'credito': 0, 'dinheiro': 0
        }, broadcast=False, carrinho=carrinho)
        return

    # Garante formato AAAA-MM-DD e troca se vier invertido
    # (assume que 'dia' na sua tabela está em TEXT 'YYYY-MM-DD' ou DATE)
    try:
        df = datetime.strptime(date_from, '%Y-%m-%d').date()
        dt = datetime.strptime(date_to,   '%Y-%m-%d').date()
    except ValueError:
        emit_for_carrinho('faturamento_enviar', {
            'dia': 'Formato de data inválido (use YYYY-MM-DD)',
            'faturamento': 0, 'faturamento_previsto': 0,
            'drink': 0, 'porcao': 0, 'restante': 0, 'pedidos': 0,
            'caixinha': 0, 'dezporcento': 0, 'desconto': 0,
            'pix': 0, 'debito': 0, 'credito': 0, 'dinheiro': 0
        }, broadcast=False, carrinho=carrinho)
        return

    if df > dt:
        df, dt = dt, df  # swap
    date_from = df.strftime('%Y-%m-%d')
    date_to   = dt.strftime('%Y-%m-%d')

    # --------- Agregações em PAGAMENTOS ---------
    # Por forma de pagamento
    metodosDict = db.execute("""
        SELECT forma_de_pagamento, SUM(valor) AS valor_total
        FROM pagamentos
        WHERE dia BETWEEN ? AND ? AND carrinho = ?
        GROUP BY forma_de_pagamento
    """, date_from, date_to, carrinho)

    dinheiro = credito = debito = pix = 0
    for row in metodosDict:
        forma = (row.get("forma_de_pagamento") or "").lower()
        val = row.get("valor_total") or 0
        if forma == "dinheiro":
            dinheiro += val
        elif forma == "credito":
            credito += val
        elif forma == "debito":
            debito += val
        elif forma == "pix":
            pix += val

    # Por tipo (caixinha, 10%, desconto, etc.)
    caixinha = db.execute("SELECT COALESCE(SUM(caixinha),0) AS total_caixinha FROM pagamentos WHERE dia BETWEEN ? AND ? AND carrinho = ?", date_from, date_to, carrinho)
    caixinha = caixinha[0]['total_caixinha'] or 0
    dezporcento = db.execute("SELECT COALESCE(SUM(dez_por_cento),0) AS total_dezporcento FROM pagamentos WHERE dia BETWEEN ? AND ? AND carrinho = ?",date_from,date_to, carrinho)
    dezporcento = dezporcento[0]['total_dezporcento'] or 0
    desconto = db.execute("SELECT SUM(valor) AS total_desconto FROM pagamentos WHERE dia BETWEEN ? AND ? AND tipo = ? AND carrinho = ?",date_from,date_to ,'desconto', carrinho)
    desconto = desconto[0]['total_desconto'] or 0

    # Faturamento real = tudo que entrou - descontos
    total_recebimentos = db.execute("SELECT SUM(valor_total) AS total_recebimentos FROM pagamentos WHERE tipo = ? AND dia BETWEEN ? AND ? AND carrinho = ?", 'normal',date_from, date_to, carrinho)
    total_recebimentos = total_recebimentos[0]['total_recebimentos'] or 0
    # --------- Agregações em PEDIDOS ---------
    # Mantive sua lógica de categorias (1=restante, 2=drink, 3=porção)
    pedidosQuantDict = db.execute("""
        SELECT categoria,
               SUM(quantidade) AS quantidade_total,
               SUM(preco_unitario*NULLIF(quantidade,0))      AS preco_total
        FROM pedidos
        WHERE dia BETWEEN ? AND ?
          AND pedido != ? AND carrinho = ?
        GROUP BY categoria
        ORDER BY categoria ASC
    """, date_from, date_to, 'Comanda Aberta', carrinho)
    print('predidosQuantDict', pedidosQuantDict)
    drink = restante = porcao = 0
    faturamento_previsto = 0
    for row in pedidosQuantDict:
        cat = row.get('categoria')
        qtd = row.get('quantidade_total') or 0
        if cat == '1':
            restante = qtd
        elif cat == '2':
            drink = qtd
        elif cat == '3':
            porcao = qtd
        faturamento_previsto += (row.get('preco_total') or 0)

    pedidos = (drink or 0) + (restante or 0) + (porcao or 0)

    # --------- Rótulo do período (mostrado no front em "Dia base") ---------
    periodo_fmt = f"{df.strftime('%d/%m')} — {dt.strftime('%d/%m')}"
    print(f'Faturamento de {periodo_fmt}: R$ {total_recebimentos:.2f} (previsto R$ {faturamento_previsto:.2f})')
    print(f'  Pedidos: {pedidos} (drink {drink}, porção {porcao}, restante {restante})')
    print(f'  Recebimentos: R$ {total_recebimentos:.2f} (pix R$ {pix:.2f}, débito R$ {debito:.2f}, crédito R$ {credito:.2f}, dinheiro R$ {dinheiro:.2f})')
    print(f'  Caixinha R$ {caixinha:.2f}, 10% R$ {dezporcento:.2f}, Descontos R$ {desconto:.2f})')
    print(f'  (emitir={emitir})')
    # ------------------------------------------
    # --------- Emite no MESMO formato do 'faturamento' ---------
    vendas_user = []
    vendas_user =db.execute('SELECT username, SUM(preco_unitario*NULLIF(quantidade,0)) AS valor_vendido, SUM(quantidade)  AS quant_vendida FROM pedidos WHERE dia BETWEEN ? AND ? AND pedido!= ? AND carrinho = ? GROUP BY username ORDER BY SUM(preco_unitario*NULLIF(quantidade,0)) DESC',date_from,date_to,'Comanda Aberta', carrinho)
    print('vendas_user', vendas_user)

    emit_for_carrinho('faturamento_enviar', {
        'dia': periodo_fmt,
        'faturamento': total_recebimentos,
        'faturamento_previsto': faturamento_previsto,
        'drink': drink,
        'porcao': porcao,
        "restante": restante,
        "pedidos": pedidos,
        "caixinha": caixinha,
        "dezporcento": dezporcento,
        "desconto": desconto,
        "pix": pix,
        "debito": debito,
        "credito": credito,
        "dinheiro": dinheiro,
        "vendas_user": vendas_user
    }, broadcast=emitir, carrinho=carrinho)


import re
from flask_socketio import emit  # ou use socketio.emit se preferir

@socketio.on('pagar_itens')
def pagar_itens(data):
    comanda = data.get('comanda')
    itens = data.get('itens')
    forma_de_pagamento = data.get('forma_de_pagamento')
    caixinha = data.get('caixinha', 0)
    caixinha = float(caixinha) if caixinha else 0
    aplicarDez = data.get('aplicarDez', False)
    carrinho = data.get('carrinho')
    ids_quant = []
    dia = datetime.now(brazil).date()
    preco = 0
    for row in itens:
        quantidade = float(row.get('quantidade'))
        item = row.get('pedido')
        ids = db.execute('SELECT id,quantidade,quantidade_paga,preco_unitario FROM pedidos WHERE pedido = ? AND comanda = ? AND ordem = ? AND dia = ? AND carrinho = ?',item,comanda,0,dia, carrinho)
        id_usar = None
        preco_dict = None
        for id in ids:
            if id['quantidade'] - id['quantidade_paga'] - quantidade >= 0:
                id_usar = id['id']
                preco_dict = id['preco_unitario']
                break
        if id_usar:
            db.execute('''
                    UPDATE pedidos
                    SET quantidade_paga = quantidade_paga + ?,
                        preco = preco_unitario * NULLIF(quantidade - (quantidade_paga + ?), 0)
                    WHERE comanda = ?
                    AND id = ?
                    AND ordem = ?
                    AND dia = ?
                    AND carrinho = ?
                ''', quantidade, quantidade, comanda, id_usar, 0, dia, carrinho)

            if preco_dict:
                preco += float(preco_dict)*quantidade
                ids_quant.append({'id': id_usar, 'quantidade': quantidade})

    if ids:
        dez_por_cento = 0 if not aplicarDez else (preco * 0.1)
        db.execute('INSERT INTO pagamentos (valor,valor_total,caixinha,dez_por_cento,tipo,ordem,dia,forma_de_pagamento,comanda,horario,ids,carrinho) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',preco,preco+caixinha+dez_por_cento,caixinha,dez_por_cento,'normal',0,dia,forma_de_pagamento,comanda,datetime.now(brazil).strftime('%H:%M'),json.dumps(ids_quant),carrinho)
        faturamento({'emitir': True, 'carrinho': carrinho})
    totalComandaDict = db.execute('SELECT SUM(preco_unitario*NULLIF(quantidade,0)) AS total FROM pedidos WHERE comanda = ? AND ordem = ? AND dia = ? AND carrinho = ?', comanda, 0,dia, carrinho)
    valorTotalDict = db.execute('SELECT SUM(valor) as total FROM pagamentos WHERE dia = ? AND comanda = ? AND ordem = ? AND tipo = ? AND carrinho = ?',dia,comanda,0,'normal',carrinho)
    if totalComandaDict and valorTotalDict:
        totalComanda = float(totalComandaDict[0]['total']) if totalComandaDict[0]['total'] else 0
        valorTotal = float(valorTotalDict[0]['total']) if valorTotalDict[0]['total'] else 0
        if totalComanda <= valorTotal:
            handle_delete_comanda({'fcomanda':comanda,'carrinho':carrinho})

    handle_get_cardapio(comanda, carrinho)


@socketio.on('buscar_menu_data')
def buscar_menu_data(payload):
    try:
        print('entrou buscar menu data')

        if isinstance(payload, dict):
            emitir_broadcast = payload.get('emitir', True)
            carrinho = payload.get('carrinho')
        else:
            emitir_broadcast = bool(payload)
            carrinho = None

        if carrinho:
            _register_carrinho_room(carrinho)

        data_geral = db.execute(
            '''
            SELECT id, item, preco,preco_base, categoria_id, image, opcoes, subcategoria
            FROM cardapio
            WHERE usable_on_qr = ?
            ORDER BY item ASC
            ''',
            1
        )


        data_geral_atualizado = []
        for row in data_geral:
            item_nome = (row.get('item') or '').strip()
            if not item_nome:
                continue

            cat_id = row.get('categoria_id')

            # Classificação
            if (cat_id in (1, 2)) and (item_nome not in ['amendoim', 'milho mostarda e mel', 'Pack de seda', 'cigarro', 'bic', 'dinheiro','castanha de caju']) and not item_nome.startswith('acai'):
                categoria_item = 'bebida'
            elif (cat_id == 3) or (item_nome in ['amendoim', 'milho mostarda e mel','castanha de caju']) or (item_nome.startswith('acai')):
                categoria_item = 'comida'
            else:
                categoria_item = 'outros'
            
            raw = row.get('opcoes')

            if not raw:
                options = []
            elif isinstance(raw, (list, dict)):
                # já é Python list/dict — ótimo
                options = raw
            else:
                try:
                    options = json.loads(raw)  # string JSON válida (aspas duplas)
                except Exception:
                    try:
                        # fallback se veio com aspas simples
                        options = json.loads(raw.replace("'", '"'))
                    except Exception as e:
                        print(f'Erro ao carregar opções para item {item_nome}:', e)
                        options = []

        
            
            data_geral_atualizado.append({
                'id': row['id'],
                'name': item_nome,
                'price': row.get('preco'),
                'original_price': row.get('preco_base'),
                'categoria': categoria_item,
                'subCategoria': row.get('subcategoria','outros'),
                'image': row.get('image') or None,
                'options': options,

            })

        emit_for_carrinho('menuData', data_geral_atualizado, broadcast=emitir_broadcast, carrinho=carrinho)

    except Exception as e:
        print('erro ao buscar_menu_data:', e)

@socketio.on('enviar_pedido_on_qr')
def enviar_pedido_on_qr(data,comanda,token,carrinho='NossoPoint'):
    print(f'enviar pedido on qr:\n {data}')
    print(f'comanda {comanda}')
    cliente = db.execute('SELECT numero FROM clientes WHERE token = ?',token)
    user_number = cliente[0].get('numero') if cliente else None
    if not user_number:
        user_number = 'Desconhecido'
    dia = datetime.now(brazil).date()
    for row in data:
        subcategoria = row.get('subcategoria')
        pedido_dict = db.execute('SELECT item,preco FROM cardapio WHERE id = ?',row.get('id'))
        if pedido_dict:
            pedido = pedido_dict[0].get('item')
            preco_unitario = float(pedido_dict[0].get('preco'))
        preco = float(row.get('price'))
        categoria = row.get('categoria')
        quantidade = row.get('quantity')
        options = row.get('selectedOptions',[])
        if not options:
            options = []
        obs = row.get('observations', None)
        extra = ''
        if categoria=='comida':
            if pedido not in ['amendoim', 'milho','castanha de caju']:
                categoria_id = 1
            elif pedido.startswith('acai'):
                categoria_id = 2
            else :
                categoria_id = 3
        else:
            if subcategoria in ['outros,cervejas']:
                categoria_id = 1
            else:
                categoria_id = 2

        agr = datetime.now()
        hora_min = agr.strftime("%H:%M")
        db.execute('''INSERT INTO pedidos (comanda,pedido,quantidade,extra,preco,preco_unitario,categoria,inicio,estado,nome,ordem,dia,username,opcoes,carrinho)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',comanda,pedido,quantidade,obs, preco,preco_unitario,categoria_id,hora_min,'A Fazer','-1',0,dia,f'Cliente:{user_number}',json.dumps(options),carrinho)



@socketio.on('savePromotion')
def savePromotion(data):
    print('entrou savePromotion')
    try:
        promotionData = data.get('promotionData')
        tipo = data.get('type')
        emitirBroadcast = data.get('emitirBroadcast', True)
        carrinho = data.get('carrinho')
        status = 'active' if promotionData['endDate'] > datetime.now(brazil).date().strftime('%Y-%m-%d') else 'expired'

        if tipo == 'create':
            db.execute('INSERT INTO promotions (name, products, type, value, endDate,status, carrinho) VALUES (?,?,?,?,?,?,?)',promotionData['name'],json.dumps(promotionData['products']),promotionData['type'],float(promotionData['value']),promotionData['endDate'],status, carrinho)
        elif tipo == 'update':
            db.execute('UPDATE promotions SET name = ?, products = ?, type = ?, value = ?, endDate = ?, status = ? WHERE id = ?',promotionData['name'],json.dumps(promotionData['products']),promotionData['type'],float(promotionData['value']),promotionData['endDate'],status,int(promotionData['id']))
        getPromotions({'emitir':True, 'carrinho': carrinho})
        # Aplicar promoção no cardápio
        if status == 'expired':
            for item in promotionData['products']:
                db.execute('UPDATE cardapio SET preco = preco_base WHERE id = ?', item['id'])
        else:
            if promotionData['type'] == 'percentage':
                value = 1.0 - (float(promotionData['value']) / 100)
                sinal = '*'
            else:
                value = float(promotionData['value'])
                sinal = '-'
            for item in promotionData['products']:
                db.execute(f'UPDATE cardapio SET preco = preco_base {sinal} ? WHERE id = ?', round(value, 2),item['id'])
        getCardapio({'emitir':True, 'carrinho': carrinho})


    except Exception as e:
        print('erro ao salvar promoção:', e)

@socketio.on('getPromotions')
def getPromotions(data):
    print('entrou getPromotions')
    emitirBroadcast = data.get('emitir')
    carrinho = data.get('carrinho')
    _register_carrinho_room(carrinho)
    dados = db.execute('SELECT * FROM promotions WHERE carrinho = ?', carrinho)
    emit_for_carrinho('promotionsData', dados, broadcast=emitirBroadcast, carrinho=carrinho)


@socketio.on('invocar_atendente')
def invocar_antendente(data):
    comanda = data.get('comanda')
    hoje = datetime.now()
    status = data.get('status')
    #horario = hoje.strftime('')
    
    #db.execute('INSERT into invocações_atendentes (comanda,horario,status,dia) VALUES (?,?,?,?)',)
        
    return {'status':'atendente_chamado'},200


    


SEU_CLIENT_ID = "c25a19b3-ca72-4ab3-b390-99e75a90e77d"
SEU_CLIENT_SECRET = "a3eg0gkdgddr6rs8zvlsd2yd4bweu1rj26s8h25w9p96c051y0jcishcz9tvhr1wvves5k5i7pf1x0ojos4dbvp2khct45vf0ug"
TOKEN_URL = "https://merchant-api.ifood.com.br/authentication/v1.0/oauth/token"

_token_cache = {"accessToken": None, "expiresAt": 0.0}
_cache_lock = threading.Lock()

def get_ifood_token():
    """
    Sempre retorna (access_token: str, expires_at: float).
    Renova 60s antes de expirar.
    """
    with _cache_lock:
        now = time.time()
        if _token_cache["accessToken"] and (_token_cache["expiresAt"] - now > 60):
            return _token_cache["accessToken"], _token_cache["expiresAt"]

        if not SEU_CLIENT_ID or not SEU_CLIENT_SECRET:
            raise RuntimeError("IFOOD_CLIENT_ID/IFOOD_CLIENT_SECRET não configurados nas variáveis de ambiente.")

        data = {
            "grantType": "client_credentials",
            "clientId": SEU_CLIENT_ID,
            "clientSecret": SEU_CLIENT_SECRET,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        r = requests.post(TOKEN_URL, data=data, headers=headers, timeout=20)
        r.raise_for_status()
        payload = r.json()

        access_token = payload.get("accessToken") or payload.get("access_token")
        expires_in = int(payload.get("expiresIn") or payload.get("expires_in") or 0)
        if not access_token or not expires_in:
            raise RuntimeError(f"Resposta de token inesperada: {payload}")

        expires_at = now + expires_in
        _token_cache["accessToken"] = access_token
        _token_cache["expiresAt"] = expires_at
        return access_token, expires_at

def fluxo_authentication():
    try:
        token, exp = get_ifood_token()
        return {"ok": True, "accessToken": token, "expiresAt": int(exp)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.route("/ifood/token", methods=["GET"])
def ifood_token_health():
    """Rota utilitária pra testar autenticação rapidamente."""
    res = fluxo_authentication()
    status = 200 if res.get("ok") else 500
    return jsonify(res), status

@app.route('/webhook_ifood', methods=['POST'])
def web_hooks_notifications():
    """
    Webhook do iFood:
    - SEMPRE retornar rapidamente 204 (ou 200) pra evitar reentregas infinitas.
    - Processamento pode ser assíncrono; aqui está direto pra simplificar.
    """
    try:
        print('ENTROUUUUUUU NO WEBHOOOOOK')
        data = request.get_json(silent=True) or {}
        print('data',data)
        # Campos comuns em webhooks do iFood:
        # code: "PLACED" | "CONFIRMED" | ...
        # orderId: "xxxx"
        event_code = data.get("fullCode") or data.get("event") or data.get("eventType")
        
        # Garante token válido
        access_token, _ = get_ifood_token()

        if event_code == "PLACED":
            order_id = data.get("orderId") or data.get("id")
            # Aqui você pode enfileirar para um worker; mantive direto para ficar pronto pra uso.
            pedido_detalhes(order_id, access_token)

        # Responde rápido SEMPRE
        return ("", 204)
    except Exception as e:
        print(f"[webhook_ifood] erro: {e}")
        # Mesmo com erro, devolva 204 pra não gerar loop de reentrega
        return ("", 204)

def pedido_detalhes(order_id: str, access_token: str):
    """Busca detalhes do pedido no endpoint do iFood e faz o parse básico."""
    if not access_token:
        access_token, _ = get_ifood_token()

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    # Detalhes do pedido
    url_order = f"https://merchant-api.ifood.com.br/order/v1.0/orders/{order_id}"
    resp = requests.get(url_order, headers=headers, timeout=20)
    resp.raise_for_status()
    order = resp.json()
    print("[iFood] detalhes do pedido:", order)
    print('/n'*8)
    data = extrair_pedido_ifood(order)
    print(f'Resposta:\n{resp}')
    order_id = data.get('pedido_id')
    produtos = data.get('produtos')
    nome_cliente = data.get('cliente_nome')
    endereco_dict = data.get('endereco')
    endereco = endereco_dict.get('rua')
    endereco+=f" {endereco_dict['numero']}"
    
    orderTiming = data.get('orderTiming')
    pedido_hora = data.get('pedido_hora')
    pedido_data = data.get('pedido_data')
    agendamento_hora = None
    if orderTiming == 'SCHEDULED':
        pedido_data = data.get('agendamento_data')
        agendamento_hora = data.get('agendamento_hora')
    
    for row in produtos:
        pedido = row['produto']
        quantidade = row['quantidade']
        preco = row['preco_total']
        extra = row.get('observacoes','')
        extra+='\n'
        for i in row.get('complementos'):
            extra+=f"{i['quantidade']} {i['nome']},"
        db.execute('INSERT INTO pedidos (pedido,quantidade,preco,categoria,inicio,estado,extra,nome,dia,orderTiming,endereco_entrega,order_id,remetente,horario_para_entrega) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                  pedido,quantidade,preco,3,pedido_hora,'A Fazer',extra,nome_cliente,pedido_data,orderTiming,endereco,order_id,'IFOOD',pedido_hora)
    
    # save_order_to_db(order_id, customer_name, customer_phone, parsed_items, sub_total, delivery_fee, order_total)
def parse_iso_br(dt_str: str | None) -> tuple[str | None, str | None]:
    """Converte datetime ISO do iFood para data e hora separadas (em São Paulo)."""
    if not dt_str:
        return None, None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00")).astimezone(brazil)
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")
    except Exception:
        return None, None

def extrair_pedido_ifood(order: dict) -> dict:
    """
    Retorna informações essenciais do pedido iFood:
    - nome do produto
    - complementos / especificações / observações
    - total com taxas (orderAmount)
    - valor sem taxas (subTotal)
    - endereço formatado
    - horário do pedido (data/hora)
    - se agendado, horário do agendamento (data/hora)
    """
    # Totais
    total_block = order.get("total") or {}
    valor_sem_taxas = total_block.get("subTotal")
    valor_com_taxas = total_block.get("orderAmount")
    print('Totais')

    # Endereço
    delivery = order.get("delivery") or {}
    addr = delivery.get("deliveryAddress") or {}
    endereco = {
        "rua": addr.get("streetName"),
        "numero": addr.get("streetNumber"),
        "bairro": addr.get("neighborhood"),
        "cidade": addr.get("city"),
        "estado": addr.get("state"),
        "cep": addr.get("postalCode"),
        "complemento": addr.get("complement"),
        "referencia": addr.get("reference"),
    }
    print('endereco')

    # Horários
    pedido_data, pedido_hora = parse_iso_br(order.get("createdAt"))
    agendamento_data, agendamento_hora = parse_iso_br(delivery.get("deliveryDateTime"))
    print('horarios')
    # Itens
    itens_extraidos = []
    for it in order.get("items", []):
        item_dict = {
            "produto": it.get("name"),
            "quantidade": it.get("quantity", 1),
            "preco_unit": it.get("unitPrice"),
            "preco_total": it.get("totalPrice"),
            "observacoes": it.get("observations"),
            "complementos": []
        }
        for opt in it.get("options", []):
            comp = {
                "nome": opt.get("name"),
                "grupo": opt.get("groupName"),
                "quantidade": opt.get("quantity", 1),
                "preco": opt.get("price"),
                "customizacoes": []
            }
            for cust in opt.get("customizations", []):
                comp["customizacoes"].append({
                    "nome": cust.get("name"),
                    "grupo": cust.get("groupName"),
                    "quantidade": cust.get("quantity", 1),
                    "preco": cust.get("price"),
                })
            item_dict["complementos"].append(comp)
        itens_extraidos.append(item_dict)
    print('itens')

    return {
        "pedido_id": order.get("id"),
        "cliente_nome": (order.get("customer") or {}).get("name"),
        "produtos": itens_extraidos,
        "valor_sem_taxas": valor_sem_taxas,
        "endereco": endereco,
        "pedido_data": pedido_data,
        "pedido_hora": pedido_hora,
        "orderTiming": order.get('orderTiming'),
        "agendamento_data": agendamento_data,
        "agendamento_hora": agendamento_hora,
    }

def _now_iso():
    return datetime.utcnow().isoformat(timespec="seconds")

_slug_non_alnum = re.compile(r"[^a-z0-9]+")
def slugify(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = _slug_non_alnum.sub("-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s

def _get_column_names(table: str):
    try:
        rows = db.execute(f"SELECT name FROM pragma_table_info('{table}')") or []
        return { (r.get("name") or "").strip() for r in rows }
    except Exception:
        return set()

def ensure_schema():
    """
    Garante colunas em `opcoes` e cria auditoria (sem DEFAULT(datetime('now'))).
    Backfill dos slugs a partir de nome_grupo/opcao.
    """
    colnames = _get_column_names("opcoes")

    # Estas três já existem no seu schema, mas mantemos defensivo:
    if "grupo_slug" not in colnames:
        db.execute("ALTER TABLE opcoes ADD COLUMN grupo_slug TEXT")
    if "opcao_slug" not in colnames:
        db.execute("ALTER TABLE opcoes ADD COLUMN opcao_slug TEXT")
    if "updated_at" not in colnames:
        db.execute("ALTER TABLE opcoes ADD COLUMN updated_at TEXT")

    # Auditoria
    db.execute("""
        CREATE TABLE IF NOT EXISTS opcoes_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT (datetime('now')),
            actor TEXT,
            where_json TEXT,
            set_json TEXT,
            dry_run INTEGER,
            matched INTEGER,
            updated INTEGER,
            items_json TEXT
        )
    """)

    # Backfill de slugs (a partir de nome_grupo/opcao)
    rows = db.execute("""
        SELECT rowid, nome_grupo, opcao, grupo_slug, opcao_slug
        FROM opcoes
    """) or []
    to_update = []
    for r in rows:
        gslug = (r.get("grupo_slug") or "").strip()
        oslug = (r.get("opcao_slug") or "").strip()
        if not gslug or not oslug:
            ng = (r.get("nome_grupo") or "").strip()
            op = (r.get("opcao") or "").strip()
            to_update.append({
                "rowid": r["rowid"],
                "g": slugify(ng),
                "o": slugify(op),
            })

    if to_update:
        db.execute("BEGIN")
        try:
            ts = _now_iso()
            for u in to_update:
                db.execute(
                    "UPDATE opcoes SET grupo_slug = :g, opcao_slug = :o, updated_at = :ts WHERE rowid = :rowid",
                    g=u["g"], o=u["o"], ts=ts, rowid=u["rowid"]
                )
            db.execute("COMMIT")
        except Exception:
            db.execute("ROLLBACK")
            raise

def _parse_bool(s):
    if s is None:
        return False
    return str(s).strip().lower() in ("1", "true", "yes", "y")

# ---------- /opcoes/aggregate ----------
@app.route("/opcoes/aggregate", methods=["GET"])
def opcoes_aggregate():
    """
    Params:
      q (opcional) - pesquisa em nome_grupo/opcao/item
      grupo_slug (opcional)
      somente_esgotados (0|1)
      somente_extra_positivo (0|1)
      limit (opcional, padrão 100)
    """
    ensure_schema()

    q = (request.args.get("q") or "").strip()
    grupo_slug = (request.args.get("grupo_slug") or "").strip().lower()
    somente_esgotados = _parse_bool(request.args.get("somente_esgotados"))
    somente_extra_positivo = _parse_bool(request.args.get("somente_extra_positivo"))
    carrinho = (request.args.get("carrinho") or "").strip()
    try:
        limit = int(request.args.get("limit") or 100)
    except Exception:
        limit = 100
    limit = max(1, min(limit, 500))

    # Filtros dinâmicos (base)
    wh = ["carrinho = :carrinho"]
    base_params = {"carrinho":carrinho}

    if grupo_slug:
        wh.append("grupo_slug = :gslug")
        base_params["gslug"] = grupo_slug

    if somente_esgotados:
        wh.append("(esgotado_bool = 1)")

    if somente_extra_positivo:
        wh.append("(COALESCE(valor_extra,0) > 0)")

    if q:
        wh.append("""
          (
            LOWER(COALESCE(nome_grupo,'')) LIKE :q
            OR LOWER(COALESCE(opcao,'')) LIKE :q
            OR LOWER(COALESCE(item,'')) LIKE :q
          )
        """)
        base_params["q"] = f"%{q.lower()}%"

    where_sql = " AND ".join(wh)

    # -------- Agregação (usa :lim) --------
    agg_sql = f"""
        SELECT
          MIN(nome_grupo)  AS grupo,
          grupo_slug       AS grupo_slug,
          MIN(opcao)       AS opcao,
          opcao_slug       AS opcao_slug,
          COUNT(*)         AS ocorrencias,
          SUM(CASE WHEN esgotado_bool = 1 THEN 1 ELSE 0 END) AS esgotados,
          ROUND(AVG(COALESCE(valor_extra,0)), 2) AS media_valor_extra
        FROM opcoes
        WHERE {where_sql}
        GROUP BY grupo_slug, opcao_slug
        ORDER BY MIN(nome_grupo), MIN(opcao)
        LIMIT :lim
    """
    paramsAgg = dict(base_params)
    paramsAgg["lim"] = limit

    clusters = db.execute(agg_sql, **paramsAgg) or []

    # -------- Amostra de itens (NÃO usa :lim) --------
    out = []
    for c in clusters:
        items_sql = f"""
            SELECT
              id_cardapio AS item_id,
              item        AS item_nome,
              valor_extra,
              esgotado_bool
            FROM opcoes
            WHERE {where_sql} AND grupo_slug = :gs AND opcao_slug = :os
            ORDER BY id_cardapio
            LIMIT 30
        """
        paramsItems = dict(base_params)
        paramsItems["gs"] = c["grupo_slug"]
        paramsItems["os"] = c["opcao_slug"]

        items = db.execute(items_sql, **paramsItems) or []

        out.append({
            "grupo": c["grupo"],
            "grupo_slug": c["grupo_slug"],
            "opcao": c["opcao"],
            "opcao_slug": c["opcao_slug"],
            "ocorrencias": c["ocorrencias"],
            "esgotados": c["esgotados"] or 0,
            "media_valor_extra": float(c["media_valor_extra"] or 0),
            "amostra_itens": [
                {
                    "item_id": r["item_id"],
                    "item_nome": r["item_nome"],
                    "valor_extra": float(r["valor_extra"] or 0),
                    "esgotado": int(r["esgotado_bool"] or 0),
                }
                for r in items
            ],
        })

    return jsonify(out)

# ---------- /opcoes/bulk-update ----------
@app.route("/opcoes/bulk-update", methods=["POST"])
def opcoes_bulk_update():
    """
    Body:
    {
      "where": { "grupo_slug": "...", "opcao_slug": "..." },
      "restrict_items": [1,2,3],                  // IDs de cardapio (id_cardapio) - opcional
      "set": { "valor_extra": 22.0, "esgotado": 1 }, // pelo menos um
      "dry_run": true|false
    }
    """
    ensure_schema()

    data = request.get_json(force=True) or {}
    where = data.get("where") or {}
    carrinho = (data.get('carrinho') or "")
    set_ = data.get("set") or {}
    restrict_items = data.get("restrict_items") or []
    dry_run = bool(data.get("dry_run"))

    gslug = (where.get("grupo_slug") or "").strip().lower()
    oslug = (where.get("opcao_slug") or "").strip().lower()
    if not gslug or not oslug:
        return jsonify({"error": "where.grupo_slug e where.opcao_slug são obrigatórios."}), 400

    set_fields = {}
    if "valor_extra" in set_ and set_["valor_extra"] is not None:
        try:
            set_fields["valor_extra"] = float(set_["valor_extra"])
        except Exception:
            return jsonify({"error": "set.valor_extra inválido."}), 400
    if "esgotado" in set_ and set_["esgotado"] is not None:
        v = set_["esgotado"]
        if v in (0, 1, "0", "1", True, False, "true", "false", "True", "False"):
            set_fields["esgotado_bool"] = 1 if str(v).lower() in ("1", "true") else 0
        else:
            return jsonify({"error": "set.esgotado deve ser 0/1/true/false."}), 400

    if not set_fields:
        return jsonify({"error": "Inclua pelo menos um campo em 'set' (valor_extra/esgotado)."}), 400

    # Filtro base
    wh = ["grupo_slug = :gs", "opcao_slug = :os", "carrinho = :carrinho"]
    params = {"gs": gslug, "os": oslug, "carrinho": carrinho}

    # Restrição opcional por itens (id_cardapio)
    ids = []
    if restrict_items:
        ids = [int(x) for x in restrict_items if str(x).isdigit()]
        if not ids:
            return jsonify({"error": "restrict_items inválido/vazio."}), 400
        placeholders = ",".join([f":id{i}" for i in range(len(ids))])
        wh.append(f"id_cardapio IN ({placeholders})")
        for i, v in enumerate(ids):
            params[f"id{i}"] = v

    where_sql = " AND ".join(wh)

    # Impacto
    rows = db.execute(
        f"SELECT id_cardapio FROM opcoes WHERE {where_sql}",
        **params) or []
    matched = len(rows)
    items = sorted(list({r["id_cardapio"] for r in rows}))
    if dry_run:
        return jsonify({
            "matched": matched,
            "would_update": matched,
            "items": items,
            "dry_run": True
        })

    # UPDATE em transação
    set_clauses = []
    set_params = {}
    if "valor_extra" in set_fields:
        set_clauses.append("valor_extra = :nv")
        set_params["nv"] = float(set_fields["valor_extra"])
    if "esgotado_bool" in set_fields:
        set_clauses.append("esgotado_bool = :ne")
        set_params["ne"] = int(set_fields["esgotado_bool"])
    set_clauses.append("updated_at = :ts")
    set_params["ts"] = _now_iso()

    db.execute("BEGIN")
    try:
        sql = f"UPDATE opcoes SET {', '.join(set_clauses)} WHERE {where_sql}"
        db.execute(sql, **set_params, **params)
        updated = matched  # cs50/SQLite não dá rowcount confiável

        actor = request.headers.get("X-User") or "api"
        audit_id = db.execute(
            """
            INSERT INTO opcoes_audit (actor, where_json, set_json, dry_run, matched, updated, items_json, carrinho)
            VALUES (:actor, :w, :s, 0, :m, :u, :items, :carrinho)
            """,
            actor=actor,
            w=json.dumps({"grupo_slug": gslug, "opcao_slug": oslug}, ensure_ascii=False),
            s=json.dumps(set_fields, ensure_ascii=False),
            m=matched,
            u=updated,
            items=json.dumps(items),
            carrinho=carrinho
        )
        getCardapio({'emitir':True,'carrinho': carrinho})  # broadcast atualização do cardápio
        if not audit_id:
            rid = db.execute("SELECT last_insert_rowid() AS id")[0]["id"]
            audit_id = rid

        db.execute("COMMIT")
    except Exception as e:
        db.execute("ROLLBACK")
        return jsonify({"error": f"Falha ao aplicar: {e}"}), 500

    return jsonify({
        "matched": matched,
        "updated": updated,
        "items": items,
        "audit_id": audit_id,
        "dry_run": False
    })

# ---------- Reconstrução do JSON cardapio.opcoes ----------
def _read_cardapio_props_map(item_id: int):
    """
    Lê cardapio.opcoes e devolve mapa por nome do grupo com props a preservar:
      { "<nome_grupo>": {"ids": ..., "max_selected": ..., "obrigatorio": ...}, ... }
    """
    row = db.execute("SELECT opcoes FROM cardapio WHERE id = :id", id=item_id)
    if not row or not row[0]["opcoes"]:
        return {}
    try:
        data = json.loads(row[0]["opcoes"])
    except Exception:
        return {}
    out = {}
    for g in data if isinstance(data, list) else []:
        nome = (g.get("nome") or "").strip()
        if not nome:
            continue
        out[nome] = {
            "ids": g.get("ids") or "",
            "max_selected": g.get("max_selected", 1),
            "obrigatorio": g.get("obrigatorio", 0),
        }
    return out

def _build_opcoes_json_from_table(item_id: int, carrinho) -> str:
    """
    Monta a estrutura JSON de grupos/opções para um item
    a partir da tabela opcoes (campos: nome_grupo, opcao, valor_extra, esgotado_bool),
    preservando ids/max_selected/obrigatorio do JSON atual.
    """
    rows = db.execute("""
        SELECT nome_grupo, grupo_slug, opcao, valor_extra, esgotado_bool
        FROM opcoes
        WHERE id_cardapio = :id AND carrinho = :carrinho
        ORDER BY nome_grupo, opcao
    """, id=item_id, carrinho=carrinho) or []

    keep = _read_cardapio_props_map(item_id)
    grupos = {}
    for r in rows:
        gnome = (r["nome_grupo"] or "").strip()
        if not gnome:
            continue
        if gnome not in grupos:
            base = keep.get(gnome, {})
            grupos[gnome] = {
                "nome": gnome,
                "ids": base.get("ids", ""),
                "options": [],
                "max_selected": base.get("max_selected", 1),
                "obrigatorio": base.get("obrigatorio", 0),
            }
        grupos[gnome]["options"].append({
            "nome": r["opcao"],
            "valor_extra": float(r["valor_extra"] or 0),
            "esgotado": int(r["esgotado_bool"] or 0),
        })

    out = []
    for gnome in sorted(grupos.keys(), key=lambda s: s.lower()):
        gobj = grupos[gnome]
        gobj["options"] = sorted(gobj["options"], key=lambda x: (str(x["nome"]).lower()))
        out.append(gobj)

    return json.dumps(out, ensure_ascii=False)

# ---------- /opcoes/sync-json ----------
@app.route("/opcoes/sync-json", methods=["POST"])
def opcoes_sync_json():
    """
    Body:
      { "items": [1,2,3] }   // IDs de cardapio (obrigatório)
    Efeito:
      Reescreve cardapio.opcoes de cada item com base na tabela opcoes.
    """
    ensure_schema()

    data = request.get_json(force=True) or {}
    carrinho = data.get('carrinho')
    items = data.get("items")
    if not isinstance(items, list) or not items:
        return jsonify({"error": "Forneça 'items' como lista de IDs (ex.: [1,2,3])."}), 400

    item_ids = sorted(list({int(i) for i in items if str(i).isdigit()}))
    if not item_ids:
        return jsonify({"error": "Lista 'items' inválida."}), 400

    db.execute("BEGIN")
    synced = 0
    try:
        for iid in item_ids:
            new_json = _build_opcoes_json_from_table(iid, carrinho)
            db.execute(
                "UPDATE cardapio SET opcoes = :j WHERE id = :id",
                j=new_json, id=iid
            )
            synced += 1
        db.execute("COMMIT")
        getCardapio(True)  # broadcast atualização do cardápio
    except Exception as e:
        db.execute("ROLLBACK")
        return jsonify({"error": f"Falha ao sincronizar: {e}"}), 500

    return jsonify({"synced": synced, "items": item_ids})

# ======= /opcoes/group-props-bulk  (editar max_selected, obrigatorio, ids do GRUPO) =======
@app.route("/opcoes/group-props-bulk", methods=["POST"])
def opcoes_group_props_bulk():
    """
    Body:
    {
      "where": { "grupo_slug": "adicionais" },      // obrigatório
      "restrict_items": [1,2,3],                    // opcional (IDs de cardápio)
      "set": { "max_selected": 2, "obrigatorio": 1, "ids": "" },  // pelo menos um
      "dry_run": true|false
    }

    Efeito:
      - Descobre os itens que possuem esse grupo (via tabela `opcoes`).
      - Se dry_run: retorna só o impacto (quantos itens).
      - Se aplicar: reconstrói o JSON de cada item a partir da TABELA `opcoes`,
        e sobrescreve as propriedades do grupo alvo (max_selected / obrigatorio / ids).
    """
    ensure_schema()

    data = request.get_json(force=True) or {}
    where = data.get("where") or {}
    set_ = data.get("set") or {}
    restrict_items = data.get("restrict_items") or []
    dry_run = bool(data.get("dry_run"))
    carrinho = (data.get('carrinho') or "")
    gslug = (where.get("grupo_slug") or "").strip().lower()
    if not gslug:
        return jsonify({"error": "where.grupo_slug é obrigatório."}), 400

    # Valida campos do set
    set_fields = {}
    if "max_selected" in set_ and set_["max_selected"] is not None:
        try:
            ms = int(set_["max_selected"])
            if ms < 0:
                return jsonify({"error": "max_selected deve ser >= 0."}), 400
            set_fields["max_selected"] = ms
        except Exception:
            return jsonify({"error": "max_selected inválido (inteiro)."}), 400
    if "obrigatorio" in set_ and set_["obrigatorio"] is not None:
        v = set_["obrigatorio"]
        if v in (0, 1, "0", "1", True, False, "true", "false", "True", "False"):
            set_fields["obrigatorio"] = 1 if str(v).lower() in ("1", "true") else 0
        else:
            return jsonify({"error": "obrigatorio deve ser 0/1/true/false."}), 400
    if "ids" in set_ and set_["ids"] is not None:
        # Campo livre string
        set_fields["ids"] = str(set_["ids"])

    if not set_fields:
        return jsonify({"error": "Inclua pelo menos um campo em 'set' (max_selected/obrigatorio/ids)."}), 400

    # Monta filtro base para descobrir itens que possuem esse grupo
    wh = ["grupo_slug = :gs", "carrinho = :carrinho"]
    params = {"gs": gslug, "carrinho": carrinho}

    ids = []
    if restrict_items:
        ids = [int(x) for x in restrict_items if str(x).isdigit()]
        if not ids:
            return jsonify({"error": "restrict_items inválido/vazio."}), 400
        placeholders = ",".join([f":id{i}" for i in range(len(ids))])
        wh.append(f"id_cardapio IN ({placeholders})")
        for i, v in enumerate(ids):
            params[f"id{i}"] = v

    where_sql = " AND ".join(wh)

    # Coleta itens distintos que possuem esse grupo
    item_rows = db.execute(
        f"""
        SELECT DISTINCT id_cardapio
        FROM opcoes
        WHERE {where_sql}
        ORDER BY id_cardapio
        """,
        **params
    ) or []
    items = [r["id_cardapio"] for r in item_rows]
    matched = len(items)

    if dry_run:
        return jsonify({
            "matched": matched,
            "would_update": matched,
            "items": items,
            "dry_run": True
        })

    # Aplica nos JSONs de cada item
    db.execute("BEGIN")
    try:
        for iid in items:
            # Nome do grupo desse item (para casar com JSON)
            gr = db.execute(
                "SELECT MIN(nome_grupo) AS nome FROM opcoes WHERE id_cardapio = :id AND grupo_slug = :gs AND carrinho = :carrinho",
                id=iid, gs=gslug, carrinho = carrinho
            )
            group_name = (gr[0]["nome"] if gr and gr[0]["nome"] else "").strip()
            if not group_name:
                # não deve ocorrer, pois o item veio da opcoes com esse grupo_slug
                continue

            # Reconstrói JSON a partir da tabela (garante que grupos/opções estejam atualizados)
            json_str = _build_opcoes_json_from_table(iid, carrinho)
            try:
                data_json = json.loads(json_str) if json_str else []
            except Exception:
                data_json = []

            # Sobrescreve props do grupo alvo
            changed = False
            for g in data_json:
                if (g.get("nome") or "").strip() == group_name:
                    if "max_selected" in set_fields:
                        g["max_selected"] = int(set_fields["max_selected"])
                        changed = True
                    if "obrigatorio" in set_fields:
                        g["obrigatorio"] = int(set_fields["obrigatorio"])
                        changed = True
                    if "ids" in set_fields:
                        g["ids"] = set_fields["ids"]
                        changed = True
                    break

            if changed:
                new_str = json.dumps(data_json, ensure_ascii=False)
                db.execute("UPDATE cardapio SET opcoes = :j WHERE id = :id AND carrinho = :carrinho", j=new_str, id=iid, carrinho=carrinho)
                getCardapio(True)  # broadcast atualização do cardápio

        # Auditoria (reuso da tabela existente)
        actor = request.headers.get("X-User") or "api"
        audit_id = db.execute(
            """
            INSERT INTO opcoes_audit (actor, where_json, set_json, dry_run, matched, updated, items_json, carrinho)
            VALUES (:actor, :w, :s, 0, :m, :u, :items, :carrinho)
            """,
            actor=actor,
            w=json.dumps({"grupo_slug": gslug, "type": "group_props"}, ensure_ascii=False),
            s=json.dumps(set_fields, ensure_ascii=False),
            m=matched,
            u=matched,
            items=json.dumps(items),
            carrinho=carrinho
        )
        if not audit_id:
            rid = db.execute("SELECT last_insert_rowid() AS id")[0]["id"]
            audit_id = rid

        db.execute("COMMIT")
    except Exception as e:
        db.execute("ROLLBACK")
        return jsonify({"error": f"Falha ao aplicar propriedades do grupo: {e}"}), 500

    return jsonify({
        "matched": matched,
        "updated": matched,
        "items": items,
        "audit_id": audit_id,
        "dry_run": False
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
