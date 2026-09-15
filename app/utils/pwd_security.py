from passlib.hash import pbkdf2_sha256

def get_hash_password(password: str) -> str:
    return pbkdf2_sha256.hash(password)
#验证密码：返回值是BOOL
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pbkdf2_sha256.verify(plain_password, hashed_password)
