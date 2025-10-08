# ===========================
# IFOOD - FLUXO COMPLETO
# ===========================
import os
from cs50 import SQL
import time
import hmac
import json
import queue
import hashlib
import threading
import dotenv
from typing import Any, Dict, Optional, List
import shutil

DATABASE_PATH = "/data/dados.db"
db = SQL("sqlite:///" + DATABASE_PATH)

import requests
from flask import request, jsonify
from datetime import datetime
try:
    import zoneinfo
    brazil = zoneinfo.ZoneInfo("America/Sao_Paulo")
except Exception:
    # fallback se faltar zoneinfo
    from datetime import timezone, timedelta
    brazil = timezone(timedelta(hours=-3))

# --------- ENV & TOKEN ----------
load_dotenv()
SEU_CLIENT_ID = os.getenv("SEU_CLIENT_ID")
SEU_CLIENT_SECRET = os.getenv("SEU_CLIENT_SECRET")
TOKEN_URL = os.getenv("TOKEN_URL")
WEBHOOK_SECRET = os.getenv("IFOOD_WEBHOOK_SECRET") or SEU_CLIENT_SECRET

_token_cache = {"accessToken": None, "expiresAt": 0.0}
_cache_lock = threading.Lock()

def get_ifood_token() -> tuple[str, float]:
    """
    Sempre retorna (access_token: str, expires_at: float).
    Renova 60s antes de expirar.
    """
    with _cache_lock:
        now = time.time()
        if _token_cache["accessToken"] and (_token_cache["expiresAt"] - now > 60):
            return _token_cache["accessToken"], _token_cache["expiresAt"]

        if not SEU_CLIENT_ID or not SEU_CLIENT_SECRET or not TOKEN_URL:
            raise RuntimeError("SEU_CLIENT_ID/SEU_CLIENT_SECRET/TOKEN_URL não configurados nas variáveis de ambiente.")

        data = {
            "grantType": "client_credentials",
            "clientId": SEU_CLIENT_ID,
            "clientSecret": SEU_CLIENT_SECRET,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
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

# --------- ASSINATURA HMAC ----------
def _valid_signature(req) -> bool:
    try:
        raw = req.get_data(cache=False)  # bytes exatos do corpo
        sent = req.headers.get("X-IFood-Signature", "")
        if not (raw and sent and WEBHOOK_SECRET):
            return False
        mac = hmac.new(WEBHOOK_SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
        return hmac.compare_digest(mac, sent)
    except Exception:
        return False

# --------- FILA / WORKER ----------
_event_q: "queue.SimpleQueue[dict]" = queue.SimpleQueue()

def _worker_loop():
    while True:
        evt = _event_q.get()
        try:
            _process_ifood_event(evt)
        except Exception as e:
            print("[webhook_ifood][worker] erro:", e)

# inicia worker background
threading.Thread(target=_worker_loop, daemon=True).start()

# --------- HELPERS DE TEMPO ----------
def parse_iso_br(dt_str: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Converte datetime ISO do iFood para data e hora separadas (em São Paulo)."""
    if not dt_str:
        return None, None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00")).astimezone(brazil)
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")
    except Exception:
        return None, None

# --------- PARSE DO PEDIDO ----------
def extrair_pedido_ifood(order: dict) -> dict:
    """
    Retorna informações essenciais do pedido iFood:
    - produtos, observações, complementos
    - totais
    - endereço (pode ser None em retirada)
    - horários (pedido e, se houver, agendamento)
    """
    total_block = order.get("total") or {}
    valor_sem_taxas = total_block.get("subTotal")
    valor_com_taxas = total_block.get("orderAmount")

    # Endereço (pode não existir em retirada)
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

    # Horários
    pedido_data, pedido_hora = parse_iso_br(order.get("createdAt"))
    agendamento_data, agendamento_hora = parse_iso_br(delivery.get("deliveryDateTime"))

    # Itens
    itens_extraidos: List[dict] = []
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

    return {
        "pedido_id": order.get("id"),
        "cliente_nome": (order.get("customer") or {}).get("name"),
        "produtos": itens_extraidos,
        "valor_sem_taxas": valor_sem_taxas,
        "valor_com_taxas": valor_com_taxas,
        "endereco": endereco,
        "pedido_data": pedido_data,
        "pedido_hora": pedido_hora,
        "orderTiming": order.get('orderTiming'),
        "agendamento_data": agendamento_data,
        "agendamento_hora": agendamento_hora,
    }

# --------- BUSCA DETALHES E INSERE NO DB ----------
def pedido_detalhes(order_id: str, access_token: Optional[str] = None):
    """Busca detalhes do pedido e insere no seu DB."""
    if not access_token:
        access_token, _ = get_ifood_token()

    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    url_order = f"https://merchant-api.ifood.com.br/order/v1.0/orders/{order_id}"
    resp = requests.get(url_order, headers=headers, timeout=20)
    resp.raise_for_status()
    order = resp.json()

    data = extrair_pedido_ifood(order)

    endereco_dict = data.get('endereco') or {}
    endereco = " ".join(
        s for s in [
            endereco_dict.get('rua'),
            str(endereco_dict.get('numero') or '').strip()
        ] if s
    ).strip() or "Retirada no balcão"

    # Insere item a item
    for row in data.get('produtos', []):
        extra = (row.get('observacoes') or '')
        for comp in row.get('complementos', []):
            extra += f"\n{comp.get('quantidade',1)} {comp.get('nome','')}"

        # Ajuste a query conforme seu schema/driver
        db.execute(
            'INSERT INTO pedidos (pedido,quantidade,preco,categoria,inicio,estado,extra,nome,dia,orderTiming,endereco_entrega,order_id,remetente,horario_para_entrega) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            row['produto'], row['quantidade'], row['preco_total'], 3,
            data['pedido_hora'], 'A Fazer', extra, data['cliente_nome'],
            data['pedido_data'], data['orderTiming'], endereco, data['pedido_id'],
            'IFOOD', data['pedido_hora']
        )

# --------- PROCESSAMENTO DE EVENTO ----------
def _event_code(evt: dict) -> str:
    return (evt.get("fullCode") or evt.get("code") or evt.get("event") or evt.get("eventType") or "").upper()

def _process_ifood_event(evt: dict):
    code = _event_code(evt)

    # Exemplos que você pode expandir: CONFIRMED, CANCELLATION_REQUESTED, etc.
    if code in ("PLACED", "PLC"):
        order_id = evt.get("orderId") or evt.get("id")
        token, _ = get_ifood_token()
        pedido_detalhes(order_id, token)

    # Aqui você pode gravar o evento para idempotência (recomendado)
    # Exemplo:
    # db.execute('INSERT OR IGNORE INTO ifood_events (event_id, order_id, code, received_at) VALUES (?,?,?,CURRENT_TIMESTAMP)',
    #            evt.get("id") or evt.get("orderId") or "", order_id or "", code)

# --------- ROTAS ----------
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
    - Responder 202 em até 5s
    - Validar assinatura HMAC (X-IFood-Signature) no raw body
    - Tratar presença (KEEPALIVE)
    - Enfileirar processamento
    """
    try:
        # 1) valida assinatura (obrigatório)
        if not _valid_signature(request):
            return jsonify({"error": "invalid signature"}), 401

        # 2) payload pode ser dict ou lista
        data = request.get_json(silent=True)
        if data is None:
            # corpo pode ser vazio em alguns heartbeats
            return ("", 202)

        # normaliza para lista
        events = data if isinstance(data, list) else [data]

        # 3) trata KEEPALIVE rapidamente
        # se qualquer evento for KEEPALIVE com merchantIds, responde com merchantIds online
        for evt in events:
            code = _event_code(evt)
            if code in ("KEEPALIVE", "KEEP-ALIVE", "HEARTBEAT"):
                mids = evt.get("merchantIds")
                if isinstance(mids, list) and mids:
                    return jsonify({"merchantIds": mids}), 202
                # sem mids: apenas aceite
                return ("", 202)

        # 4) enfileira todos os eventos para processamento assíncrono
        for evt in events:
            _event_q.put(evt)

        return ("", 202)
    except Exception as e:
        print(f"[webhook_ifood] erro: {e}")
        # se você NÃO quiser retentativa, mantenha 202 mesmo com erro.
        return ("", 202)

@app.route('/botaoActionIfood', methods=['POST'])
def postarActionIfood():
    """
    Dispara uma ação do pedido no iFood (confirm, startPreparation, readyToPickup, dispatch, requestCancellation...).
    Usa POST e espera, em geral, 202 (sem corpo).
    """
    data = request.get_json() or {}
    order_id = data.get('order_id')
    action = data.get('action')  # ex: "confirm", "startPreparation", "readyToPickup", "dispatch", "requestCancellation"
    estado = data.get('newState')  # estado que você quer refletir no seu DB (opcional)

    if not order_id or not action:
        return {"ok": False, "error": "ID do pedido/ação não fornecidos", "status_code": 400}

    def _call(api_token: str):
        url = f"https://merchant-api.ifood.com.br/order/v1.0/orders/{order_id}/{action}"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        body = {}
        # Exemplo: cancelamento pode exigir body com razão
        if action == "requestCancellation":
            reason = data.get("reasonCode") or "OTHER"
            description = data.get("reasonDescription") or ""
            body = {"reason": reason, "description": description}

        return requests.post(url, headers=headers, json=body, timeout=20)

    try:
        access_token, _ = get_ifood_token()
        resp = _call(access_token)

        if resp.status_code in (401, 403):
            # força refresh e tenta de novo
            _token_cache["accessToken"] = None
            _token_cache["expiresAt"] = 0
            access_token, _ = get_ifood_token()
            resp = _call(access_token)

        ok = (resp.status_code == 202)

        # nem sempre há JSON no 202
        try:
            payload = resp.json()
        except ValueError:
            payload = {"status": resp.status_code, "text": (resp.text or "")[:200]}

        # Atualiza estado no seu DB, se você mandou 'newState'
        if ok and estado:
            try:
                db.execute('UPDATE pedidos SET estado = ? WHERE order_id = ?', estado, order_id)
            except Exception as e:
                print("[ifood][action] falha ao atualizar estado local:", e)

        return {"ok": ok, "response": payload, "status_code": resp.status_code}
    except requests.RequestException as e:
        return {"ok": False, "error": f"HTTP error: {e}", "status_code": getattr(e.response, "status_code", None)}
    except Exception as e:
        return {"ok": False, "error": str(e), "status_code": 500}
