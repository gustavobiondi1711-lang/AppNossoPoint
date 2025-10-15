from flask import send_from_directory
import atexit
import unicodedata
import qrcode
from qrcode.constants import ERROR_CORRECT_Q
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import Flask, request, jsonify, url_for
from flask_socketio import SocketIO, emit
from cs50 import SQL
from flask_cors import CORS
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
from pytz import timezone
import os, random, time, requests, threading
import pandas as pd
from io import BytesIO
import logging
logging.getLogger('matplotlib').setLevel(logging.WARNING)
import subprocess
import requests
import re
from twilio.rest import Client
from dotenv import load_dotenv
import jwt
import json
import os, io, base64, re, unicodedata 


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

app.config['SECRET_KEY'] = 'seu_segredo_aqui'
socketio = SocketIO(app, cors_allowed_origins="*")  
import shutil

SECRET_KEY = "sua_chave_super_secreta_aqui"

load_dotenv()
ACCOUNT_SID = os.getenv("ACCOUNT_SID_TWILIO")
AUTH_TOKEN  = os.getenv("AUTH_TOKEN_TWILIO")
VERIFY_SID  = os.getenv("VERIFY_SID") 

PIX_KEY = os.getenv("PIX_KEY", "nossopointdrinks@gmail.com")  # sua chave Pix (email/cpf/cnpj/phone/aleatória)
MERCHANT_NAME = os.getenv("PIX_MERCHANT_NAME", "NOSSOPOINT")   # até 25 chars
MERCHANT_CITY = os.getenv("PIX_MERCHANT_CITY", "SAO PAULO")    # até 15 chars, sem acento
TXID_PREFIX = os.getenv("PIX_TXID_PREFIX", "WEB")

client = Client(ACCOUNT_SID, AUTH_TOKEN)

CORS(
    app,
    resources={r"/*": {"origins": '*'}},
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)



def decode_number_jwt(token: str) -> int:
    decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    # decoded é dict; o sub tem o número
    print(decoded['sub'])
    return int(decoded["sub"])

@app.route("/validate_table_number_on_qr", methods=['POST'])
def validate_table_number_on_qr():
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



@app.route("/auth/sms/create", methods=["POST"])
def send_verification():
    print('creatingsms')
    phone = request.json.get("phone")
    #v = client.verify.v2.services(VERIFY_SID).verifications.create(to=phone, channel="sms")
    #print(v)
    return jsonify({"status": 'pending'}), 200

@app.route("/auth/sms/check", methods=["POST"])
def check_verification():
    print('verification')
    #phone = request.json.get("phone")
    #code = request.json.get("code")
    #chk = client.verify.v2.services(VERIFY_SID).verification_checks.create(to=phone, code=code)
    #print(chk)
    return jsonify({"status": 'approved'}), 200  # 'approved' se ok

@app.route('/pegar_pagamentos_comanda', methods=['POST'])
def pegar_pagamentos_comanda():
    data = request.get_json()
    comanda = data.get('comanda')
    dia = datetime.now(brazil).date()
    pagamentos = db.execute('SELECT * FROM pagamentos WHERE comanda = ? AND dia = ? AND ordem = 0',comanda,dia)
    if not pagamentos:
        pagamentos = []
    return {'pagamentos': pagamentos}

@app.route('/excluir_pagamento', methods=['POST'])
def excluir_pagamento():
    try:
        data = request.get_json()
        pagamento_id = data.get('pagamento_id')
        ids = db.execute('SELECT ids FROM pagamentos WHERE id = ?', pagamento_id)
        comanda = data.get('comanda')
        if ids and ids[0]['ids']:
            ids_list = json.loads(ids[0]['ids'])
            print('ids_list', ids_list)
            for row in ids_list:
                db.execute('UPDATE pedidos SET quantidade_paga = quantidade_paga - ?, preco = preco_unitario *NULLIF((quantidade-(quantidade_paga - ?)),0) WHERE id = ? AND dia = ?',row['quantidade'],row['quantidade'],row['id'],datetime.now(brazil).date())
        db.execute('DELETE FROM pagamentos WHERE id = ?', pagamento_id)
        
        handle_get_cardapio(comanda)
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
    db=SQL('sqlite:///data/dados.db')

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

from datetime import datetime, timedelta
from flask import request, jsonify

@app.route('/validate_token_on_qr', methods=['POST'])
def validate_token_on_qr():
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

@app.route('/guardar_login', methods=['POST'])
def guardar_login():
    
    print('entrou guardar login')
    data = request.get_json(silent=True) or {}
    number = str(data.get('numero'))
    print('number',number)

    if not number:
        return jsonify({"error": "Campo 'number' é obrigatório."}), 400

    # Busca 1 usuário; evite depender de != 'bloqueado' no WHERE para mensagens claras
    
    payload = {
    "sub": f"{number}",      # identificador do usuário (pode ser id, CPF, etc.)
    "name": f"nome:{number}",  # nome do usuário
    "iat": int(datetime.now(brazil).timestamp()),
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


@app.route('/salvarTokenCarg"o', methods=['POST'])
def salvarTokenCargo():
    data = request.get_json()
    username = data.get('username')
    cargo = data.get('cargo')
    token = data.get('token')
    print(f'data {data}, username {username}, token {token}')
    if db.execute('SELECT * FROM tokens WHERE token =?',token):
        db.execute('DELETE FROM tokens WHERE token = ?',token)
    if token and token!='semtoken':
        db.execute('INSERT INTO tokens (username,cargo,token) VALUES (?,?,?)',username,cargo,token)
    

    return "cargo e user inserido com sucesso"

def enviar_notificacao_expo(cargo,titulo,corpo,token_user,canal="default"):
    print(f'cargo {cargo} titulo, {titulo},corpo {corpo} canal {canal}')
    if cargo:
        tokens = db.execute('SELECT token FROM tokens WHERE cargo = ? AND token != ? GROUP BY token',cargo,'semtoken')
    else:
        tokens = db.execute('SELECT token FROM tokens WHERE token != ? GROUP BY token','semtoken')
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
    db.execute('DELETE FROM tokens WHERE cargo!=?','ADM')
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
    print('entrou no opcoes')
    data = request.get_json()
    item = data.get('pedido')
    print(item) 
    opcoes = db.execute('SELECT opcoes FROM cardapio WHERE item = ?', item)
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
    if int(ordem) != 0:
        
        print(f'ORDEM : {ordem}')
        dia = datetime.now(brazil).date()
        dados = db.execute('''
                SELECT pedido, id, ordem, SUM(quantidade) AS quantidade, SUM(preco) AS preco
                FROM pedidos WHERE comanda = ? AND ordem = ? AND dia = ? AND pedido != ?
                GROUP BY pedido, (preco/quantidade)
            ''', comanda, int(ordem),dia, 'Comanda Aberta')
    
        return{'data':dados,'preco':''}
    else:
        print('ordem 0')
        handle_get_cardapio(comanda)
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
        return {'data': True, 'cargo': existe[0]['cargo']}
    else:
        print('false')
        return {'data': False}


@app.route('/verificar_quantidade', methods=['POST'])
def verif_quantidade():
    data = request.json  # Use request.json para pegar o corpo da requisição
    item = data.get('item')
    quantidade = data.get('quantidade')

    categoria = db.execute(
        'SELECT categoria_id FROM cardapio WHERE item = ?', item)

    if categoria and categoria[0]['categoria_id'] != 2:
        verificar_estoque = db.execute(
            'SELECT quantidade,estoque_ideal FROM estoque WHERE item = ?', item)

        if verificar_estoque:
            estoque_atual = float(verificar_estoque[0]['quantidade'])
            if estoque_atual - float(quantidade) < 0:
                return {'erro': 'Estoque insuficiente', 'quantidade': estoque_atual}
            elif estoque_atual:
                estoque_ideal = verificar_estoque[0]['estoque_ideal']
                if estoque_ideal:
                    alerta = 7 if item!='tropical' and item!='red bull' else 3
                    if estoque_atual<alerta:
                        return {'erro': False, 'quantidade': estoque_atual}
    return {'erro': False}





@app.route('/changeBrinde', methods=['POST'])
def change_brinde():
    datas = request.json
    data = datas.get('pedido').lower()
    print(data)
    pedidos = db.execute('SELECT item FROM cardapio')
    pedidos_filtrados = []
    cont = 0
    for row in pedidos:
        if cont < 2:
            pedido = row['item']
            if pedido.startswith(data):
                cont += 1
                pedidos_filtrados.append(pedido)
        else:
            break
    return {'data': pedidos_filtrados}

@app.route('/updatePrinted', methods=['POST'])
def update_printed():
    data = request.json or {}
    pedido_id = data.get('pedidoId')
    if not pedido_id:
        return jsonify({'status': 'error', 'message': 'pedidoId ausente'}), 400

    # CORREÇÃO: definir printed = 1 e passar parâmetros corretamente
    db.execute('UPDATE pedidos SET printed = ? WHERE id = ?', 1, pedido_id)
    return jsonify({'status': 'success'}), 200


@app.route('/getPendingPrintOrders', methods=['POST'])
def get_pending_print_orders():
    print('getPendingPrintOrders')
    data = request.json or {}

    # opcional: permitir que o cliente mande printed/ordem; manter defaults
    printed = 0
    ordem = 0

    dia = datetime.now(brazil).date()
    inicio_limite = (datetime.now(brazil) - timedelta(minutes=25)).strftime('%H:%M')

    # CORREÇÃO: usar tupla de parâmetros
    pedidos = db.execute(
        'SELECT * FROM pedidos WHERE printed = ? AND ordem = ? AND dia = ? AND inicio > ? AND categoria = ?',
        printed, ordem, dia, inicio_limite, 1
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
def getCardapio(emitirBroadcast):
    dataCardapio = db.execute("SELECT * FROM cardapio ORDER BY item ASC")
    if emitirBroadcast:
        socketio.emit('respostaCardapio',{'dataCardapio':dataCardapio})
    else:
        emit('respostaCardapio',{'dataCardapio':dataCardapio},broadcast=emitirBroadcast)

@socketio.on('getPedidos')
def getPedidos(emitirBroadcast):
    print('getPedidos')
    print('emitirBroadcast', emitirBroadcast)
    dia = datetime.now(brazil).date()
    dataPedidos = db.execute('SELECT * FROM pedidos WHERE dia = ? AND pedido != ?',dia,'Comanda Aberta')
    if not dataPedidos:
        dataPedidos = []
    if emitirBroadcast:
        socketio.emit('respostaPedidos',{'dataPedidos':dataPedidos})
    else:
        emit('respostaPedidos',{'dataPedidos':dataPedidos},broadcast=emitirBroadcast)

@socketio.on('getItensPromotion')
def getPedidosPromotion(emitirBroadcast):
    dia = datetime.now(brazil).date()
    dataCardapio = db.execute('SELECT id,item FROM cardapio')
    if dataCardapio:
        emit('respostaItensPromotion',{'dataCardapio':dataCardapio},broadcast=emitirBroadcast)

@socketio.on('getEstoque')
def getEstoque(emitirBroadcast):
    dataEstoque=db.execute('SELECT * FROM estoque ORDER BY item')
    if dataEstoque:
        emit('respostaEstoque',{'dataEstoque':dataEstoque},broadcast=emitirBroadcast)

@socketio.on('getEstoqueGeral')
def getEstoqueGeral(emitirBroadcast):
    dataEstoqueGeral=db.execute('SELECT * FROM estoque_geral ORDER BY item')
    if dataEstoqueGeral:
        emit('respostaEstoqueGeral',{'dataEstoqueGeral':dataEstoqueGeral},broadcast=emitirBroadcast)


@socketio.on('getComandas')
def getComandas(emitirBroadcast):
    dia = datetime.now(brazil).date()
    sql_abertas = """
        SELECT comanda
        FROM pedidos
        WHERE ordem = ? AND dia = ?
        GROUP BY comanda
        ORDER BY
        CASE
            WHEN comanda GLOB '[0-9]*' THEN CAST(comanda AS INTEGER)
            ELSE NULL
        END,
        comanda ASC
        """
    dados_comandaAberta = db.execute(sql_abertas, 0, dia)

    dados_comandaFechada = db.execute(
        'SELECT comanda,ordem FROM pedidos WHERE ordem !=? AND dia = ? GROUP BY comanda ORDER BY comanda ASC', 0,dia)
    if dados_comandaAberta or dados_comandaFechada:
        if emitirBroadcast:
            socketio.emit('respostaComandas', {'dados_comandaAberta':dados_comandaAberta,'dados_comandaFechada':dados_comandaFechada})
        else:
            emit('respostaComandas', {'dados_comandaAberta':dados_comandaAberta,'dados_comandaFechada':dados_comandaFechada},broadcast=emitirBroadcast)


@socketio.on('users')
def users(emitirBroadcast):
    users = db.execute('SELECT * from usuarios')
    emit('usuarios',{'users': users},broadcast=emitirBroadcast)











@socketio.on('disconnect')
def handle_disconnect():
    print('Cliente desconectado')

# Manipulador para inserir dados


@socketio.on('refresh')
def refresh():
    handle_connect()

@socketio.on('EditingEstoque')
def editEstoque(data):
    print('editar estoque')
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
        if db.execute(f'SELECT item FROM {estoque} WHERE item = ?',item): emit(f'{estoque}Alterado',{'erro':'Nome Igual'})
        db.execute(f"INSERT INTO {estoque} (item,quantidade,estoque_ideal) VALUES (?,?,?)",item,quantidade,estoque_ideal)
        if mudar_os_dois:
            alteracao+=' em ambos os estoques'
            estoque_sec = 'estoque' if estoque=='estoque_geral' else 'estoque_geral'
            if not db.execute(f'SELECT item FROM {estoque_sec} WHERE item = ?',item): db.execute(f"INSERT INTO {estoque_sec} (item,quantidade,estoque_ideal) VALUES (?,?,?)",item,0,0)

    elif tipo == 'Remover':
        tipo='Removeu'
        db.execute(f"DELETE FROM {estoque} WHERE item=?",item)
        if mudar_os_dois:
            alteracao+=' de ambos os estoques'
            estoque_sec = 'estoque' if estoque=='estoque_geral' else 'estoque_geral'
            db.execute(f"DELETE FROM {estoque_sec} WHERE item=?",item)
    else:
        alteracao+=': alterou'
        tipo='Editou'
        antigo = db.execute(f'SELECT estoque_ideal FROM {estoque} WHERE item = ?',item)
        antig = 'inexistente' if not antigo else antigo[0]['estoque_ideal']
        if estoque_ideal and novoNome:
            if type(antig)!=str and int(estoque_ideal) != antig:
                alteracao += f' estoque ideal de {int(antig)} para {float(estoque_ideal)} e {item} para {novoNome}'
            else: alteracao+=f' {item} para {novoNome}'
            
            db.execute(f"UPDATE {estoque} SET item=?, estoque_ideal=? WHERE item=?",novoNome, estoque_ideal,item )
        elif estoque_ideal:
            if type(antig)!=str and int(estoque_ideal) != antig:
                alteracao+= f' estoque ideal de {int(antig)} para {estoque_ideal}'
            db.execute(f"UPDATE {estoque} SET estoque_ideal=? WHERE item=?",estoque_ideal,item)
        elif novoNome:
            alteracao+= f' Nome do {item} para {novoNome}'
            db.execute(f"UPDATE {estoque} SET item=? WHERE item=?",novoNome,item ) 
            if mudar_os_dois:
                alteracao+=f' em ambos os estoques'
                estoque_sec = 'estoque' if estoque=='estoque_geral' else 'estoque_geral'
                db.execute(f"UPDATE {estoque_sec} SET item=? WHERE item=?",novoNome,item )

    insertAlteracoesTable(estoque,alteracao,tipo,f'Botao + no Editar {estoque}',usuario)
    alteracao=f"{usuario} {tipo} {alteracao}"
    enviar_notificacao_expo('ADM','Estoque Editado',alteracao,token_user)
    if mudar_os_dois:
        getEstoqueGeral(True)
        getEstoque(True)
    elif estoque=='estoque_geral':
        getEstoqueGeral(True)
    else: getEstoque(True)
            
@socketio.on("editCargo")
def edit_cargo(data):
    print('editcargo')
    usuario=data.get("usuario")
    print (usuario)
    cargo=data.get("cargo")
    print(cargo)
    db.execute("UPDATE usuarios SET cargo = ? WHERE username = ?", cargo, usuario)
    users(True)
    
     



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

        comanda = data.get('comanda')
        pedidos = data.get('pedidosSelecionados') or []
        quantidades = data.get('quantidadeSelecionada') or []
        horario = data.get('horario')
        username = data.get('username')
        preco = data.get('preco')  # flag de brinde
        nomes = data.get('nomeSelecionado') or []
        token_user = data.get('token_user')

        # AGORA: opcoesSelecionadas já vem estruturadas (listas/dicts com options e valor_extra)
        opcoesSelecionadas = data.get('opcoesSelecionadas') or []

        # "extraSelecionados" continua sendo texto/anotação, separado das opções
        extra_list = data.get('extraSelecionados') or []

        print(f"opcoesSelecionadas (estruturadas) = {opcoesSelecionadas}")

        # Helpers seguros para acessar por índice
        def get_or_default(seq, idx, default):
            if isinstance(seq, list):
                return seq[idx] if idx < len(seq) else default
            return seq if not isinstance(seq, (list, tuple)) else default

        def selecionar_opcoes_por_indice(idx):
            """
            Retorna a seleção de opções referente ao item 'idx'.
            Formatos aceitos no payload:
            A) lista alinhada por item: [ [grupos...], [grupos...] ]
            B) lista de grupos (apenas 1 item): [ {nome, options:[...]} , ... ]
            C) dict único: { ... }
            """
            sel = opcoesSelecionadas
            if isinstance(sel, list):
                # A) lista alinhada por item?
                if idx < len(sel) and (isinstance(sel[idx], list) or isinstance(sel[idx], dict)):
                    return sel[idx]
                # B) se só tem 1 item, pode ser a lista de grupos inteira
                if len(pedidos) == 1:
                    return sel
                return []
            elif isinstance(sel, dict):
                return sel
            else:
                return []

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

        # logs úteis
        print(username)
        print(comanda)
        print(pedidos)
        print(quantidades)
        print(horario)
        print(nomes)

        if not nomes:
            nomes = []
            for _ in range(len(pedidos)):
                nomes.append('-1')

        for i in range(len(pedidos)):
            pedido = pedidos[i]
            quantidade = float(quantidades[i])

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
                print('else (item não encontrado no cardápio)')

            # extra (texto) totalmente separado das opções
            extra_txt = get_or_default(extra_list, i, "") or ""
            if extra_txt:
                extra_txt = str(extra_txt).strip()

            # nome do cliente/identificador
            nome_cliente = get_or_default(nomes, i, "-1") or "-1"

            # === NOVA LÓGICA: opções estruturadas + valor_extra por unidade ===
            selecao_opcoes = selecionar_opcoes_por_indice(i)
            extra_por_unidade = somar_extra_por_unidade(selecao_opcoes)  # soma dos valor_extra
            opcoes_json = json.dumps(selecao_opcoes or [], ensure_ascii=False)

            # notificação por categoria (mantido)
            horario_entrega = None
            if categoria == 3:
                horario_entrega = (datetime.now(brazil) + timedelta(minutes=40)).strftime('%H:%M')

                enviar_notificacao_expo('Cozinha', 'Novo Pedido',
                                        f'{quantidade} {pedido} {extra_txt} na {comanda}', token_user)
            elif categoria == 2:
                horario_entrega = (datetime.now(brazil) + timedelta(minutes=15)).strftime('%H:%M')
                enviar_notificacao_expo('Colaborador', 'Novo Pedido',
                                        f'{quantidade} {pedido} {extra_txt} na {comanda}', token_user)
            
                

            # === CÁLCULO DE PREÇO COM NOVAS OPÇÕES ===
            # preco_unitario_final = preco_base + extra_por_unidade
            # preco_total = preco_unitario_final * quantidade
            preco_unitario_final = preco_base + float(extra_por_unidade or 0)
            preco_total = preco_unitario_final * quantidade
            remetente = 'Carrinho:NossoPoint'
            if preco:  # brinde: força preco 0 (mantém comportamento antigo)
                db.execute(
                    'INSERT INTO pedidos(comanda, pedido, quantidade, preco, categoria, inicio, estado, extra, opcoes, username, ordem, nome, remetente, dia,horario_para_entrega) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,?)',
                    comanda, pedido, quantidade, 0, categoria, horario, 'A Fazer',
                    extra_txt, opcoes_json, username, 0, nome_cliente, remetente, dia, horario_entrega
                )

            elif not preco_unitario_row:  # item fora do cardápio (sem preço conhecido)
                db.execute(
                    'INSERT INTO pedidos(comanda, pedido, quantidade, preco, categoria, inicio, estado, extra, opcoes, username, ordem, nome,remetente, dia, horario_para_entrega) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,?,?)',
                    comanda, pedido, quantidade, 0, categoria, horario, 'A Fazer',
                    extra_txt, opcoes_json, username, 0, nome_cliente,remetente ,dia, horario_entrega
                )

            else:
                # sempre que conhecemos o preço base, gravamos também preco_unitario
                db.execute(
                    'INSERT INTO pedidos(comanda, pedido, quantidade, preco, preco_unitario, categoria, inicio, estado, extra, opcoes, username, ordem, nome,remetente, dia, horario_para_entrega) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? , ?, ?)',
                    comanda, pedido, quantidade,
                    preco_total, preco_unitario_final, categoria, horario, 'A Fazer',
                    extra_txt, opcoes_json, username, 0, nome_cliente, remetente,dia, horario_entrega
                )

            # mantém o restante da lógica (emissão, estoque, etc.)
            if categoria == 1:
                id = db.execute("SELECT last_insert_rowid() AS id")[0]['id']
                hora = datetime.now(brazil).strftime('%H:%M')
                emit('emitir_pedido_restante',
                     {'mesa': comanda, 'pedido': pedido, 'quantidade': quantidade,
                      'extra': extra_txt, 'hora': hora, 'sendBy': username, 'id': id},
                     broadcast=True)

            quantidade_anterior = db.execute(
                'SELECT quantidade FROM estoque WHERE item = ?', pedido)
            dados_pedido = db.execute(
                'SELECT * FROM pedidos WHERE dia = ? AND pedido != ?', dia, 'Comanda Aberta')

            if quantidade_anterior:
                quantidade_nova = float(quantidade_anterior[0]['quantidade']) - quantidade
                db.execute(
                    'UPDATE estoque SET quantidade = ? WHERE item = ?', quantidade_nova, pedido)
                if quantidade_nova < 10:
                    emit('alerta_restantes',
                         {'quantidade': quantidade_nova, 'item': pedido}, broadcast=True)
                getEstoque(True)

        faturamento(True)
        getPedidos(True)
        getComandas(True)
        handle_get_cardapio(comanda)

    except Exception as e:
        print("Erro ao inserir ordem:", e)
        emit('error', {'message': str(e)})


@socketio.on('faturamento')
def faturamento(data):

    if type(data)!=bool:
        change = data.get('change')
        dia = datetime.now(brazil).date() + timedelta(days=(change))
        dia_formatado = dia.strftime('%d/%m')
        emitir = data.get('emitir')
    else:
        dia = datetime.now(brazil).date()
        emitir = data
        dia_formatado = dia.strftime('%d/%m')
    metodosDict=db.execute("SELECT forma_de_pagamento,SUM(valor_total) AS valor_total FROM pagamentos WHERE dia =? GROUP BY forma_de_pagamento",dia)
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
    caixinha = db.execute("SELECT COALESCE(SUM(caixinha),0) AS total_caixinha FROM pagamentos WHERE dia = ?", dia)
    caixinha = caixinha[0]['total_caixinha'] or 0
    dezporcento = db.execute("SELECT COALESCE(SUM(dez_por_cento),0) AS total_dezporcento FROM pagamentos WHERE dia = ?", dia)
    dezporcento = dezporcento[0]['total_dezporcento'] or 0
    desconto = db.execute("SELECT SUM(valor) AS total_desconto FROM pagamentos WHERE dia = ? AND tipo = ?", dia,'desconto')
    desconto = desconto[0]['total_desconto'] or 0
        
    total_recebido = db.execute("SELECT SUM(valor_total) AS total_recebido FROM pagamentos WHERE dia = ? AND tipo = ?", dia, 'normal')
    total_recebido = total_recebido[0]['total_recebido'] or 0
    pedidosQuantDict = db.execute("""
        SELECT categoria,
               SUM(quantidade) AS quantidade_total,
               SUM(preco_unitario*NULLIF(quantidade,0))      AS preco_total
        FROM pedidos
        WHERE dia = ?
          AND pedido != ?
        GROUP BY categoria
        ORDER BY categoria ASC
    """, dia, 'Comanda Aberta')
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
    vendas_user =db.execute('SELECT username, SUM(preco_unitario *NULLIF(quantidade,0)) AS valor_vendido, SUM(quantidade)  AS quant_vendida FROM pedidos WHERE dia = ? GROUP BY username ORDER BY SUM(preco_unitario*NULLIF(quantidade,0)) DESC',dia)
    print('vendas_user', vendas_user)

    emit('faturamento_enviar', {'dia': str(dia_formatado),
                                'faturamento': total_recebido,
                                'faturamento_previsto': faturamento_previsto,
                                'drink': drink,
                                'porcao': porcao,
                                "restante": restante,
                                "pedidos": pedidos,
                                "caixinha": caixinha,
                                "dezporcento":dezporcento,
                                "desconto":desconto,
                                "pix":pix,
                                "debito":debito,
                                "credito":credito,
                                "dinheiro":dinheiro,
                                "vendas_user":vendas_user
                                },
        broadcast=emitir,
        )
    


@socketio.on('alterarValor')
def alterarValor(data):
    dia = datetime.now(brazil).date()
    valor = float(data.get('valor'))
    tipo = data.get('categoria')
    comanda = data.get('comanda')
    print(tipo)
    print(valor)
        
    db.execute('INSERT INTO pagamentos(valor,valor_total,comanda,ordem,tipo,dia) VALUES (?,?,?,?,?)',valor,valor,comanda,0,tipo,dia)
    faturamento(True)
    handle_get_cardapio(comanda)



@socketio.on('atualizar_pedidos')
def handle_atualizar_pedidos(data):
    dia = datetime.now(brazil).date()
    p = data.get('pedidoAlterado')
    usuario=data.get('usuario')
    alteracoes=f'{p["pedido"]}, '
    token_user = data.get('token')
    preco = db.execute(
        'SELECT comanda,preco,quantidade,extra,pedido FROM pedidos WHERE id = ? AND dia = ?', p['id'],dia)
    if preco : 
        p2 = preco[0]
        dif={k:(p[k],p2[k]) for k in p.keys() & p2.keys() if p[k]!=p2[k]}.keys()
        for key in dif:
            alteracoes+=f'{key} de {p2[key]} para {p[key]} '
        print(alteracoes)
        db.execute("UPDATE pedidos SET comanda = ?, pedido = ?, quantidade = ?, extra = ?,preco = ? WHERE id = ? AND dia = ?",
               p["comanda"], p["pedido"], p["quantidade"], p["extra"], p["preco"], p["id"],dia)
    insertAlteracoesTable('pedidos',alteracoes,'editou','Tela Pedidos',usuario)
    alteracoes=f'{usuario} Editou {alteracoes}'
    enviar_notificacao_expo('ADM','Pedido Editado',alteracoes,token_user,usuario)
    handle_get_cardapio(str(p["comanda"]))


@socketio.on('desfazer_pagamento')
def desfazer_pagamento(data):
    dia = datetime.now(brazil).date()
    comanda = data.get('comanda')
    ids_dict = db.execute('''
        SELECT ids FROM pagamentos
        WHERE id = (
            SELECT id FROM pagamentos
            WHERE comanda = ? AND ordem = ? AND dia = ?
            ORDER BY id DESC
            LIMIT 1
        )
    ''', comanda, 1, dia)
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
            WHERE comanda = ? AND ordem = ? AND dia = ?
            ORDER BY id DESC
            LIMIT 1
        )
    ''', comanda, 1, dia)

    db.execute('UPDATE pagamentos SET ordem = ordem - ? WHERE comanda = ? AND dia = ? AND ordem != ?',1,comanda,dia,0)
    db.execute('UPDATE pedidos SET ordem = ordem - ? WHERE comanda = ? AND dia = ? AND ordem != ?',1,comanda,dia,0)
    faturamento(True)
    handle_get_cardapio(comanda)



@socketio.on('delete_comanda')
def handle_delete_comanda(data):
    try:
        dia = datetime.now(brazil).date()
        # Identificar a comanda recebida
        if type(data) == str:
            comanda = data
        else:
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
            db.execute('INSERT INTO pagamentos (valor,valor_total,caixinha,dez_por_cento,tipo,ordem,dia,forma_de_pagamento,comanda,horario) VALUES (?,?,?,?,?,?,?,?,?,?)',valor_pago,valor_pago+caixinha+dez_por_cento,caixinha,dez_por_cento,'normal',0,dia,forma_de_pagamento,comanda,datetime.now(brazil).strftime('%H:%M'))
            
           

        db.execute('UPDATE pedidos SET ordem = ordem +? WHERE comanda = ? AND dia = ?',1,comanda, dia)
        db.execute('UPDATE pagamentos SET ordem = ordem + ? WHERE comanda = ? AND dia = ?',1,comanda,dia)
        faturamento(True)
        handle_get_cardapio(comanda)
        emit('comanda_deleted', {'fcomanda': comanda}, broadcast=True)

    except Exception as e:
        print("Erro ao apagar comanda:", e)
        emit('error', {'message': str(e)})


@socketio.on('pagar_parcial')
def pagar_parcial(data):
    comanda = data.get('fcomanda')
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
    
    totalComandaDict = db.execute('SELECT SUM(preco) AS total FROM pedidos WHERE comanda = ? AND ordem = ? AND dia = ?', comanda, 0,dia)
    valorTotalDict = db.execute('SELECT SUM(valor_total) as total FROM pagamentos WHERE dia = ? AND comanda = ? AND ordem = ? AND tipo = ?',dia,comanda,1,'normal')
    
    if valorTotalDict and valorTotalDict[0]['total']:
        valorTotal = valorTotalDict[0]['total']
    else:
        valorTotal = 0

    db.execute('INSERT INTO pagamentos (valor,valor_total,caixinha,dez_por_cento,tipo,ordem,dia,forma_de_pagamento,comanda,horario) VALUES (?,?,?,?,?,?,?,?,?,?)',valor_pago,valor_pago+caixinha+dez_por_cento,caixinha,dez_por_cento,'normal',0,dia,forma_de_pagamento,comanda,datetime.now(brazil).strftime('%H:%M'))
    faturamento(True)
    if valorTotal+valor_pago>=totalComandaDict[0]['total']:
        db.execute('UPDATE pagamentos SET ordem = ordem + ? WHERE dia = ? AND comanda = ?',1,dia,comanda)
        handle_delete_comanda(comanda)
    
    handle_get_cardapio(comanda)


@socketio.on('get_ingredientes')
def get_ingredientes(data):
    item = data.get('ingrediente')
    ingredientes = db.execute(
        'SELECT instrucoes FROM cardapio WHERE item = ?', item)

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
    estado = data.get('estado')
    horario = datetime.now(pytz.timezone(
        "America/Sao_Paulo")).strftime('%H:%M')
    print(f'id: {id}, estado: {estado}, horario: {horario}')

    if estado == 'Pronto':
        print('entrou no pronto')
        db.execute('UPDATE pedidos SET fim = ? WHERE id = ?', horario, id)
    elif estado == 'Em Preparo':
        print('entrou no em preparo')
        db.execute('UPDATE pedidos SET comecar = ? WHERE id = ?', horario, id)
    
    db.execute('UPDATE pedidos SET estado = ? WHERE id = ?',estado,
               id)
    print('depois do update')
    getPedidos(True)


@socketio.on('atualizar_estoque_geral')
def atualizar_estoque_geral(data):
    usuario = data.get('username')
    itensAlterados = data.get('itensAlterados')
    token_user = data.get('token')
    for i in itensAlterados:
        item = i['item']
        quantidade = i['quantidade']
        quantidadeAnterior=db.execute("SELECT quantidade FROM estoque_geral WHERE item =?",item)
        if quantidadeAnterior: anterior=quantidadeAnterior[0]['quantidade']
        db.execute('UPDATE estoque_geral SET quantidade = ? WHERE item = ?',
                   float(quantidade), item)
        insertAlteracoesTable('estoque geral',f'{i["item"]} de {int(anterior)} para {i["quantidade"]}','editou','Editar Estoque Geral',usuario)
        enviar_notificacao_expo('ADM','Estoque Geral Atualizado',f'{usuario} Editou {i["item"]} de {int(anterior)} para {i["quantidade"]}',token_user)
    getEstoqueGeral(True)


@socketio.on('atualizar_estoque')
def atualizar_estoque(data):
    usuario = data.get('username')
    itensAlterados = data.get('itensAlterados')
    token_user = data.get('token')
    for i in itensAlterados:
        item = i['item']
        anterior=''
        quantidade = i['quantidade']
        quantidadeAnterior=db.execute("SELECT quantidade FROM estoque WHERE item=?",item)
        if quantidadeAnterior:anterior=quantidadeAnterior[0]['quantidade']
        db.execute('UPDATE estoque SET quantidade = ? WHERE item = ?',
                   float(quantidade), item)
        insertAlteracoesTable('estoque carrinho',f'{i["item"]} de {int(anterior)} para {i["quantidade"]}','editou','Editar Estoque',usuario)
        enviar_notificacao_expo('ADM','Estoque Atualizado',f'{usuario} Editou {i["item"]} de {int(anterior)} para {i["quantidade"]}',token_user)
        
        
    getEstoque(True)


@socketio.on('atualizar_comanda')
def atualizar__comanda(data):
    print(data)
    itensAlterados = data.get('itensAlterados')
    print(itensAlterados)
    comanda = data.get('comanda')
    usuario = data.get('username')
    dia = datetime.now(brazil).date()
    token_user = data.get('token')
    for i in itensAlterados:

        item = i['pedido']
        antes_dic = db.execute('SELECT quantidade FROM pedidos WHERE pedido = ? AND ordem = ? AND dia = ?',item,0,dia)
        antes = antes_dic[0]['quantidade']

        quantidade = float(i['quantidade'])
        print(f'quantidade = {quantidade}')
        if quantidade == 0:
            quantidade_total_dic = db.execute('''SELECT quantidade,id FROM pedidos
            WHERE pedido = ? AND comanda = ? AND ordem = ? AND dia = ?;
                ''', item, comanda,dia, 0)
            quantidade_total = 0
            for j in quantidade_total_dic:
                quantidade_total += float(j['quantidade'])
            verifEstoq = db.execute(
                'SELECT * FROM estoque WHERE item = ?', item)
            if verifEstoq:
                db.execute(
                    'UPDATE estoque SET quantidade = quantidade + ? WHERE item = ?', quantidade_total, item)
                
                insertAlteracoesTable('Pedido Editado',f'{i["pedido"]} de {antes} para {i["quantidade"]}','editou','Editar Comanda',usuario)
                enviar_notificacao_expo('ADM','Comanda Editada',f'{usuario} Editou {i["pedido"]} de {antes} para {i["quantidade"]}',token_user)


            db.execute(
                'DELETE FROM pedidos WHERE pedido = ? AND comanda = ? AND ordem = ? AND dia = ?', item, comanda, 0,dia)
        else:
            print(i['preco'])
            preco = float(i['preco'])/quantidade
            print(f'quantidade {quantidade}')
            print(f'preco {preco}')
            quantidade_total_dic = db.execute('''SELECT quantidade,id FROM pedidos
                WHERE pedido = ? AND comanda = ? AND ordem = ? AND preco / quantidade = ? AND dia = ?;
                    ''', item, comanda, 0, preco,dia)
            quantidade_total = 0
            for j in quantidade_total_dic:
                quantidade_total += float(j['quantidade'])
            quantidade_atualizada = (quantidade_total - quantidade)*-1
            print(f'quantidade atualizada acima {quantidade_atualizada}')
            preco_atualizado = preco*quantidade_atualizada

            if quantidade_atualizada < 0:
                quantidade_atualizada *= -1
                ids = db.execute(
                    'SELECT id,quantidade FROM pedidos WHERE pedido = ? AND comanda = ? AND ordem = ? AND dia = ?', item, comanda, 0,dia)
                verifEstoq = db.execute(
                    'SELECT * FROM estoque WHERE item = ?', item)
                if verifEstoq:
                    db.execute(
                        'UPDATE estoque SET quantidade = quantidade + ? WHERE item = ?', quantidade_atualizada, item)
                insertAlteracoesTable('Pedido Editado',f'{i["pedido"]} de {antes} para {i["quantidade"]} na comanda:{comanda} ','editou','Editar Comanda',usuario)
                enviar_notificacao_expo('ADM','Comanda Editada',f'{usuario} Editou {i["pedido"]} de {antes} para {i["quantidade"]} na comanda:{comanda}',token_user)

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
                    'SELECT * FROM estoque WHERE item = ?', item)
                if verifEstoq:
                    db.execute(
                        'UPDATE estoque SET quantidade = quantidade - ? WHERE item = ?', quantidade_atualizada, item)
                insertAlteracoesTable('Pedido Editado',f'{i["pedido"]} de {antes} para {i["quantidade"]} na comanda:{comanda}','editou','Editar Comanda',usuario)
                enviar_notificacao_expo('ADM','Comanda Editada',f'{usuario} Editou {i["pedido"]} de {antes} para {i["quantidade"]} na comanda:{comanda}',token_user)
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
                                    GROUP BY pedido
                                    HAVING SUM(quantidade) = 0
                                ) subquery
                            );
                        ''', comanda,dia, 'Comanda Aberta')
    
    getEstoque(True)
    handle_get_cardapio(comanda)

@socketio.on('transferir_para_estoque_carrinho')
def transferir_para_estoque_carrinho(data):
    itensAlterados = data.get('itensAlterados')
    token = data.get('token')
    usuario = data.get('username')
    for i in itensAlterados:
        
        quantidade_antiga = db.execute('SELECT quantidade FROM estoque_geral WHERE item = ?',i['item'])
        existe_no_estoque = db.execute('SELECT quantidade FROM estoque WHERE item = ?',i['item'])
        if quantidade_antiga and existe_no_estoque:
            quantidade_antig = float(quantidade_antiga[0]['quantidade'])
            quantidade = float(i['quantidade'])
            db.execute('UPDATE estoque SET quantidade = quantidade + ? WHERE item = ?',quantidade_antig-quantidade,i['item'])
            getEstoque(True)
            insertAlteracoesTable('Estoque Carrinho',f'{i["item"]} de {existe_no_estoque[0]["quantidade"]} para {quantidade_antig-quantidade}','editou','Transferir para Estoque Carrinho',usuario)
            enviar_notificacao_expo('ADM','Estoque Carrinho Tranferir',f'{usuario} Editou {i["item"]} de {existe_no_estoque[0]["quantidade"]} para {quantidade_antig-quantidade}',token)
    atualizar_estoque_geral(data)
            

@socketio.on('get_cardapio')
def handle_get_cardapio(data):
    print('get_cardapio')
    try:
        dia = datetime.now(brazil).date()
        if type(data) == str:
            print('if')
            fcomanda = data
            ordem = 0
        else:
            print('else')
            fcomanda = data.get('fcomanda')
            ordem = data.get('ordem')
        if ordem == 0:
            valor_pago = db.execute('SELECT SUM(valor) AS total FROM pagamentos WHERE comanda = ? AND ordem = ? AND dia = ? AND (tipo = ? OR tipo = ?)', fcomanda, ordem,dia,'normal','desconto')
            print('valor_pago', valor_pago)
            preco_pago = 0
            if valor_pago and valor_pago[0]['total']:
                
                preco_pago = float(valor_pago[0]['total'])
            
            total_comanda = db.execute('SELECT SUM(preco_unitario*quantidade) AS total FROM pedidos WHERE comanda = ? AND ordem = ? AND dia = ? AND pedido != ?', fcomanda, ordem,dia, 'Comanda Aberta')
            preco_total = 0
            print('total_comanda', total_comanda)
            if total_comanda and total_comanda[0]['total']:
                
                print(total_comanda)
                preco_total = float(total_comanda[0]['total'])
            

                dados = db.execute('''
                    SELECT pedido,id,ordem,nome,extra,opcoes, SUM(quantidade) AS quantidade, SUM(quantidade_paga) as quantidade_paga, SUM(preco) AS preco
                    FROM pedidos WHERE comanda =? AND ordem = ? AND dia = ? GROUP BY pedido, preco_unitario
                ''', fcomanda, ordem,dia)
                nomes = db.execute(
                    'SELECT nome FROM pedidos WHERE comanda = ? AND ordem = ? AND nome != ? AND dia = ? AND pedido != ? GROUP BY nome', fcomanda, ordem, '-1',dia, 'Comanda Aberta')
                if not nomes or not nomes[0]['nome']:
                    nomes = []
                preco_a_pagar = preco_total-preco_pago
                socketio.emit('preco', {'preco_a_pagar': preco_a_pagar, 'preco_total': preco_total, 'preco_pago': preco_pago,
                               'dados': dados, 'comanda': fcomanda, 'nomes': nomes})
            else:
                print('primeiro else')
                socketio.emit('preco', {'preco_a_pagar': '', 'preco_total': '', 'preco_pago': '', 'dados': [], 'nomes': [],
                               'comanda': fcomanda})
        else:
            print('segundo else')
            dados = db.execute('''
                    SELECT pedido,id,ordem,nome,extra,opcoes, SUM(quantidade) AS quantidade, SUM(quantidade_paga) as quantidade_paga, SUM(preco) AS preco
                    FROM pedidos WHERE comanda =? AND ordem = ? AND dia = ? GROUP BY pedido, preco_unitario
                ''', fcomanda, ordem,dia)
            socketio.emit('preco', {'preco_a_pagar': '', 'preco_total': '', 'preco_pago': '', 'dados': dados, 'nomes': '',
                           'comanda': fcomanda})


    except Exception as e:
        print("Erro ao calcular preço:", e)




@socketio.on('permitir')
def permitir(data):
    id = data.get('id')
    # Corrigido para buscar 'numero', que está vindo do frontend
    numero = data.get('numero')
    db.execute('UPDATE usuarios SET liberado = ? WHERE id = ?',
               numero, id)  # Atualiza a coluna 'liberado'
    users(True)



@socketio.on('Delete_user')
def delete_user(data):
    id = data.get('id')
    db.execute('DELETE FROM usuarios WHERE id = ?',id)
    users(True)

@socketio.on('cadastrar')
def cadastro(data):
    print('entrou')
    username = data.get('username')
    cargo = data.get('cargo')
    print(username)
    senha = data.get('senha')
    print(senha)
    db.execute('INSERT INTO usuarios (username,senha,cargo,liberado) VALUES (?,?,?,?)',
               username, senha, cargo, '1')
    print('sucesso'
          )
    users(True)

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

def _sync_opcoes_rows(id_cardapio: int, item_nome: str, grupos: list):
    """Limpa e re-insere as linhas em `opcoes` para este cardápio."""
    db.execute("DELETE FROM opcoes WHERE id_cardapio = ?", id_cardapio)
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
                  (id_cardapio, item, nome_grupo, opcao, valor_extra, esgotado_bool, grupo_slug, opcao_slug, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                id_cardapio, item_nome, gname, oname, extra, esgotado, gslug, oslug, now
            )


@socketio.on('adicionarCardapio')
def adicionarCardapio(data):
    item = (data.get('item') or '').strip()
    preco = data.get('preco')
    categoria = data.get('categoria')
    usuario = data.get('username')
    token_user = data.get('token')

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
        'INSERT INTO cardapio (item, categoria_id, preco, opcoes) VALUES (?,?,?,?)',
        item, categoria_id, float(preco), opcoes_json
    )
    # SQLite: id da última inserção na mesma conexão
    new_id = db.execute("SELECT last_insert_rowid() AS id")[0]["id"]

    # sincroniza linhas da tabela `opcoes`
    _sync_opcoes_rows(new_id, item, grupos)

    alteracoes = f'item: {item} preco: {preco} categoria: {categoria} (com opcoes)'
    insertAlteracoesTable('Cardapio', alteracoes, 'Adicionou', 'Tela Cardapio', usuario)
    enviar_notificacao_expo('ADM', 'Item Adicionado Cardapio', f"{usuario} Adicionou {alteracoes}", token_user)
    getCardapio(True)






@socketio.on('editarCardapio')
def editarCardapio(data):
    item = (data.get('item') or '').strip()
    preco = data.get('preco')
    categoria = data.get('categoria')
    novoNome = (data.get('novoNome') or '').strip()
    raw_opcoes = data.get('opcoes')

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
    dadoAntigo = db.execute('SELECT * FROM cardapio WHERE item = ?', item)
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
            "UPDATE cardapio SET item = ?, preco = ?, categoria_id = ?, opcoes = ? WHERE item = ?",
            novoNome, float(preco), categoria_id, opcoes_json, item
        )
    elif opcoes_json is not None:
        db.execute(
            "UPDATE cardapio SET preco = ?, categoria_id = ?, opcoes = ? WHERE item = ?",
            float(preco), categoria_id, opcoes_json, item
        )
    elif novoNome:
        db.execute(
            "UPDATE cardapio SET item = ?, preco = ?, categoria_id = ? WHERE item = ?",
            novoNome, float(preco), categoria_id, item
        )
    else:
        db.execute(
            "UPDATE cardapio SET preco = ?, categoria_id = ? WHERE item = ?",
            float(preco), categoria_id, item
        )

    # chave atual para buscar id
    chaveBusca = novoNome if novoNome else item
    dadoAtualizado = db.execute('SELECT * FROM cardapio WHERE item = ? ORDER BY id DESC LIMIT 1', chaveBusca)
    dadoAtualizado = dadoAtualizado[0] if dadoAtualizado else {}

    # sincroniza tabela `opcoes`
    if dadoAtualizado:
        id_cardapio = dadoAtualizado.get("id")
        if grupos is not None:
            _sync_opcoes_rows(id_cardapio, chaveBusca, grupos)
        elif novoNome:
            # só renomeou item — reflita em `opcoes.item`
            db.execute("UPDATE opcoes SET item = ? WHERE id_cardapio = ?", chaveBusca, id_cardapio)

    # log diffs
    alteracoes = f'{item}, '
    dif = {k for k in (dadoAtualizado.keys() & dadoAntigo.keys())
           if dadoAtualizado[k] != dadoAntigo.get(k)}
    for key in dif:
        alteracoes += f'{key} de {dadoAntigo.get(key)} para {dadoAtualizado.get(key)} '

    insertAlteracoesTable('Cardapio', alteracoes, 'Editou', 'Tela Cardapio', usuario)
    enviar_notificacao_expo('ADM', 'Cardapio editado', f"{usuario} Editou {alteracoes}", token_user)
    getCardapio(True)


  

@socketio.on('removerCardapio')
def removerCardapio(data):
    item=data.get('item')
    usuario = data.get('username')
    token_user = data.get('token')
    print("Removendo item:", item)
    db.execute("DELETE FROM cardapio WHERE item=?",item)

    insertAlteracoesTable('Cardapio',item,'Removeu','Tela Cardapio',usuario)
    enviar_notificacao_expo('ADM','Item Removido Cardapio',f"{usuario} Removeu {item} do Cardapio",token_user)
    getCardapio(True)
    


@socketio.on('getItemCardapio')
def getItemCardapio(data):
    item = data.get('item')
    print(item) 
    opcoes = db.execute('SELECT opcoes FROM cardapio WHERE item = ?', item)
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

def insertAlteracoesTable(tabela,alteracao,tipo,tela,usuario):
    hoje = datetime.now(brazil).date()
    horario = datetime.now(pytz.timezone(
        "America/Sao_Paulo")).strftime('%H:%M')
    print(tabela,alteracao,tipo,usuario)
    db.execute('INSERT INTO alteracoes (tabela,alteracao,tipo,usuario,tela,dia,horario) VALUES (?,?,?,?,?,?,?)',tabela,alteracao,tipo,usuario,tela,hoje,horario)
    getAlteracoes(True)

@socketio.on('getAlteracoes')
def getAlteracoes(emitir):
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

    data=db.execute("SELECT * FROM alteracoes WHERE dia = ?",hoje)
    emit('respostaAlteracoes', {"alteracoes":data,"hoje":str(dia_mes)}, broadcast=emiti)

@socketio.on('faturamento_range')
def faturamento_range(data):
    print('Fsturamento rangeeeeeeeeeeeeeeee')
    # --------- Entrada / defaults ---------
    date_from = (data or {}).get('date_from') or (data or {}).get('start')
    date_to   = (data or {}).get('date_to')   or (data or {}).get('end')
    emitir    = bool((data or {}).get('emitir', False))

    if not date_from or not date_to:
        emit('faturamento_enviar', {
            'dia': 'Período inválido',
            'faturamento': 0, 'faturamento_previsto': 0,
            'drink': 0, 'porcao': 0, 'restante': 0, 'pedidos': 0,
            'caixinha': 0, 'dezporcento': 0, 'desconto': 0,
            'pix': 0, 'debito': 0, 'credito': 0, 'dinheiro': 0
        }, broadcast=False)
        return

    # Garante formato AAAA-MM-DD e troca se vier invertido
    # (assume que 'dia' na sua tabela está em TEXT 'YYYY-MM-DD' ou DATE)
    try:
        df = datetime.strptime(date_from, '%Y-%m-%d').date()
        dt = datetime.strptime(date_to,   '%Y-%m-%d').date()
    except ValueError:
        emit('faturamento_enviar', {
            'dia': 'Formato de data inválido (use YYYY-MM-DD)',
            'faturamento': 0, 'faturamento_previsto': 0,
            'drink': 0, 'porcao': 0, 'restante': 0, 'pedidos': 0,
            'caixinha': 0, 'dezporcento': 0, 'desconto': 0,
            'pix': 0, 'debito': 0, 'credito': 0, 'dinheiro': 0
        }, broadcast=False)
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
        WHERE dia BETWEEN ? AND ?
        GROUP BY forma_de_pagamento
    """, date_from, date_to)

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
    caixinha = db.execute("SELECT COALESCE(SUM(caixinha),0) AS total_caixinha FROM pagamentos WHERE dia BETWEEN ? AND ?", date_from, date_to)
    caixinha = caixinha[0]['total_caixinha'] or 0
    dezporcento = db.execute("SELECT COALESCE(SUM(dez_por_cento),0) AS total_dezporcento FROM pagamentos WHERE dia BETWEEN ? AND ? ",date_from,date_to)
    dezporcento = dezporcento[0]['total_dezporcento'] or 0
    desconto = db.execute("SELECT SUM(valor) AS total_desconto FROM pagamentos WHERE dia = BETWEEM ? AND ? AND tipo = ?",date_from,date_to ,'desconto')
    desconto = desconto[0]['total_desconto'] or 0

    # Faturamento real = tudo que entrou - descontos
    total_recebimentos = db.execute(""" SELECT SUM(valor_total) AS total_recebimentos FROM pagamentos WHERE tipo =? dia BETWEEN ? AND ? """, 'normal',date_from, date_to)
    total_recebimentos = total_recebimentos[0]['total_recebimentos'] or 0
    # --------- Agregações em PEDIDOS ---------
    # Mantive sua lógica de categorias (1=restante, 2=drink, 3=porção)
    pedidosQuantDict = db.execute("""
        SELECT categoria,
               SUM(quantidade) AS quantidade_total,
               SUM(preco_unitario*NULLIF(quantidade,0))      AS preco_total
        FROM pedidos
        WHERE dia BETWEEN ? AND ?
          AND pedido != ?
        GROUP BY categoria
        ORDER BY categoria ASC
    """, date_from, date_to, 'Comanda Aberta')
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
    print(f'Faturamento de {periodo_fmt}: R$ {faturamento:.2f} (previsto R$ {faturamento_previsto:.2f})')
    print(f'  Pedidos: {pedidos} (drink {drink}, porção {porcao}, restante {restante})')
    print(f'  Recebimentos: R$ {total_recebimentos:.2f} (pix R$ {pix:.2f}, débito R$ {debito:.2f}, crédito R$ {credito:.2f}, dinheiro R$ {dinheiro:.2f})')
    print(f'  Caixinha R$ {caixinha:.2f}, 10% R$ {dezporcento:.2f}, Descontos R$ {desconto:.2f}')
    print(f'  (emitir={emitir})')
    # ------------------------------------------
    # --------- Emite no MESMO formato do 'faturamento' ---------
    vendas_user = []
    vendas_user =db.execute('SELECT username, SUM(preco_unitario*NULLIF(quantidade,0)) AS valor_vendido, SUM(quantidade)  AS quant_vendida FROM pedidos WHERE dia BETWEEN ? AND ? AND pedido!= ? GROUP BY username ORDER BY SUM(preco_unitario*NULLIF(quantidade,0)) DESC',date_from,date_to,'Comanda Aberta')
    print('vendas_user', vendas_user)

    emit('faturamento_enviar', {
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
    }, broadcast=emitir)


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
    ids_quant = []
    dia = datetime.now(brazil).date()
    preco = 0
    for row in itens:
        quantidade = float(row.get('quantidade'))
        item = row.get('pedido')
        ids = db.execute('SELECT id,quantidade,quantidade_paga,preco_unitario FROM pedidos WHERE pedido = ? AND comanda = ? AND ordem = ? AND dia = ?',item,comanda,0,dia)
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
                ''', quantidade, quantidade, comanda, id_usar, 0, dia)

            if preco_dict:
                preco += float(preco_dict)*quantidade
                ids_quant.append({'id': id_usar, 'quantidade': quantidade})

    if ids:
        dez_por_cento = 0 if not aplicarDez else (preco * 0.1)
        db.execute('INSERT INTO pagamentos (valor,valor_total,caixinha,dez_por_cento,tipo,ordem,dia,forma_de_pagamento,comanda,horario,ids) VALUES (?,?,?,?,?,?,?,?,?,?,?)',preco,preco+caixinha+dez_por_cento,caixinha,dez_por_cento,'normal',0,dia,forma_de_pagamento,comanda,datetime.now(brazil).strftime('%H:%M'),json.dumps(ids_quant))
        faturamento(True)
    totalComandaDict = db.execute('SELECT SUM(preco_unitario*NULLIF(quantidade,0)) AS total FROM pedidos WHERE comanda = ? AND ordem = ? AND dia = ?', comanda, 0,dia)
    valorTotalDict = db.execute('SELECT SUM(valor) as total FROM pagamentos WHERE dia = ? AND comanda = ? AND ordem = ? AND tipo = ?',dia,comanda,1,'normal')
    if totalComandaDict and valorTotalDict:
        totalComanda = float(totalComandaDict[0]['total']) if totalComandaDict[0]['total'] else 0
        valorTotal = float(valorTotalDict[0]['total']) if valorTotalDict[0]['total'] else 0
        if totalComanda <= valorTotal:
            handle_delete_comanda(comanda)

    handle_get_cardapio(comanda)


@socketio.on('buscar_menu_data')
def buscar_menu_data(emitir_broadcast):
    try:
        print('entrou buscar menu data')

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

        emit('menuData', data_geral_atualizado, broadcast=emitir_broadcast)

    except Exception as e:
        print('erro ao buscar_menu_data:', e)

@socketio.on('enviar_pedido_on_qr')
def enviar_pedido_on_qr(data,comanda,token):
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
        db.execute('''INSERT INTO pedidos (comanda,pedido,quantidade,extra,preco,preco_unitario,categoria,inicio,estado,nome,ordem,dia,username,opcoes,remetente)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',comanda,pedido,quantidade,obs, preco,preco_unitario,categoria_id,hora_min,'A Fazer','-1',0,dia,f'Cliente:{user_number}',json.dumps(options),'Carrinho:NossoPoint')



@socketio.on('savePromotion')
def savePromotion(data):
    print('entrou savePromotion')
    try:
        promotionData = data.get('promotionData')
        tipo = data.get('type')
        emitirBroadcast = data.get('emitirBroadcast', True)

        status = 'active' if promotionData['endDate'] > datetime.now(brazil).date().strftime('%Y-%m-%d') else 'expired'

        if tipo == 'create':
            db.execute('INSERT INTO promotions (name, products, type, value, endDate,status) VALUES (?,?,?,?,?,?)',promotionData['name'],json.dumps(promotionData['products']),promotionData['type'],float(promotionData['value']),promotionData['endDate'],status)
        elif tipo == 'update':
            db.execute('UPDATE promotions SET name = ?, products = ?, type = ?, value = ?, endDate = ?, status = ? WHERE id = ?',promotionData['name'],json.dumps(promotionData['products']),promotionData['type'],float(promotionData['value']),promotionData['endDate'],status,int(promotionData['id']))
        getPromotions(emitirBroadcast)
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
        getCardapio(True)


    except Exception as e:
        print('erro ao salvar promoção:', e)

@socketio.on('getPromotions')
def getPromotions(emitirBroadcast):
    print('entrou getPromotions')
    dados = db.execute('SELECT * FROM promotions')
    emit('promotionsData',dados,broadcast=emitirBroadcast)


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
    try:
        limit = int(request.args.get("limit") or 100)
    except Exception:
        limit = 100
    limit = max(1, min(limit, 500))

    # Filtros dinâmicos (base)
    wh = ["1=1"]
    base_params = {}

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
    wh = ["grupo_slug = :gs", "opcao_slug = :os"]
    params = {"gs": gslug, "os": oslug}

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
        **params
    ) or []
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
            INSERT INTO opcoes_audit (actor, where_json, set_json, dry_run, matched, updated, items_json)
            VALUES (:actor, :w, :s, 0, :m, :u, :items)
            """,
            actor=actor,
            w=json.dumps({"grupo_slug": gslug, "opcao_slug": oslug}, ensure_ascii=False),
            s=json.dumps(set_fields, ensure_ascii=False),
            m=matched,
            u=updated,
            items=json.dumps(items)
        )
        getCardapio(True)  # broadcast atualização do cardápio
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

def _build_opcoes_json_from_table(item_id: int) -> str:
    """
    Monta a estrutura JSON de grupos/opções para um item
    a partir da tabela opcoes (campos: nome_grupo, opcao, valor_extra, esgotado_bool),
    preservando ids/max_selected/obrigatorio do JSON atual.
    """
    rows = db.execute("""
        SELECT nome_grupo, grupo_slug, opcao, valor_extra, esgotado_bool
        FROM opcoes
        WHERE id_cardapio = :id
        ORDER BY nome_grupo, opcao
    """, id=item_id) or []

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
            new_json = _build_opcoes_json_from_table(iid)
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
    wh = ["grupo_slug = :gs"]
    params = {"gs": gslug}

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
                "SELECT MIN(nome_grupo) AS nome FROM opcoes WHERE id_cardapio = :id AND grupo_slug = :gs",
                id=iid, gs=gslug
            )
            group_name = (gr[0]["nome"] if gr and gr[0]["nome"] else "").strip()
            if not group_name:
                # não deve ocorrer, pois o item veio da opcoes com esse grupo_slug
                continue

            # Reconstrói JSON a partir da tabela (garante que grupos/opções estejam atualizados)
            json_str = _build_opcoes_json_from_table(iid)
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
                db.execute("UPDATE cardapio SET opcoes = :j WHERE id = :id", j=new_str, id=iid)
                getCardapio(True)  # broadcast atualização do cardápio

        # Auditoria (reuso da tabela existente)
        actor = request.headers.get("X-User") or "api"
        audit_id = db.execute(
            """
            INSERT INTO opcoes_audit (actor, where_json, set_json, dry_run, matched, updated, items_json)
            VALUES (:actor, :w, :s, 0, :m, :u, :items)
            """,
            actor=actor,
            w=json.dumps({"grupo_slug": gslug, "type": "group_props"}, ensure_ascii=False),
            s=json.dumps(set_fields, ensure_ascii=False),
            m=matched,
            u=matched,
            items=json.dumps(items)
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

# ====== HELPERS ======
def strip_accents_upper(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    return s.upper()

def sanitize_txid(s: str) -> str:
    # Especificação permite [a-zA-Z0-9]{1,25}
    s = re.sub(r"[^A-Za-z0-9]", "", s or "")
    return s[:25] or "TXID"

def emv(k: str, v: str) -> str:
    vb = v.encode("utf-8")
    return f"{k}{len(vb):02d}{v}"

def crc16(payload: str) -> str:
    # CRC16-CCITT (0x1021)
    polynomial = 0x1021
    result = 0xFFFF
    for ch in payload.encode("utf-8"):
        result ^= ch << 8
        for _ in range(8):
            if (result & 0x8000) != 0:
                result = (result << 1) ^ polynomial
            else:
                result <<= 1
            result &= 0xFFFF
    return format(result, "04X")

def strip_accents_ascii(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    # mantém letras, números, espaço e alguns sinais básicos
    s = re.sub(r"[^A-Za-z0-9 \-_.]", "", s)
    return s

def up_to(s: str, n: int) -> str:
    return (s or "")[:n]

def bytes_len(s: str) -> int:
    return len((s or "").encode("utf-8"))

def build_pix_payload(key: str, nome: str, cidade: str, valor: float, txid: str, descricao: str = "") -> str:
    # normalizações
    nome = up_to(strip_accents_ascii(nome).upper(), 25) or "LOJA"
    cidade = up_to(strip_accents_ascii(cidade).upper(), 15) or "SAO PAULO"
    descricao = up_to(strip_accents_ascii(descricao), 40)
    valor_str = f"{float(valor):.2f}"

    # 00 e 01 (estático)
    pfi  = emv("00", "01")
    poim = emv("01", "11")  # <- trocado para 11

    # 26: BR Code Pix
    gui = emv("00", "BR.GOV.BCB.PIX")
    mai = gui + emv("01", key)
    if descricao:
        mai += emv("02", descricao)
    mai_full = emv("26", mai)

    # 52/53/54/58/59/60
    mcc           = emv("52", "0000")
    currency      = emv("53", "986")
    amount        = emv("54", valor_str)
    country       = emv("58", "BR")
    merchant_name = emv("59", nome)
    merchant_city = emv("60", cidade)

    # 62: TXID
    add      = emv("05", txid[:25])
    add_full = emv("62", add)

    # 63: CRC
    partial = pfi + poim + mai_full + mcc + currency + amount + country + merchant_name + merchant_city + add_full + "6304"
    crc = crc16(partial + "0000")
    return partial + crc

def make_qr_png_base64(data: str) -> str:
    qr = qrcode.QRCode(
        version=None,  # ajusta automaticamente
        error_correction=ERROR_CORRECT_Q,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


def normalize_pix_key(key: str) -> str:
    k = (key or "").strip()
    # ajuste pelo tipo que você usa de verdade:
    # CPF:
    return re.sub(r"\D", "", k)
#====== ROUTE ======
@app.post("/pix/qr")
def gerar_qr():
    """
    Espera JSON:
    {
      "pedido_id": "WEBABC123",
      "valor": "49.90" (ou numero),
      "descricao": "Pedido WEBABC123" (opcional)
    }
    Retorna:
    {
      "txid": "...",
      "payload": "<brcode copia e cola>",
      "qr_png_base64": "data:image/png;base64,..."
    }
    """
    try:
        data = request.get_json(force=True, silent=False) or {}
        pedido_id = str(data.get("pedido_id") or "").strip()
        descricao = str(data.get("descricao") or "")[:40]

        if "valor" not in data:
            return jsonify({"error": "Campo 'valor' é obrigatório."}), 400

        try:
            valor = float(str(data.get("valor")).replace(",", "."))
        except (TypeError, ValueError):
            return jsonify({"error": "Valor inválido."}), 400

        if valor <= 0:
            return jsonify({"error": "Valor deve ser maior que zero."}), 400

        txid = sanitize_txid(f"{TXID_PREFIX}{pedido_id}")

        key_norm = normalize_pix_key(PIX_KEY)
        
        payload = build_pix_payload(
            key=PIX_KEY,
            nome=MERCHANT_NAME,
            cidade=MERCHANT_CITY,
            valor=valor,
            txid=txid,
            descricao=descricao,
        )

        print("TOTAL BYTES do payload:", bytes_len(payload))

        qr_b64 = make_qr_png_base64(payload)

        return jsonify({
            "txid": txid,
            "payload": payload,          # Pix Copia e Cola
            "qr_png_base64": qr_b64,      # imagem do QR para exibir/baixar
            "debug_key_used": key_norm
        })
    except Exception as e:
        # logue e trate como preferir
        return jsonify({"error": f"Falha ao gerar Pix: {str(e)}"}), 500




if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))

    socketio.run(app, host='0.0.0.0', port=port, debug=True)

