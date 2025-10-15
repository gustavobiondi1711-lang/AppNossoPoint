import jwt
from datetime import datetime, timezone

SECRET_KEY = "sua_chave_super_secreta_aqui"  # guarde com segurança

def decode_number_jwt(token: str) -> int:
    decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    # decoded é dict; o sub tem o número
    print(decoded['sub'])
    return int(decoded["sub"])

def encode_number_jwt(number: int) -> str:
    payload = {
        "sub": str(number),
        "iat": int(datetime.now(timezone.utc).timestamp())  # opcional
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    # pyjwt retorna str (ou bytes em versões antigas)
    print(token)

#encode_number_jwt(5)


decode_number_jwt('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1IiwiaWF0IjoxNzYwMzk2NDE0fQ.D4t-lSK98nwa8bzwxisfWCaqrj1Z2BVRWwDtL8I1S2Y')