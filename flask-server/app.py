from flask import send_from_directory
import atexit
import base64
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

SECRET_KEY = "minha_chave_super_secreta"

load_dotenv()
ACCOUNT_SID = os.getenv("ACCOUNT_SID_TWILIO")
AUTH_TOKEN  = os.getenv("AUTH_TOKEN_TWILIO")
VERIFY_SID  = os.getenv("VERIFY_SID") 

client = Client(ACCOUNT_SID, AUTH_TOKEN)

CORS(
    app,
    resources={r"/*": {"origins": '*'}},
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.route("/auth/sms/create", methods=["POST"])
def send_verification():
    print('creatingsms')
    phone = request.json.get("phone")
    v = client.verify.v2.services(VERIFY_SID).verifications.create(to=phone, channel="sms")
    print(v)
    return jsonify({"status": v.status}), 200

@app.route("/auth/sms/check", methods=["POST"])
def check_verification():
    print('verification')
    phone = request.json.get("phone")
    code = request.json.get("code")
    chk = client.verify.v2.services(VERIFY_SID).verification_checks.create(to=phone, code=code)
    print(chk)
    return jsonify({"status": chk.status})  # 'approved' se ok

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

@app.route('/guardar_login', methods=['POST'])
def guardar_login():
    print('entrou guardar login')
    data = request.get_json(silent=True) or {}
    number = data.get('numero')

    if not number:
        return jsonify({"error": "Campo 'number' é obrigatório."}), 400

    # Busca 1 usuário; evite depender de != 'bloqueado' no WHERE para mensagens claras
    rows = db.execute(
        'SELECT numero, nome, status FROM clientes WHERE numero = ? LIMIT 1',
        number
    )

    if not rows:
        db.execute('INSERT INTO clientes (numero,nome,status) VALUES (?,?,?)',number,f'nome:{number}','aprovado')
        rows = [{'numero':number,'nome':f'nome:{number}','status':'aprovado'}]

    user = rows[0]
    if user.get('status') == 'bloqueado':
        return jsonify({"error": "Usuário bloqueado."}), 403

    payload = {
        "sub": str(user["numero"]),             # subject do token (id/numero)
        "name": user["nome"],
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    # PyJWT v2 já retorna str; se for bytes em versões antigas: token = token.decode()

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
    
     



@socketio.on('insert_order')
def handle_insert_order(data):
    try:
        dia = datetime.now(brazil).date()

        comanda = data.get('comanda')
        pedidos = data.get('pedidosSelecionados')
        quantidades = data.get('quantidadeSelecionada')
        horario = data.get('horario')
        username = data.get('username')
        preco = data.get('preco')
        nomes = data.get('nomeSelecionado')
        token_user=data.get('token_user')
        opcoesSelecionadas = data.get('opcoesSelecionadas')
        print(f"opcoesSelecionadas = {opcoesSelecionadas}")
        valorExtra = []
        if opcoesSelecionadas:
            extraSelecionados = data.get('extraSelecionados')
            extra = []

            for j in range(len(extraSelecionados)):
                extras = ''
                print(extraSelecionados)

                # Verifica se todas as opções selecionadas são listas
                if all(isinstance(item, list) for item in opcoesSelecionadas):
                    print('multiplo')
                    chave = ' '.join(opcoesSelecionadas[j])
                    for i in opcoesSelecionadas[j]:
                        if '+' in i:
                            # Separa o item e o preço extra
                            item, precoExtra = i.split('+')
                            precoExtra = int(precoExtra)

                            # Atualiza ou adiciona o preço extra na lista
                            estava = False

                            for key in valorExtra:
                                if pedidos[j]+chave in key:
                                    precoAntigo = key[pedidos[j] +
                                                      chave]
                                    key[pedidos[j]+chave
                                        ] = precoAntigo + precoExtra
                                    estava = True
                                    break

                            if not estava:
                                valorExtra.append(
                                    {pedidos[j]+chave: precoExtra})
                        else:
                            item = i

                        extras += f'{item} '
                else:
                    print('solo')
                    chave = ' '.join(opcoesSelecionadas)
                    for i in opcoesSelecionadas:
                        if '+' in i:
                            item, precoExtra = i.split('+')
                            precoExtra = int(precoExtra)

                            estava = False

                            for key in valorExtra:
                                if pedidos[j]+chave in key:
                                    precoAntigo = key[pedidos[j]+chave]
                                    key[pedidos[j]+chave] = precoAntigo + \
                                        precoExtra
                                    estava = True
                                    break

                            if not estava:
                                valorExtra.append(
                                    {pedidos[j]+chave: precoExtra})
                        else:
                            item = i

                        extras += f'{item} '

                # Adiciona extraSelecionados[j] ao final
                extras += extraSelecionados[j]
                print(extras)
                extra.append(extras)

        else:
            extra = data.get('extraSelecionados')
        print(f'Valor extra: {valorExtra}')
        print(username)
        print(comanda)
        print(pedidos)
        print(quantidades)
        print(horario)
        print(nomes)
        if not nomes:
            nomes = []
            for i in range(len(pedidos)):
                nomes.append('-1')
        for i in range(len(pedidos)):
            pedido = pedidos[i]

            quantidade = quantidades[i]
            preco_unitario = db.execute(
                'SELECT preco,categoria_id FROM cardapio WHERE item = ?', pedido)
            if preco_unitario:
                categoria = preco_unitario[0]['categoria_id']
                if comanda != 'controle de estoque':
                    preco_individual = preco_unitario[0]['preco']
                else:
                    preco_individual = 0
            else:
                categoria = 4
                print('else')
        
            if not extra[i]:
                extra[i] = ""
            else:
                extra[i] = extra[i].strip() + ' '
            
            if not nomes[i]:
                nomes[i] = "-1"
            
            print("extra", extra)
            estava = 'a'
            if categoria==3:
                enviar_notificacao_expo('Cozinha','Novo Pedido',f'{quantidade} {pedido} {extra[i]}na {comanda}',token_user)
            elif categoria==2:
                enviar_notificacao_expo('Colaborador','Novo Pedido',f'{quantidade} {pedido} {extra[i]}na {comanda}',token_user)
            
            if preco:
                print('brinde')
                db.execute('INSERT INTO pedidos(comanda, pedido, quantidade,preco,categoria,inicio,estado,extra,username,ordem,nome,dia) VALUES (?, ?, ?,?,?,?,?,?,?,?,?,?)',
                           comanda, pedido, float(quantidade), 0, categoria, horario, 'A Fazer', extra[i], username, 0, nomes[i],dia)
                
            elif not preco_unitario:
                db.execute('INSERT INTO pedidos(comanda, pedido, quantidade,preco,categoria,inicio,estado,extra,username,ordem,nome,dia) VALUES (?, ?, ?,?,?,?,?,?,?,?,?,?)',
                           comanda, pedido, float(quantidade), 0, 4, horario, 'A Fazer', extra[i], username, 0, nomes[i],dia)
                
            elif not valorExtra:
                db.execute('INSERT INTO pedidos(comanda, pedido, quantidade,preco,preco_unitario,categoria,inicio,estado,extra,username,ordem,nome,dia) VALUES (?, ?, ?,?,?,?,?,?,?,?,?,?,?)',
                           comanda, pedido, float(quantidade), float(preco_individual)*float(quantidade),float(preco_individual), categoria, horario, 'A Fazer', extra[i], username, 0, nomes[i],dia)
               
            else:
                brek = False
                contV = -1
                for item in valorExtra:
                    contV += 1
                    if brek:
                        break
                    for cont in range(len(opcoesSelecionadas)):
                        if all(isinstance(ass, list) for ass in opcoesSelecionadas):
                            chave = pedido+' '.join(opcoesSelecionadas[cont])
                        else:
                            chave = pedido+' '.join(opcoesSelecionadas)
                        if chave in item:
                            valor_inserido = float(
                                item[chave]) * float(quantidade)
                            print(
                                f'Inserindo valor {valor_inserido} no pedido {pedido}')
                            db.execute('INSERT INTO pedidos(comanda, pedido, quantidade,preco,preco_unitario,categoria,inicio,estado,extra,username,ordem,nome,dia) VALUES (?, ?, ?,?,?,?,?,?,?,?,?,?,?)',
                                       comanda, pedido, float(quantidade), (float(preco_individual)*float(quantidade))+valor_inserido,float(preco_individual)+valor_inserido, categoria, horario, 'A Fazer', extra[i], username, 0, nomes[i],dia)
                            estava = 'b'
                            del (valorExtra[contV])
                            brek = True
                            break
                    if estava == 'a':
                        db.execute('INSERT INTO pedidos(comanda, pedido, quantidade,preco,preco_unitario,categoria,inicio,estado,extra,username,ordem,nome,dia) VALUES (?, ?, ?,?,?,?,?,?,?,?,?,?,?)',
                                   comanda, pedido, float(quantidade), float(preco_unitario[0]['preco'])*float(quantidade),float(preco_individual), categoria, horario, 'A Fazer', extra[i], username, 0, nomes[i],dia)
            
            if categoria==1:
                id = db.execute("SELECT last_insert_rowid() AS id")[0]['id']
                hora = datetime.now(brazil).strftime('%H:%M')
                emit('emitir_pedido_restante',{'mesa':comanda,'pedido':pedido,'quantidade':quantidade,'extra':extra[i],'hora':hora,'sendBy':username, 'id':id},broadcast=True)
            
            quantidade_anterior = db.execute(
                'SELECT quantidade FROM estoque WHERE item = ?', pedido)
            dados_pedido = db.execute('SELECT * FROM pedidos WHERE dia = ? AND pedido != ?',dia, 'Comanda Aberta')
            if quantidade_anterior:
                quantidade_nova = float(
                    quantidade_anterior[0]['quantidade']) - quantidade
                db.execute(
                    'UPDATE estoque SET quantidade = ? WHERE item = ?', quantidade_nova, pedido)
                if quantidade_nova < 10:
                    emit('alerta_restantes', {
                         'quantidade': quantidade_nova, 'item': pedido}, broadcast=True)
                getEstoque(True)            
                
            
        faturamento(True)
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
    metodosDict=db.execute("SELECT forma_de_pagamento,SUM(valor) AS valor_total FROM pagamentos WHERE dia =? GROUP BY forma_de_pagamento",dia)
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
    faturamentoDict = db.execute('SELECT SUM(valor) AS valor_total,tipo FROM pagamentos WHERE dia = ? GROUP BY tipo',dia)
    caixinha = 0
    dezporcento = 0
    faturamento = 0
    desconto = 0
    for row in faturamentoDict:
        if row['tipo']=='caixinha':
            caixinha += row['valor_total']
        elif row['tipo']=='10%':
            dezporcento += row['valor_total']
        elif row['tipo']=='desconto' :
            desconto += row['valor_total']
        faturamento += row['valor_total']
        faturamento -=desconto
        
    
    
    pedidosQuantDict = db.execute("""
        SELECT categoria,
               SUM(quantidade) AS quantidade_total,
               SUM(preco)      AS preco_total
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
    vendas_user =db.execute('SELECT username, SUM(preco) AS valor_vendido, SUM(quantidade)  AS quant_vendida FROM pedidos WHERE dia = ? GROUP BY username ORDER BY SUM(preco) DESC',dia)
    print('vendas_user', vendas_user)

    emit('faturamento_enviar', {'dia': str(dia_formatado),
                                'faturamento': faturamento,
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
        
    db.execute('INSERT INTO pagamentos(valor,comanda,ordem,tipo,dia) VALUES (?,?,?,?,?)',valor,comanda,0,tipo,dia)
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
                    SELECT pedido,id,ordem,nome,extra, SUM(quantidade) AS quantidade, SUM(quantidade_paga) as quantidade_paga, SUM(preco) AS preco
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
                    SELECT pedido,id,ordem,nome,extra, SUM(quantidade) AS quantidade, SUM(quantidade_paga) as quantidade_paga, SUM(preco) AS preco
                    FROM pedidos WHERE comanda =? AND ordem = ? AND dia = ? GROUP BY pedido, preco_unitario
                ''', fcomanda, ordem,dia)
            socketio.emit('preco', {'preco_a_pagar': '', 'preco_total': '', 'preco_pago': '', 'dados': dados, 'nomes': '',
                           'comanda': fcomanda})
        getPedidos(True)
        getComandas(True)


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


@socketio.on('adicionarCardapio')
def adicionarCardapio(data):
    print(data.get('opcoes'))
    item = data.get('item')
    preco = data.get('preco')
    categoria = data.get('categoria')
    usuario = data.get('username')
    token_user = data.get('token')

    if not item or not preco or not categoria:
        emit('Erro', {'erro': 'Alguma categoria faltando'})
        return

    alteracoes = f'item: {item} preco: {preco} categoria: {categoria}'

    if categoria != 'Restante':
        opcoes = data.get('opcoes') or []  # garante lista
        if categoria == 'Bebida':
            categoria_id = 2
        elif categoria == 'Porção':
            categoria_id = 3
        else:
            categoria_id = 1  # fallback

        opcoesFormatadas = ''
        if opcoes:  # só monta se tiver algo
            for row in opcoes:
                titulo = row.get('titulo') or ''
                conteudos = row.get('conteudo') or []
                opcoesFormatadas += titulo
                opcoesFormatadas += '(' + '-'.join([str(c) for c in conteudos if c]) + ')'

            alteracoes += f' opcoes {opcoesFormatadas}'

        db.execute(
            'INSERT INTO cardapio (item,categoria_id,preco,opcoes) VALUES (?,?,?,?)',
            item, categoria_id, float(preco), opcoesFormatadas
        )

    else:
        db.execute(
            'INSERT INTO cardapio (item,categoria_id,preco) VALUES (?,?,?)',
            item, 1, float(preco)
        )

    insertAlteracoesTable('Cardapio', alteracoes, 'Adicionou', 'Tela Cardapio', usuario)
    alteracoes = f"{usuario} Adicionou {alteracoes}"
    enviar_notificacao_expo('ADM', 'Item Adicionado Cardapio', alteracoes, token_user)
    getCardapio(True)




@socketio.on('editarCardapio')
def editarCardapio(data):
    item = data.get('item')
    preco = data.get('preco')
    categoria = data.get('categoria')
    novoNome = data.get('novoNome')
    opcoes = data.get('opcoes')
    usuario = data.get('username')
    token_user=data.get('token')
    
    
    


    if item and preco and categoria:
        alteracoes = f'{item}, '
        dadoAntigo = db.execute('SELECT * FROM cardapio WHERE item = ?',item)[0]
        if categoria == 'Restante':
            categoria_id = 1
        elif categoria =='Porção':
            categoria_id= 3
        elif categoria == 'Bebida':
            categoria_id = 2
        opcoesFormatadas = ''
        
        if opcoes:
            for row in opcoes:
                opcoesFormatadas+=row['titulo']
                print (opcoesFormatadas)
                opcoesFormatadas+='('
                for i in range(len(row['conteudo'])):
                    opcoesFormatadas+=row['conteudo'][i]
                    if i != len(row['conteudo'])-1:
                        opcoesFormatadas+='-'
                opcoesFormatadas+=')'
        if opcoesFormatadas and novoNome:
            db.execute("UPDATE cardapio SET item =?,preco=?,categoria_id=?,opcoes=? WHERE item = ?",novoNome,preco,categoria_id,opcoesFormatadas,item)
        elif opcoesFormatadas:
            db.execute("UPDATE cardapio SET preco=?,categoria_id=?,opcoes=? WHERE item = ?",preco,categoria_id,opcoesFormatadas,item)
        elif novoNome:
            db.execute("UPDATE cardapio SET item =?,preco=?,categoria_id=? WHERE item = ?",novoNome,preco,categoria_id,item)
        else:
            db.execute("UPDATE cardapio SET preco=?,categoria_id=? WHERE item = ?",preco,categoria_id,item)
        
        dadoAtualizado = db.execute('SELECT * FROM cardapio WHERE item = ?',novoNome)[0] if novoNome else db.execute('SELECT * FROM cardapio WHERE item = ?',item)[0]
        
        dif={k:(dadoAtualizado[k],dadoAntigo[k]) for k in dadoAtualizado.keys() & dadoAntigo.keys() if dadoAtualizado[k]!=dadoAntigo[k]}.keys()
        for key in dif:
            alteracoes+=f'{key} de {dadoAntigo[key]} para {dadoAtualizado[key]} '
        print(alteracoes)

        insertAlteracoesTable('Cardapio',alteracoes,'Editou','Tela Cardapio',usuario)
        alteracoes=f"{usuario} Editou {alteracoes}"
        enviar_notificacao_expo('ADM','Cardapio editado',alteracoes,token_user)
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
    tiposDict = db.execute("""
        SELECT tipo, SUM(valor) AS valor_total
        FROM pagamentos
        WHERE dia BETWEEN ? AND ?
        GROUP BY tipo
    """, date_from, date_to)

    caixinha = dezporcento = desconto = 0
    total_recebimentos = 0
    for row in tiposDict:
        tipo = row.get('tipo')
        val = row.get('valor_total') or 0
        total_recebimentos += val
        if tipo == 'caixinha':
            caixinha += val
        elif tipo == '10%':
            dezporcento += val
        elif tipo == 'desconto':
            desconto += val

    # Faturamento real = tudo que entrou - descontos
    faturamento = total_recebimentos - desconto

    # --------- Agregações em PEDIDOS ---------
    # Mantive sua lógica de categorias (1=restante, 2=drink, 3=porção)
    pedidosQuantDict = db.execute("""
        SELECT categoria,
               SUM(quantidade) AS quantidade_total,
               SUM(preco)      AS preco_total
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
    vendas_user =db.execute('SELECT username, SUM(preco) AS valor_vendido, SUM(quantidade)  AS quant_vendida FROM pedidos WHERE dia BETWEEN ? AND ? AND pedido!= ? GROUP BY username ORDER BY SUM(preco) DESC',date_from,date_to,'Comanda Aberta')
    print('vendas_user', vendas_user)

    emit('faturamento_enviar', {
        'dia': periodo_fmt,
        'faturamento': faturamento,
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
    totalComandaDict = db.execute('SELECT SUM(preco) AS total FROM pedidos WHERE comanda = ? AND ordem = ? AND dia = ?', comanda, 0,dia)
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
            SELECT id, item, preco, categoria_id, image, opcoes, subcategoria
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

            # --- Coalesce seguro para options_on_qr ---
            opcoes_str = row.get('opcoes')
            if opcoes_str is None:
                opcoes_str = ''
            elif not isinstance(opcoes_str, str):
                opcoes_str = str(opcoes_str)

            # pega "Titulo(conteudo)" sem ser guloso além do próximo ')'
            matches = re.findall(r'([A-Za-zÀ-ÿ\' ]+)\(([^)]*)\)', opcoes_str)

            options = {}
            for opt_key, conteudo in matches:
                itens = [i.strip() for i in conteudo.split('-') if i.strip()]
                options[opt_key.strip()] = itens

            data_geral_atualizado.append({
                'id': row['id'],
                'name': item_nome,
                'price': row.get('preco'),
                'categoria': categoria_item,
                'subCategoria': row.get('subcategoria','outros'),
                'image': row.get('image') or None,
                'options': options
            })

        emit('menuData', data_geral_atualizado, broadcast=emitir_broadcast)

    except Exception as e:
        print('erro ao buscar_menu_data:', e)

@socketio.on('enviar_pedido_on_qr')
def enviar_pedido_on_qr(data,comanda):
    print(f'enviar pedido on qr:\n {data}')
    print(f'comanda {comanda}')
    dia = datetime.now(brazil).date()
    for row in data:
        subcategoria = row.get('subcategoria')
        pedido_dict = db.execute('SELECT item FROM cardapio WHERE id = ?',row.get('id'))
        if pedido_dict:
            pedido = pedido_dict[0].get('item')
        preco = float(row.get('price'))
        categoria = row.get('categoria')
        quantidade = row.get('quantity')
        options = row.get('selectedOptions')
        obs = row.get('observations')
        extra = ''
        if categoria=='comida':
            if pedido not in ['amendoim', 'milho']:
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
        extra = None
        if options:
            extra = auxiliar_dicionario_para_string(options)
            if obs:
                extra = (extra + ", " + 'Obs: '+ obs).strip(", ")
        elif obs:
            extra = obs

        db.execute('''INSERT INTO pedidos (comanda,pedido,quantidade,extra,preco,categoria,inicio,estado,nome,ordem,dia)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)''',comanda,pedido,quantidade,extra, preco,categoria_id,hora_min,'A Fazer','-1',0,dia)


def auxiliar_dicionario_para_string(options):
    try:
        limpo = {}
        for k, v in options.items():
            if isinstance(v, str):
                val = re.sub(r'\+\d+(?:[.,]\d+)?$', '', v).replace('+', ' ').strip()
                limpo[k] = val
            elif isinstance(v, list):
                limpo[k] = [re.sub(r'\+\d+(?:[.,]\d+)?$', '', item).replace('+', ' ').strip() for item in v]
            else:
                limpo[k] = v

        parts = []
        for k, v in limpo.items():
            if isinstance(v, list):
                for item in v:
                    if item:
                        parts.append(f"{k}: {item}")
            else:
                if v:
                    parts.append(f"{k}: {v}")

        extra = ", ".join(parts)
        return extra
    except Exception as e:
        print('erro_auxiliar_dicionario_para_string:', e)

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




if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))

    socketio.run(app, host='0.0.0.0', port=port, debug=True)




























