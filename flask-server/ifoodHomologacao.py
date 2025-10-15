# ===========================
# IFOOD - FLUXO COMPLETO (Flask)
# ===========================
import os
import time
import hmac
import json
import queue
import hashlib
import threading
from typing import Any, Dict, Optional, List, Tuple

from dotenv import load_dotenv
import requests
from flask import Flask, request, jsonify
from cs50 import SQL
from datetime import datetime

# ---------------- Base Flask & DB ----------------
app = Flask(__name__)

DATABASE_PATH = os.getenv("IFOOD_DB_PATH", "/data/dados.db")
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
db = SQL("sqlite:///" + DATABASE_PATH)

# ---------------- TZ ----------------
try:
    import zoneinfo
    tz_sp = zoneinfo.ZoneInfo("America/Sao_Paulo")
except Exception:
    from datetime import timezone, timedelta
    tz_sp = timezone(timedelta(hours=-3))

def parse_iso_br(dt_str: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not dt_str:
        return None, None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00")).astimezone(tz_sp)
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")
    except Exception:
        return None, None

# ---------------- ENV ----------------
load_dotenv()
SEU_CLIENT_ID      = os.getenv("SEU_CLIENT_ID")
SEU_CLIENT_SECRET  = os.getenv("SEU_CLIENT_SECRET")
TOKEN_URL          = os.getenv("TOKEN_URL", "https://merchant-api.ifood.com.br/authentication/v1.0/oauth/token")
WEBHOOK_SECRET     = os.getenv("IFOOD_WEBHOOK_SECRET") or SEU_CLIENT_SECRET
POLL_EVERY_SECONDS = int(os.getenv("IFOOD_POLL_INTERVAL", "30"))  # regra: 30s
MERCHANT_IDS_ENV   = os.getenv("IFOOD_MERCHANT_IDS")  # "merchantA,merchantB"
START_POLLING_ENV  = os.getenv("IFOOD_POLLING_START", "0") == "1"

# ---------------- HTTP Session ----------------
SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json"})
ADAPTER_KW = dict(pool_connections=30, pool_maxsize=60, max_retries=0)
SESSION.mount("https://", requests.adapters.HTTPAdapter(**ADAPTER_KW))
SESSION.mount("http://",  requests.adapters.HTTPAdapter(**ADAPTER_KW))

# ---------------- Token cache ----------------
_token_cache = {"accessToken": None, "expiresAt": 0.0}
_cache_lock = threading.Lock()

def get_ifood_token() -> Tuple[str, float]:
    """
    Retorna (access_token, expires_at). Renova 60s antes de expirar.
    """
    with _cache_lock:
        now = time.time()
        if _token_cache["accessToken"] and (_token_cache["expiresAt"] - now > 60):
            return _token_cache["accessToken"], _token_cache["expiresAt"]

        if not SEU_CLIENT_ID or not SEU_CLIENT_SECRET or not TOKEN_URL:
            raise RuntimeError("SEU_CLIENT_ID/SEU_CLIENT_SECRET/TOKEN_URL não configurados.")

        data = {
            "grantType": "client_credentials",
            "clientId": SEU_CLIENT_ID,
            "clientSecret": SEU_CLIENT_SECRET,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        r = SESSION.post(TOKEN_URL, data=data, headers=headers, timeout=20)
        r.raise_for_status()
        payload = r.json()
        access_token = payload.get("accessToken") or payload.get("access_token")
        expires_in   = int(payload.get("expiresIn") or payload.get("expires_in") or 0)
        if not access_token or not expires_in:
            raise RuntimeError(f"Resposta de token inesperada: {payload}")

        expires_at = now + expires_in
        _token_cache["accessToken"] = access_token
        _token_cache["expiresAt"]   = expires_at
        return access_token, expires_at

def invalidate_token():
    with _cache_lock:
        _token_cache["accessToken"] = None
        _token_cache["expiresAt"]   = 0.0

# ---------------- Schema mínimo ----------------
def ensure_schema():
    db.execute("""
    CREATE TABLE IF NOT EXISTS ifood_events (
      event_id    TEXT PRIMARY KEY,
      order_id    TEXT,
      code        TEXT,
      received_at TEXT
    )""")

    db.execute("""
    CREATE TABLE IF NOT EXISTS pedidos (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      pedido TEXT,                -- nome do item
      quantidade INTEGER,
      preco REAL,
      categoria INTEGER,
      inicio TEXT,                -- hora do pedido
      estado TEXT,
      extra TEXT,                 -- obs + complementos
      nome TEXT,                  -- nome do cliente
      dia TEXT,                   -- data do pedido
      orderTiming TEXT,           -- IMMEDIATE / SCHEDULED
      endereco_entrega TEXT,      -- rua + numero ou 'Retirada no balcão'
      order_id TEXT UNIQUE,       -- id do pedido iFood
      remetente TEXT,             -- 'IFOOD'
      horario_para_entrega TEXT,  -- hora agendada ou hora do pedido
      cpf_cnpj TEXT,              -- documento do cliente, se houver
      codigo_coleta TEXT          -- pickup code (TAKEOUT) se houver
    )""")

    db.execute("""
    CREATE TABLE IF NOT EXISTS ifood_pedidos_payments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      order_id TEXT,
      nome TEXT,           -- ex: CREDIT, DEBIT, PIX
      presencial INTEGER,  -- 0/1
      bandeira TEXT,       -- VISA/MASTERCARD...
      adquirente TEXT,
      valor REAL,
      liability TEXT       -- quem recebe (MERCHANT/IFOOD)
    )""")

    db.execute("""
    CREATE TABLE IF NOT EXISTS ifood_pedidos_benefits (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      order_id TEXT,
      alvo TEXT,           -- target (ORDER/ITEM)
      responsavel TEXT,    -- liability (IFOOD/MERCHANT)
      valor REAL
    )""")

ensure_schema()

# ---------------- Assinatura HMAC (Webhook) ----------------
def _valid_signature(req) -> bool:
    try:
        raw  = req.get_data(cache=False)  # bytes exatos
        sent = req.headers.get("X-IFood-Signature", "")
        if not (raw and sent and WEBHOOK_SECRET):
            return False
        mac  = hmac.new(WEBHOOK_SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
        return hmac.compare_digest(mac, sent)
    except Exception:
        return False

# ---------------- Fila e worker ----------------
_event_q: "queue.SimpleQueue[dict]" = queue.SimpleQueue()

def _event_code(evt: dict) -> str:
    return (evt.get("fullCode") or evt.get("code") or evt.get("event") or evt.get("eventType") or "").upper()

def _human_state_from_code(code: str) -> Optional[str]:
    # mapeamento mínimo para refletir status no PDV
    m = {
        "PLACED": "Novo",
        "CONFIRMED": "Confirmado",
        "READY_TO_PICKUP": "Pronto para retirada",
        "DISPATCHED": "Despachado",
        "CANCELLATION_REQUESTED": "Cancelamento solicitado",
        "CANCELLED": "Cancelado",
        "CANCELED": "Cancelado",
        "CANC_APPROVED": "Cancelado",
    }
    return m.get(code)

def _worker_loop():
    while True:
        evt = _event_q.get()
        try:
            _process_ifood_event(evt)
        except Exception as e:
            print("[webhook_ifood][worker] erro:", e)

threading.Thread(target=_worker_loop, daemon=True).start()

# ---------------- Extração do Pedido ----------------
def extrair_pedido_ifood(order: dict) -> dict:
    total_block = order.get("total") or {}
    delivery    = order.get("delivery") or {}
    addr        = delivery.get("deliveryAddress") or {}

    pedido_data, pedido_hora         = parse_iso_br(order.get("createdAt"))
    agendamento_data, agendamento_h  = parse_iso_br(delivery.get("deliveryDateTime"))

    # Payments
    payments_out = []
    methods = (order.get("payments") or {}).get("methods", [])
    for pm in methods:
        card   = pm.get("card") or {}
        amount = (pm.get("amount") or {}).get("value") or 0
        payments_out.append({
            "nome": pm.get("name"),
            "presencial": 1 if pm.get("inPerson") else 0,
            "bandeira": card.get("brand"),
            "adquirente": card.get("provider"),
            "valor": amount/100.0,
            "liability": pm.get("liability"),
        })

    # Benefits / Subsídios
    beneficios_out = []
    benefits = (order.get("benefits") or {}).get("benefits", [])
    for b in benefits:
        for s in (b.get("sponsorships") or []):
            val = (s.get("amount") or {}).get("value") or 0
            beneficios_out.append({
                "alvo": b.get("target"),
                "responsavel": s.get("liability"),
                "valor": val/100.0
            })

    # Itens + complementos
    itens_out: List[dict] = []
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
        itens_out.append(item_dict)

    verification_codes = order.get("verificationCodes") or {}
    pickup_code = verification_codes.get("takeout") or verification_codes.get("pickup") or verification_codes.get("code")

    return {
        "pedido_id": order.get("id"),
        "display_id": order.get("displayId"),
        "cliente_nome": (order.get("customer") or {}).get("name"),
        "cliente_documento": (order.get("customer") or {}).get("documentNumber"),
        "produtos": itens_out,
        "valor_sem_taxas": total_block.get("subTotal"),
        "valor_com_taxas": total_block.get("orderAmount"),
        "endereco": {
            "rua": addr.get("streetName"),
            "numero": addr.get("streetNumber"),
            "bairro": addr.get("neighborhood"),
            "cidade": addr.get("city"),
            "estado": addr.get("state"),
            "cep": addr.get("postalCode"),
            "complemento": addr.get("complement"),
            "referencia": addr.get("reference"),
        },
        "pedido_data": pedido_data,
        "pedido_hora": pedido_hora,
        "orderTiming": order.get("orderTiming"),
        "agendamento_data": agendamento_data,
        "agendamento_hora": agendamento_h,
        "delivery_observations": delivery.get("observations"),
        "payments": payments_out,
        "beneficios": beneficios_out,
        "pickup_code": pickup_code,
        "takeout": order.get("takeout") or {},
    }

def pedido_detalhes(order_id: str, access_token: Optional[str] = None):
    if not access_token:
        access_token, _ = get_ifood_token()

    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    url_order = f"https://merchant-api.ifood.com.br/order/v1.0/orders/{order_id}"
    resp = SESSION.get(url_order, headers=headers, timeout=20)
    if resp.status_code in (401, 403):
        invalidate_token()
        access_token, _ = get_ifood_token()
        headers["Authorization"] = f"Bearer {access_token}"
        resp = SESSION.get(url_order, headers=headers, timeout=20)
    resp.raise_for_status()
    order = resp.json()

    data = extrair_pedido_ifood(order)

    # Endereço (ou retirada)
    end = data.get("endereco") or {}
    endereco = " ".join(s for s in [end.get("rua"), str(end.get("numero") or "").strip()] if s).strip()
    endereco = endereco or "Retirada no balcão"

    # Observações / complementos
    for row in data.get("produtos", []):
        extra = (row.get("observacoes") or "")
        for comp in row.get("complementos", []):
            extra += f"\n{comp.get('quantidade',1)} {comp.get('nome','')}"

        hora_entrega = data["agendamento_hora"] or data["pedido_hora"]

        # INSERT item a item (um registro por item do pedido)
        db.execute(
            """INSERT OR IGNORE INTO pedidos
               (pedido, quantidade, preco, categoria, inicio, estado, extra, nome, dia,
                orderTiming, endereco_entrega, order_id, remetente, horario_para_entrega, cpf_cnpj, codigo_coleta)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            row["produto"], row["quantidade"], row["preco_total"], 3,
            data["pedido_hora"], "A Fazer", extra, data["cliente_nome"],
            data["pedido_data"], data["orderTiming"], endereco, data["pedido_id"],
            "IFOOD", hora_entrega, (data.get("cliente_documento") or ""), (data.get("pickup_code") or "")
        )

    # Pagamentos
    for p in data.get("payments", []):
        db.execute(
            """INSERT INTO ifood_pedidos_payments
               (order_id, nome, presencial, bandeira, adquirente, valor, liability)
               VALUES (?,?,?,?,?,?,?)""",
            data["pedido_id"], p["nome"], p["presencial"], p["bandeira"], p["adquirente"], p["valor"], p["liability"]
        )

    # Benefícios/Subsídios
    for b in data.get("beneficios", []):
        db.execute(
            """INSERT INTO ifood_pedidos_benefits
               (order_id, alvo, responsavel, valor)
               VALUES (?,?,?,?)""",
            data["pedido_id"], b["alvo"], b["responsavel"], b["valor"]
        )

# ---------------- Processamento de eventos ----------------
def _process_ifood_event(evt: dict):
    code     = _event_code(evt)
    order_id = evt.get("orderId") or evt.get("id")

    # PLACED -> carregar detalhes
    if code in ("PLACED", "PLC"):
        token, _ = get_ifood_token()
        pedido_detalhes(order_id, token)
        db.execute('UPDATE pedidos SET estado=? WHERE order_id=?', "Novo", order_id)

    elif code in ("CONFIRMED", "CFM"):
        db.execute('UPDATE pedidos SET estado=? WHERE order_id=?', "Confirmado", order_id)

    elif code in ("READY_TO_PICKUP", "RTP"):
        # manter pickup code (já salvo por pedido_detalhes); aqui só reflete estado
        db.execute('UPDATE pedidos SET estado=? WHERE order_id=?', "Pronto para retirada", order_id)

    elif code in ("DISPATCHED", "DSP"):
        db.execute('UPDATE pedidos SET estado=? WHERE order_id=?', "Despachado", order_id)

    elif code in ("CANCELLATION_REQUESTED", "CANC_REQ"):
        db.execute('UPDATE pedidos SET estado=? WHERE order_id=?', "Cancelamento solicitado", order_id)

    elif code in ("CANCELLED", "CANCELED", "CANC_APPROVED"):
        db.execute('UPDATE pedidos SET estado=? WHERE order_id=?', "Cancelado", order_id)

    # Plataforma de Negociação de Pedidos / outros códigos:
    # Se precisar, adicione aqui os códigos NEGOTIATION_* => atualize estado/observações específicas.

# ---------------- Polling + ACK + Idempotência ----------------
_stop_polling = threading.Event()
_polling_thread = None

def _ack_events(headers: dict, event_ids: List[str]):
    if not event_ids:
        return
    url_ack = "https://merchant-api.ifood.com.br/order/v1.0/events/acknowledgment"
    try:
        SESSION.post(url_ack, headers=headers, json={"eventIds": event_ids}, timeout=20)
    except Exception as e:
        print("[ifood][ack] erro:", e)

def _polling_loop(merchant_ids: Optional[List[str]] = None):
    jitter = 0
    while not _stop_polling.is_set():
        try:
            token, _ = get_ifood_token()
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
            if merchant_ids:
                headers["x-polling-merchants"] = ",".join(merchant_ids)

            url = "https://merchant-api.ifood.com.br/order/v1.0/events:polling"
            resp = SESSION.get(url, headers=headers, timeout=20)
            if resp.status_code in (401, 403):
                invalidate_token()
                token, _ = get_ifood_token()
                headers["Authorization"] = f"Bearer {token}"
                resp = SESSION.get(url, headers=headers, timeout=20)
            resp.raise_for_status()

            events = resp.json() or []
            ids = [e.get("id") for e in events if e.get("id")]

            # ACK imediato de TUDO (independente de processamento)
            if ids:
                _ack_events(headers, ids)

            # processar com idempotência
            for evt in events:
                eid = evt.get("id")
                if not eid:
                    continue
                exists = db.execute("SELECT 1 FROM ifood_events WHERE event_id=? LIMIT 1", eid)
                if exists:
                    continue
                db.execute(
                    "INSERT OR IGNORE INTO ifood_events (event_id, order_id, code, received_at) VALUES (?,?,?,datetime('now'))",
                    eid, evt.get("orderId") or evt.get("id") or "", _event_code(evt)
                )
                _event_q.put(evt)

        except Exception as e:
            print("[ifood][polling] erro:", e)

        time.sleep(POLL_EVERY_SECONDS + jitter)
        jitter = (jitter + 1) % 3  # jitter leve anti-sincronismo

def start_ifood_polling(merchant_ids: Optional[List[str]] = None):
    global _polling_thread
    if _polling_thread and _polling_thread.is_alive():
        return
    _stop_polling.clear()
    _polling_thread = threading.Thread(target=_polling_loop, args=(merchant_ids,), daemon=True)
    _polling_thread.start()

def stop_ifood_polling():
    _stop_polling.set()

# ---------------- Rotas ----------------
@app.route("/ifood/token", methods=["GET"])
def ifood_token_health():
    try:
        token, exp = get_ifood_token()
        return jsonify({"ok": True, "accessToken": token, "expiresAt": int(exp)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/ifood/cancellation_reasons", methods=["GET"])
def ifood_cancellation_reasons():
    order_id = request.args.get("order_id")
    if not order_id:
        return {"ok": False, "error": "order_id obrigatório"}, 400
    token, _ = get_ifood_token()
    url = f"https://merchant-api.ifood.com.br/order/v1.0/orders/{order_id}/cancellationReasons"
    resp = SESSION.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=20)
    if resp.status_code in (401, 403):
        invalidate_token()
        token, _ = get_ifood_token()
        resp = SESSION.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=20)
    try:
        resp.raise_for_status()
        return {"ok": True, "reasons": resp.json()}
    except requests.HTTPError:
        return {"ok": False, "status": resp.status_code, "text": (resp.text or "")[:200]}, 502

@app.route('/webhook_ifood', methods=['POST'])
def webhook_ifood():
    """
    - Valida HMAC (X-IFood-Signature)
    - Responde 202 em até 5s
    - Trata KEEPALIVE (retorna merchantIds)
    - Enfileira eventos (idempotência no worker/polling)
    """
    try:
        # 1) assinatura
        if not _valid_signature(request):
            return jsonify({"error": "invalid signature"}), 401

        # 2) corpo pode ser lista ou dict ou até vazio (heartbeat)
        data = request.get_json(silent=True)
        if data is None:
            return ("", 202)

        events = data if isinstance(data, list) else [data]

        # 3) KEEPALIVE
        for evt in events:
            code = _event_code(evt)
            if code in ("KEEPALIVE", "KEEP-ALIVE", "HEARTBEAT"):
                mids = evt.get("merchantIds")
                if isinstance(mids, list) and mids:
                    return jsonify({"merchantIds": mids}), 202
                return ("", 202)

        # 4) Enfileira (ACK é somente no polling; no webhook basta 202)
        for evt in events:
            _event_q.put(evt)

        return ("", 202)
    except Exception as e:
        print(f"[webhook_ifood] erro: {e}")
        return ("", 202)  # manter 202 para evitar retentativas agressivas

@app.route('/ifood/action', methods=['POST'])
def ifood_action():
    """
    Dispara ações: confirm, startPreparation, readyToPickup, dispatch, requestCancellation.
    Para cancelamento: consultar /cancellationReasons antes e enviar reasonCode/description.
    """
    data = request.get_json(force=True) or {}
    order_id = data.get('order_id')
    action   = data.get('action')  # "confirm" | "startPreparation" | "readyToPickup" | "dispatch" | "requestCancellation"
    estado   = data.get('newState')  # opcional: refletir estado local

    if not order_id or not action:
        return {"ok": False, "error": "order_id e action são obrigatórios"}, 400

    def _call(api_token: str):
        url = f"https://merchant-api.ifood.com.br/order/v1.0/orders/{order_id}/{action}"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        body = {}
        if action == "requestCancellation":
            # Exigir reasonCode do front (após listar via /cancellationReasons)
            reason = data.get("reasonCode")
            if not reason:
                return None, {"ok": False, "error": "reasonCode obrigatório para requestCancellation", "status_code": 400}
            body = {"reason": reason, "description": data.get("reasonDescription") or ""}

        resp = SESSION.post(url, headers=headers, json=body, timeout=20)
        return resp, None

    try:
        token, _ = get_ifood_token()
        resp, early = _call(token)
        if early:
            return early, 400
        if resp.status_code in (401, 403):
            invalidate_token()
            token, _ = get_ifood_token()
            resp, _ = _call(token)

        ok = (resp.status_code == 202)
        try:
            payload = resp.json()
        except ValueError:
            payload = {"status": resp.status_code, "text": (resp.text or "")[:200]}

        if ok and estado:
            try:
                db.execute('UPDATE pedidos SET estado=? WHERE order_id=?', estado, order_id)
            except Exception as e:
                print("[ifood][action] falha ao atualizar estado local:", e)

        return {"ok": ok, "response": payload, "status_code": resp.status_code}
    except requests.RequestException as e:
        return {"ok": False, "error": f"HTTP error: {e}", "status_code": getattr(e.response, "status_code", None)}, 502
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500

@app.route("/ifood/order/<order_id>", methods=["GET"])
def ifood_order_detail(order_id: str):
    "Endpoint utilitário de inspeção (exibir campos cruciais para a UI/comanda)."
    token, _ = get_ifood_token()
    url = f"https://merchant-api.ifood.com.br/order/v1.0/orders/{order_id}"
    resp = SESSION.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=20)
    if resp.status_code in (401, 403):
        invalidate_token()
        token, _ = get_ifood_token()
        resp = SESSION.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=20)
    resp.raise_for_status()
    order = resp.json()
    data = extrair_pedido_ifood(order)
    return jsonify({"ok": True, "order": data})

@app.route("/ifood/polling/start", methods=["POST"])
def http_start_polling():
    body = request.get_json(silent=True) or {}
    mids = body.get("merchant_ids")
    if mids and isinstance(mids, str):
        mids = [x.strip() for x in mids.split(",") if x.strip()]
    start_ifood_polling(mids)
    return {"ok": True, "running": True}

@app.route("/ifood/polling/stop", methods=["POST"])
def http_stop_polling():
    stop_ifood_polling()
    return {"ok": True, "running": False}

# ---------------- Inicialização opcional do polling ----------------
if START_POLLING_ENV:
    mids = None
    if MERCHANT_IDS_ENV:
        mids = [x.strip() for x in MERCHANT_IDS_ENV.split(",") if x.strip()]
    start_ifood_polling(mids)

# ---------------- Main guard (opcional) ----------------
if __name__ == "__main__":
    # Inicie como preferir (gunicorn/uwsgi em produção; aqui apenas dev)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=False)
